import os
from datetime import datetime, timezone

import cv2

from app.core.anotador import dibujar_detecciones
from app.db import SessionLocal
from app.models import Alerta
from app.services.notificador import Notificador


class AlertaService:
    def __init__(self, notificador: Notificador,
                 carpeta_evidencias: str = "evidencias",
                 modelo_version: str | None = None):
        self.notificador = notificador
        self.carpeta = carpeta_evidencias
        self.modelo_version = modelo_version

    def registrar(self, camara_id: int, frame, detecciones) -> int | None:
        """Guarda la imagen y el registro de una alerta. Devuelve el id."""
        if not detecciones:
            return None
        principal = max(detecciones, key=lambda d: d.confianza)
        ruta = self._guardar_imagen(camara_id, frame, detecciones)

        with SessionLocal() as db:
            alerta = Alerta(
                camara_id=camara_id,
                clase=principal.clase,
                confianza=principal.confianza,
                imagen_ruta=ruta,
                modelo_version=self.modelo_version,
            )
            db.add(alerta)
            db.commit()
            db.refresh(alerta)
            try:
                self.notificador.notificar(alerta)
            except Exception as e:
                # si falla el aviso, la alerta ya quedó guardada
                print(f"No se pudo notificar la alerta {alerta.id}: {e}")
            return alerta.id

    def _guardar_imagen(self, camara_id, frame, detecciones) -> str | None:
        os.makedirs(self.carpeta, exist_ok=True)
        marca = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        ruta = os.path.join(self.carpeta, f"cam{camara_id}_{marca}.jpg")
        ok = cv2.imwrite(ruta, dibujar_detecciones(frame, detecciones))
        return ruta if ok else None