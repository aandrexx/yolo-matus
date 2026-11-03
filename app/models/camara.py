from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Camara(Base):
    __tablename__ = "camaras"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    url: Mapped[str] = mapped_column(String(500))  # URL RTSP o ruta de un video de prueba
    activa: Mapped[bool] = mapped_column(default=True)
    conf_humo: Mapped[float] = mapped_column(default=0.3)
    conf_fuego: Mapped[float] = mapped_column(default=0.3)
    creada_en: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    alertas: Mapped[list["Alerta"]] = relationship(
        back_populates="camara", cascade="all, delete-orphan"
    )