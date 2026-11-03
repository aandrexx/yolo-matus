from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal, crear_tablas
from app.models import Alerta, Camara, EstadoAlerta

crear_tablas()

with SessionLocal() as db:
    # Crear la cámara solo si no existe (así puedes correr el script varias veces)
    cam = db.scalar(select(Camara).where(Camara.nombre == "Cámara de prueba"))
    if cam is None:
        cam = Camara(nombre="Cámara de prueba", url="videos/fyh10s.mp4")
        db.add(cam)
        db.commit()
        db.refresh(cam)
    print("Cámara:", cam.id, cam.nombre, cam.url, "activa:", cam.activa)

    # Crear una alerta
    alerta = Alerta(
        camara_id=cam.id,
        clase="fire",
        confianza=0.65,
        imagen_ruta="evidencias/prueba.jpg",
        modelo_version="yolo11s_roboflow",
    )
    db.add(alerta)
    db.commit()
    db.refresh(alerta)
    print("Alerta:", alerta.id, alerta.clase, alerta.confianza, alerta.estado.value)

    # Cambiarle el estado, como haría el operador
    alerta.estado = EstadoAlerta.falsa_alarma
    alerta.notas = "Prueba"
    alerta.revisada_en = datetime.now(timezone.utc)
    db.commit()

    # Consultar
    nuevas = db.scalars(select(Alerta).where(Alerta.estado == EstadoAlerta.nueva)).all()
    falsas = db.scalars(select(Alerta).where(Alerta.estado == EstadoAlerta.falsa_alarma)).all()
    print(f"Nuevas: {len(nuevas)} | Falsas alarmas: {len(falsas)}")
    print("Alertas de la cámara:", [a.id for a in cam.alertas])

    # Probar que la clave foránea se respeta (debe fallar)
    try:
        db.add(Alerta(camara_id=9999, clase="smoke", confianza=0.5))
        db.commit()
        print("ERROR: aceptó una alerta de una cámara que no existe")
    except Exception as e:
        db.rollback()
        print("Clave foránea OK (rechazó la cámara inexistente):", type(e).__name__)