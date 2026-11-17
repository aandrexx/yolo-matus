from datetime import datetime
from typing import Literal, Optional

from app.core.lector_camara import EstadoCamara

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models import EstadoAlerta


# ---------- Cámaras ----------
class CamaraCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=500)
    activa: bool = True
    conf_humo: float = Field(0.3, ge=0, le=1)
    conf_fuego: float = Field(0.3, ge=0, le=1)


class CamaraActualizar(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    activa: Optional[bool] = None
    conf_humo: Optional[float] = Field(None, ge=0, le=1)
    conf_fuego: Optional[float] = Field(None, ge=0, le=1)


class OfertaWebRTC(BaseModel):
    sdp: str
    type: Literal["offer"]


class CamaraSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    url: str
    activa: bool
    conf_humo: float
    conf_fuego: float
    creada_en: datetime


# ---------- Alertas ----------
class AlertaActualizar(BaseModel):
    estado: Optional[EstadoAlerta] = None
    notas: Optional[str] = Field(None, max_length=1000)


class AlertaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camara_id: int
    clase: str
    confianza: float
    fecha: datetime
    estado: EstadoAlerta
    notas: Optional[str] = None
    revisada_en: Optional[datetime] = None
    modelo_version: Optional[str] = None
    # la ruta del disco no se expone; se entrega una URL
    imagen_ruta: Optional[str] = Field(default=None, exclude=True)

    @computed_field
    @property
    def imagen_url(self) -> Optional[str]:
        return f"/alertas/{self.id}/imagen" if self.imagen_ruta else None
    
class EstadoCamaraSalida(BaseModel):
    camara_id: int
    nombre: str
    estado: EstadoCamara
    ultima_actualizacion: Optional[datetime] = None
    ultimo_error: Optional[str] = None
    fotogramas_procesados: int = 0


class AlertaReciente(AlertaSalida):
    camara_nombre: str


class ResumenMonitoreo(BaseModel):
    camaras: dict[str, int]
    alertas: dict[str, int]
    ultimas_alertas: list[AlertaReciente]