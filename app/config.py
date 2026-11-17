import yaml
from pydantic import BaseModel, Field


class ModeloCfg(BaseModel):
    ruta: str
    conf: float = Field(default=0.3, ge=0, le=1)
    imgsz: int = Field(default=960, ge=32)
    workers: int = Field(default=4, ge=1, le=16)


class MotorCfg(BaseModel):
    ventana: int = Field(default=15, ge=1)
    minimo: int = Field(default=5, ge=1)
    cierre_seg: float = Field(default=30, gt=0)


class CamarasCfg(BaseModel):
    fps_proceso: float = Field(default=2, gt=0, le=30)
    fps_vista: float = Field(default=30, gt=0, le=30)


class Config(BaseModel):
    modelo: ModeloCfg
    motor: MotorCfg
    camaras: CamarasCfg = CamarasCfg()
    evidencias: str = "evidencias"


def cargar_config(ruta: str = "config.yaml") -> Config:
    with open(ruta, encoding="utf-8") as f:
        return Config(**yaml.safe_load(f))


config = cargar_config()