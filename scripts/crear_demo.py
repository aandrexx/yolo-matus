from sqlalchemy import select

from app.db import SessionLocal, crear_tablas
from app.models import Camara

DEMO = [
    ("Cámara fuego", "videos/fyh10s.mp4"),
    ("Cámara oficina", "videos/personas.mp4"),
]

crear_tablas()
with SessionLocal() as db:
    for nombre, url in DEMO:
        if db.scalar(select(Camara).where(Camara.nombre == nombre)) is None:
            db.add(Camara(nombre=nombre, url=url))
    db.commit()
print("Cámaras de demo listas")