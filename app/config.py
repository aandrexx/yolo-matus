import yaml
from pydantic import BaseModel


class ModeloCfg(BaseModel):
    ruta: str
    conf: float = 0.3
    imgsz: int = 960


class MotorCfg(BaseModel):
    ventana: int = 15
    minimo: int = 5
    cierre_seg: float = 30


class CamarasCfg(BaseModel):
    fps_proceso: float = 2


class Config(BaseModel):
    modelo: ModeloCfg
    motor: MotorCfg
    camaras: CamarasCfg = CamarasCfg()
    evidencias: str = "evidencias"


def cargar_config(ruta: str = "config.yaml") -> Config:
    with open(ruta, encoding="utf-8") as f:
        return Config(**yaml.safe_load(f))


config = cargar_config()