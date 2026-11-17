import logging
import os
import threading
import time
from concurrent.futures import Future
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


def filtrar_detecciones_objetivo(detecciones, conf_humo: float, conf_fuego: float):
    umbrales = {"smoke": conf_humo, "fire": conf_fuego}
    return [
        deteccion
        for deteccion in detecciones
        if deteccion.clase.strip().casefold() in umbrales
        and deteccion.confianza >= umbrales[deteccion.clase.strip().casefold()]
    ]


class LectorCamara(threading.Thread):
    def __init__(self, cfg: CamaraCfg, detector: Detector, servicio: AlertaService,
                 ventana: int, minimo: int, cierre_seg: float,
                 fps_proceso: float = 2, fps_vista: float = 30,
                 espera_max: float = 30):
        super().__init__(name=f"camara-{cfg.id}", daemon=True)
        self.cfg = cfg
        self.detector = detector
        self.servicio = servicio
        self.motor = MotorAlertas(ventana, minimo, cierre_seg)
        self.intervalo = 1 / fps_proceso
        self.intervalo_vista = 1 / fps_vista
        self.espera_max = espera_max

        # OJO: no llamarlo _stop, porque threading.Thread ya usa ese nombre
        self._parar = threading.Event()
        self._lock = threading.Lock()
        self._estado = EstadoCamara.conectando
        self._error: Optional[str] = None
        self._frame = None
        self._frame_anotado = None
        self._jpg: Optional[bytes] = None
        self._jpg_version = -1
        self._version_frame = 0
        self._actualizacion: Optional[datetime] = None
        self._procesados = 0
        self._detecciones = []
        self._ancho_frame = 0
        self._alto_frame = 0

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
            return self._jpeg_actual()

    def fotograma(self) -> tuple[Optional[bytes], int]:
        with self._lock:
            return self._jpeg_actual(), self._version_frame

    def frame_bgr(self):
        with self._lock:
            return (self._frame.copy() if self._frame is not None else None,
                    self._version_frame)

    def detecciones(self) -> dict:
        with self._lock:
            return {
                "ancho": self._ancho_frame,
                "alto": self._alto_frame,
                "detecciones": [deteccion.copy() for deteccion in self._detecciones],
            }

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
        ultima_vista = 0.0
        inferencia: Optional[Future] = None
        frame_inferencia = None
        tiempo_inferencia = 0.0
        detecciones_actuales = []

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

            ahora = time.monotonic()
            ok, frame = cap.retrieve()
            if not ok:
                continue

            if inferencia is not None and inferencia.done():
                try:
                    resultado = inferencia.result()
                    procesadas = self._procesar(frame_inferencia, resultado, tiempo_inferencia)
                    if procesadas is not None:
                        detecciones_actuales = procesadas
                except Exception:
                    log.exception("Error procesando un fotograma de la cámara %s", c.id)
                inferencia = None
                frame_inferencia = None

            if ahora - ultima_vista >= self.intervalo_vista:
                self._guardar_frame(frame, detecciones_actuales, analizado=False)
                ultima_vista = ahora

            if inferencia is None and ahora - ultimo_proceso >= self.intervalo:
                ultimo_proceso = ahora
                inferencia = self.detector.detectar_async(
                    frame,
                    conf=min(c.conf_humo, c.conf_fuego),
                    cancelar=self._parar,
                )
                if inferencia is not None:
                    frame_inferencia = frame.copy()
                    tiempo_inferencia = ahora

        if cap is not None:
            cap.release()
        self._cambiar_estado(EstadoCamara.inactiva)

    def _procesar(self, frame, detecciones, t: float):
        c = self.cfg
        try:
            dets = filtrar_detecciones_objetivo(detecciones, c.conf_humo, c.conf_fuego)
            alto, ancho = frame.shape[:2]
            with self._lock:
                self._detecciones = [
                    {
                        "clase": deteccion.clase,
                        "confianza": deteccion.confianza,
                        "caja": list(deteccion.caja),
                    }
                    for deteccion in dets
                ]
                self._ancho_frame = ancho
                self._alto_frame = alto

            if self.motor.evaluar(dets, t):
                self.servicio.registrar(c.id, frame, dets)

            self._guardar_frame(frame, dets, analizado=True)
            self._cambiar_estado(
                EstadoCamara.alerta if self.motor.evento_activo else EstadoCamara.normal
            )
            return dets
        except Exception:
            log.exception("Error procesando un fotograma de la cámara %s", c.id)
            return None

    def _guardar_frame(self, frame, dets, analizado: bool = True):
        img = dibujar_detecciones(frame, dets) if dets else frame
        h, w = img.shape[:2]
        frame_video = frame
        if w > 960:
            dimensiones = (960, int(h * 960 / w))
            img = cv2.resize(img, dimensiones)
            frame_video = cv2.resize(frame, dimensiones)
        with self._lock:
            self._frame = frame_video.copy()
            self._frame_anotado = img.copy()
            self._jpg_version = -1
            self._actualizacion = datetime.now(timezone.utc)
            self._version_frame += 1
            if analizado:
                self._procesados += 1

    def _jpeg_actual(self) -> Optional[bytes]:
        if self._frame_anotado is None:
            return None
        if self._jpg_version != self._version_frame:
            ok, buf = cv2.imencode(
                ".jpg", self._frame_anotado, [cv2.IMWRITE_JPEG_QUALITY, 80]
            )
            if not ok:
                return None
            self._jpg = buf.tobytes()
            self._jpg_version = self._version_frame
        return self._jpg

    def _cambiar_estado(self, estado: EstadoCamara, error: Optional[str] = None):
        with self._lock:
            if estado != self._estado:
                log.info("Cámara %s (%s): %s", self.cfg.id, self.cfg.nombre, estado.value)
            self._estado = estado
            self._error = error