import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import cv2

from app.core.anotador import dibujar_detecciones
from app.core.detector import Detector
from app.core.motor_alertas import MotorAlertas
from app.services.alerta_service import AlertaService

log = logging.getLogger("lector")


class EstadoCamara(str, Enum):
    conectando = "conectando"
    normal = "normal"
    alerta = "alerta"
    sin_conexion = "sin_conexion"
    inactiva = "inactiva"


@dataclass(frozen=True)
class CamaraCfg:
    """Copia de los datos de la cámara (el hilo no usa objetos de la base)."""
    id: int
    nombre: str
    url: str
    conf_humo: float
    conf_fuego: float


class LectorCamara(threading.Thread):
    def __init__(self, cfg: CamaraCfg, detector: Detector, servicio: AlertaService,
                 ventana: int, minimo: int, cierre_seg: float,
                 fps_proceso: float = 2, espera_max: float = 30):
        super().__init__(name=f"camara-{cfg.id}", daemon=True)
        self.cfg = cfg
        self.detector = detector
        self.servicio = servicio
        self.motor = MotorAlertas(ventana, minimo, cierre_seg)
        self.intervalo = 1 / fps_proceso
        self.espera_max = espera_max

        # OJO: no llamarlo _stop, porque threading.Thread ya usa ese nombre
        self._parar = threading.Event()
        self._lock = threading.Lock()
        self._estado = EstadoCamara.conectando
        self._error: Optional[str] = None
        self._jpg: Optional[bytes] = None
        self._actualizacion: Optional[datetime] = None
        self._procesados = 0

    # ---------- lo que consulta la API (desde otro hilo) ----------
    def parar(self):
        self._parar.set()

    def estado(self) -> dict:
        with self._lock:
            return {
                "estado": self._estado,
                "ultima_actualizacion": self._actualizacion,
                "ultimo_error": self._error,
                "fotogramas_procesados": self._procesados,
            }

    def ultimo_frame(self) -> Optional[bytes]:
        with self._lock:
            return self._jpg

    # ---------- bucle del hilo ----------
    def run(self):
        c = self.cfg
        fuente = int(c.url) if c.url.isdigit() else c.url      # "0" = webcam
        es_archivo = isinstance(fuente, str) and os.path.isfile(fuente)
        cap = None
        espera = 2.0
        fps_fuente = 30.0
        fallos = 0
        ultimo_proceso = 0.0

        while not self._parar.is_set():
            # 1) conectar (con reintentos que se van espaciando)
            if cap is None:
                cap = cv2.VideoCapture(fuente)
                if not cap.isOpened():
                    cap.release()
                    cap = None
                    self._cambiar_estado(EstadoCamara.sin_conexion,
                                         "No se pudo abrir la fuente de video")
                    self._parar.wait(espera)
                    espera = min(espera * 2, self.espera_max)
                    continue
                espera = 2.0
                fallos = 0
                fps_fuente = cap.get(cv2.CAP_PROP_FPS) or 30.0
                self._cambiar_estado(EstadoCamara.conectando)

            # 2) avanzar un fotograma (sin decodificarlo del todo)
            if not cap.grab():
                fallos += 1
                if es_archivo and fallos == 1:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)   # el video de prueba da la vuelta
                    continue
                cap.release()
                cap = None
                self._cambiar_estado(EstadoCamara.sin_conexion, "Se perdió la señal")
                self._parar.wait(espera)
                continue
            fallos = 0

            # un archivo se lee a velocidad real para simular una cámara
            if es_archivo:
                self._parar.wait(1 / fps_fuente)

            # 3) analizar solo a la frecuencia configurada; el resto se descarta
            ahora = time.monotonic()
            if ahora - ultimo_proceso < self.intervalo:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                continue
            ultimo_proceso = ahora
            self._procesar(frame, ahora)

        if cap is not None:
            cap.release()
        self._cambiar_estado(EstadoCamara.inactiva)

    def _procesar(self, frame, t: float):
        c = self.cfg
        try:
            # el modelo corre con el umbral más bajo y luego se filtra por clase
            dets = self.detector.detectar(frame, conf=min(c.conf_humo, c.conf_fuego))
            dets = [d for d in dets
                    if d.confianza >= (c.conf_humo if d.clase == "smoke" else c.conf_fuego)]

            if self.motor.evaluar(dets, t):
                self.servicio.registrar(c.id, frame, dets)

            self._guardar_frame(frame, dets)
            self._cambiar_estado(
                EstadoCamara.alerta if self.motor.evento_activo else EstadoCamara.normal
            )
        except Exception:
            # un fallo en un fotograma no debe matar el hilo
            log.exception("Error procesando un fotograma de la cámara %s", c.id)

    def _guardar_frame(self, frame, dets):
        img = dibujar_detecciones(frame, dets) if dets else frame
        h, w = img.shape[:2]
        if w > 960:
            img = cv2.resize(img, (960, int(h * 960 / w)))
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            with self._lock:
                self._jpg = buf.tobytes()
                self._actualizacion = datetime.now(timezone.utc)
                self._procesados += 1

    def _cambiar_estado(self, estado: EstadoCamara, error: Optional[str] = None):
        with self._lock:
            if estado != self._estado:
                log.info("Cámara %s (%s): %s", self.cfg.id, self.cfg.nombre, estado.value)
            self._estado = estado
            self._error = error