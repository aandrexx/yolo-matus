import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EstadoAlerta(str, enum.Enum):
    nueva = "nueva"
    confirmada = "confirmada"
    falsa_alarma = "falsa_alarma"


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    camara_id: Mapped[int] = mapped_column(ForeignKey("camaras.id"), index=True)
    clase: Mapped[str] = mapped_column(String(20))          # "fire" o "smoke"
    confianza: Mapped[float]
    fecha: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    imagen_ruta: Mapped[Optional[str]] = mapped_column(String(500))
    estado: Mapped[EstadoAlerta] = mapped_column(
        SAEnum(EstadoAlerta, native_enum=False, length=20),
        default=EstadoAlerta.nueva,
        index=True,
    )
    notas: Mapped[Optional[str]] = mapped_column(Text)
    revisada_en: Mapped[Optional[datetime]]
    modelo_version: Mapped[Optional[str]] = mapped_column(String(100))

    camara: Mapped["Camara"] = relationship(back_populates="alertas")