from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///datos.db"

# check_same_thread=False porque más adelante varios hilos (uno por cámara) usarán la base
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def activar_foreign_keys(conexion, _):
    # SQLite no hace cumplir las claves foráneas si no se le pide
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def crear_tablas():
    from app import models  # noqa: importar los modelos los registra en Base
    Base.metadata.create_all(bind=engine)


def get_db():
    """La usará FastAPI en la Fase 4 para darle una sesión a cada petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()