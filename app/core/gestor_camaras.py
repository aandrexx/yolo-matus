import threading
from typing import Optional

from sqlalchemy import select

from app.core.detector import Detector
from app.core.lector_camara import CamaraCfg, LectorCamara
from app.db import SessionLocal
from app.models import Camara
from app.services.alerta_service import AlertaService


class GestorCamaras:
    """Mantiene un LectorCamara por cada cámara activa."""

    def __init__(self, detector: Detector, servicio: AlertaService,
                 ventana: int, minimo: int, cierre_seg: float, fps_proceso: float):
        self._args = (detector, servicio, ventana, minimo, cierre_seg, fps_proceso)
        self._lectores: dict[int, LectorCamara] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _cfg(c: Camara) -> CamaraCfg:
        return CamaraCfg(c.id, c.nombre, c.url, c.conf_humo, c.conf_fuego)

    def iniciar_activas(self):
        with SessionLocal() as db:
            for c in db.scalars(select(Camara).where(Camara.activa.is_(True))):
                self._arrancar(self._cfg(c))

    def sincronizar(self, camara: Camara):
        """Reinicia el lector con los datos nuevos, o lo detiene si ya no está activa."""
        self._detener(camara.id)
        if camara.activa:
            self._arrancar(self._cfg(camara))

    def estado(self, camara_id: int) -> Optional[dict]:
        lector = self._lectores.get(camara_id)
        return lector.estado() if lector else None

    def ultimo_frame(self, camara_id: int) -> Optional[bytes]:
        lector = self._lectores.get(camara_id)
        return lector.ultimo_frame() if lector else None

    def detener_todas(self):
        with self._lock:
            lectores = list(self._lectores.values())
            self._lectores.clear()
        for lector in lectores:
            lector.parar()
        for lector in lectores:
            lector.join(timeout=5)

    def _arrancar(self, cfg: CamaraCfg):
        lector = LectorCamara(cfg, *self._args)
        with self._lock:
            self._lectores[cfg.id] = lector
        lector.start()

    def _detener(self, camara_id: int):
        with self._lock:
            lector = self._lectores.pop(camara_id, None)
        if lector:
            lector.parar()
            lector.join(timeout=5)