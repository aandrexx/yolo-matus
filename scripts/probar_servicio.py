import argparse
import os
import sys

import cv2
from sqlalchemy import select

from app.core.detector import Detector
from app.core.motor_alertas import MotorAlertas
from app.db import SessionLocal, crear_tablas
from app.models import Alerta, Camara
from app.services.alerta_service import AlertaService
from app.services.notificador import NotificadorConsola

FPS_OBJETIVO = 5


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("modelo")
    p.add_argument("--ventana", type=int, default=15)
    p.add_argument("--minimo", type=int, default=5)
    p.add_argument("--cierre", type=float, default=10)
    a = p.parse_args()

    crear_tablas()
    with SessionLocal() as db:
        cam = db.scalar(select(Camara).where(Camara.nombre == "Cámara de prueba"))
        if cam is None:
            cam = Camara(nombre="Cámara de prueba", url=a.video)
            db.add(cam)
            db.commit()
            db.refresh(cam)
        camara_id = cam.id

    version = os.path.splitext(os.path.basename(a.modelo))[0]
    detector = Detector(a.modelo, conf=0.3, imgsz=960)
    motor = MotorAlertas(a.ventana, a.minimo, a.cierre)
    servicio = AlertaService(NotificadorConsola(), modelo_version=version)

    cap = cv2.VideoCapture(a.video)
    if not cap.isOpened():
        sys.exit(f"No se pudo abrir el video: {a.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    salto = max(1, round(fps / FPS_OBJETIVO))

    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % salto == 0:
            t = i / fps
            dets = detector.detectar(frame)
            if motor.evaluar(dets, t):
                print(f"-> evento nuevo en el segundo {t:.1f}")
                servicio.registrar(camara_id, frame, dets)
        i += 1
    cap.release()

    with SessionLocal() as db:
        total = db.scalars(select(Alerta).where(Alerta.camara_id == camara_id)).all()
        print(f"\nAlertas guardadas para esta cámara (acumuladas): {len(total)}")


if __name__ == "__main__":
    main()