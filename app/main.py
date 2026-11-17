import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import alertas, camaras, monitoreo
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

    # se carga un pool de instancias del modelo para repartir la inferencia
    # entre varias cámaras sin bloquear todas las detecciones en un solo hilo
    detector = Detector(
        config.modelo.ruta,
        conf=config.modelo.conf,
        imgsz=config.modelo.imgsz,
        workers=config.modelo.workers,
    )
    clases_modelo = {str(clase).strip().casefold() for clase in detector.model.names.values()}
    clases_objetivo = {"fire", "smoke"}
    if not clases_objetivo.issubset(clases_modelo):
        log.warning(
            "El modelo '%s' no tiene las clases fire y smoke. Clases disponibles: %s. "
            "Configura un checkpoint entrenado para fuego y humo.",
            config.modelo.ruta,
            ", ".join(sorted(clases_modelo)),
        )
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
app.include_router(monitoreo.router)


@app.get("/salud", tags=["Sistema"])
def salud():
    return {"estado": "ok"}


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "web", html=True),
    name="web",
)