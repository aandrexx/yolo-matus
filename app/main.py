import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import alertas, camaras
from app.config import config
from app.core.detector import Detector
from app.core.gestor_camaras import GestorCamaras
from app.db import crear_tablas
from app.services.alerta_service import AlertaService
from app.services.notificador import NotificadorConsola

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_tablas()
    os.makedirs(config.evidencias, exist_ok=True)

    # el modelo se carga una sola vez y lo comparten todas las cámaras
    detector = Detector(config.modelo.ruta, conf=config.modelo.conf, imgsz=config.modelo.imgsz)
    version = os.path.splitext(os.path.basename(config.modelo.ruta))[0]
    servicio = AlertaService(NotificadorConsola(), config.evidencias, version)

    gestor = GestorCamaras(
        detector, servicio,
        config.motor.ventana, config.motor.minimo, config.motor.cierre_seg,
        config.camaras.fps_proceso,
    )
    app.state.gestor = gestor
    gestor.iniciar_activas()
    yield
    gestor.detener_todas()


app = FastAPI(title="Detección de fuego y humo", version="0.5.0", lifespan=lifespan)
app.include_router(camaras.router)
app.include_router(alertas.router)


@app.get("/salud", tags=["Sistema"])
def salud():
    return {"estado": "ok"}


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "web", html=True),
    name="web",
)