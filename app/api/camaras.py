import asyncio
import mimetypes
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.gestor_camaras import GestorCamaras
from app.core.lector_camara import EstadoCamara
from app.core.webrtc import CamaraVideoTrack
from app.db import get_db
from app.models import Camara
from app.schemas import (CamaraActualizar, CamaraCrear, CamaraSalida,
                         EstadoCamaraSalida, OfertaWebRTC)

router = APIRouter(prefix="/camaras", tags=["Cámaras"])


def get_gestor(request: Request) -> GestorCamaras:
    return request.app.state.gestor


DB = Annotated[Session, Depends(get_db)]
Gestor = Annotated[GestorCamaras, Depends(get_gestor)]


def _obtener(db: Session, camara_id: int) -> Camara:
    camara = db.get(Camara, camara_id)
    if camara is None:
        raise HTTPException(404, "Cámara no encontrada")
    return camara


def _nombre_en_uso(db: Session, nombre: str, excluir_id: int | None = None) -> bool:
    consulta = select(Camara).where(Camara.nombre == nombre)
    if excluir_id is not None:
        consulta = consulta.where(Camara.id != excluir_id)
    return db.scalar(consulta) is not None


def _estado(camara: Camara, gestor: GestorCamaras) -> EstadoCamaraSalida:
    datos = gestor.estado(camara.id)
    if datos is None:   # sin lector: la cámara está desactivada
        return EstadoCamaraSalida(camara_id=camara.id, nombre=camara.nombre,
                                  estado=EstadoCamara.inactiva)
    return EstadoCamaraSalida(camara_id=camara.id, nombre=camara.nombre, **datos)


@router.get("", response_model=list[CamaraSalida])
def listar(db: DB):
    return db.scalars(select(Camara).order_by(Camara.id)).all()


# Debe ir ANTES de "/{camara_id}", si no FastAPI intentaría leer "estado" como un id
@router.get("/estado", response_model=list[EstadoCamaraSalida])
def estado_todas(db: DB, gestor: Gestor):
    camaras = db.scalars(select(Camara).order_by(Camara.id)).all()
    return [_estado(c, gestor) for c in camaras]


@router.post("", response_model=CamaraSalida, status_code=201)
def crear(datos: CamaraCrear, db: DB, gestor: Gestor):
    if _nombre_en_uso(db, datos.nombre):
        raise HTTPException(409, "Ya existe una cámara con ese nombre")
    camara = Camara(**datos.model_dump())
    db.add(camara)
    db.commit()
    db.refresh(camara)
    gestor.sincronizar(camara)
    return camara


@router.get("/{camara_id}", response_model=CamaraSalida)
def obtener(camara_id: int, db: DB):
    return _obtener(db, camara_id)


@router.get("/{camara_id}/video")
def video_archivo(camara_id: int, db: DB):
    camara = _obtener(db, camara_id)
    if camara.url.isdigit() or "://" in camara.url:
        raise HTTPException(415, "La fuente no es un archivo de video local")

    ruta = Path(camara.url).expanduser().resolve()
    if not ruta.is_file():
        raise HTTPException(404, "No se encontró el archivo de video")
    tipo, _ = mimetypes.guess_type(ruta.name)
    if tipo is None or not tipo.startswith("video/"):
        raise HTTPException(415, "El archivo no tiene un formato de video reconocido")
    return FileResponse(ruta, media_type=tipo)


@router.patch("/{camara_id}", response_model=CamaraSalida)
def actualizar(camara_id: int, datos: CamaraActualizar, db: DB, gestor: Gestor):
    camara = _obtener(db, camara_id)
    cambios = datos.model_dump(exclude_unset=True)

    nuevo_nombre = cambios.get("nombre")
    if nuevo_nombre and _nombre_en_uso(db, nuevo_nombre, excluir_id=camara.id):
        raise HTTPException(409, "Ya existe una cámara con ese nombre")

    for campo, valor in cambios.items():
        if valor is not None:   # un null no borra campos obligatorios
            setattr(camara, campo, valor)
    db.commit()
    db.refresh(camara)
    gestor.sincronizar(camara)   # aplica la URL, los umbrales o el on/off sin reiniciar el servidor
    return camara


@router.delete("/{camara_id}", status_code=204)
def eliminar(camara_id: int, db: DB, gestor: Gestor):
    camara = _obtener(db, camara_id)
    gestor.eliminar(camara.id)
    db.delete(camara)
    db.commit()
    return Response(status_code=204)


@router.get("/{camara_id}/estado", response_model=EstadoCamaraSalida)
def estado(camara_id: int, db: DB, gestor: Gestor):
    return _estado(_obtener(db, camara_id), gestor)


@router.get("/{camara_id}/ultimo-frame")
def ultimo_frame(camara_id: int, db: DB, gestor: Gestor):
    _obtener(db, camara_id)
    jpg = gestor.ultimo_frame(camara_id)
    if jpg is None:
        raise HTTPException(404, "Todavía no hay fotogramas de esta cámara")
    return Response(content=jpg, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@router.get("/{camara_id}/detecciones")
def detecciones(camara_id: int, db: DB, gestor: Gestor):
    _obtener(db, camara_id)
    return gestor.detecciones(camara_id)


@router.post("/{camara_id}/webrtc")
async def crear_sesion_webrtc(
    camara_id: int, oferta: OfertaWebRTC, request: Request, db: DB,
    gestor: Gestor,
):
    camara = _obtener(db, camara_id)
    if not camara.activa:
        raise HTTPException(409, "La cámara está pausada")

    conexiones = request.app.state.webrtc_connections
    session_id = uuid4().hex
    pc = RTCPeerConnection()
    conexiones[session_id] = pc
    pc.addTrack(CamaraVideoTrack(gestor, camara_id))

    @pc.on("connectionstatechange")
    async def limpiar_conexion():
        if pc.connectionState == "failed":
            conexiones.pop(session_id, None)
            await pc.close()
        elif pc.connectionState == "closed":
            conexiones.pop(session_id, None)

    try:
        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=oferta.sdp, type=oferta.type)
        )
        respuesta = await pc.createAnswer()
        await pc.setLocalDescription(respuesta)
    except Exception:
        conexiones.pop(session_id, None)
        await pc.close()
        raise

    return {
        "session_id": session_id,
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }


@router.delete("/{camara_id}/webrtc/{session_id}", status_code=204)
async def cerrar_sesion_webrtc(
    camara_id: int, session_id: str, request: Request, db: DB,
):
    _obtener(db, camara_id)
    pc = request.app.state.webrtc_connections.pop(session_id, None)
    if pc is not None:
        await pc.close()
    return Response(status_code=204)


@router.get("/{camara_id}/stream")
async def stream(camara_id: int, request: Request, db: DB, gestor: Gestor):
    _obtener(db, camara_id)

    async def fotogramas():
        ultima_version = -1
        while not await request.is_disconnected():
            jpg, version = gestor.fotograma(camara_id)
            if jpg is not None and version != ultima_version:
                ultima_version = version
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpg)).encode("ascii") + b"\r\n\r\n"
                    + jpg + b"\r\n"
                )
            await asyncio.sleep(1 / 30)

    return StreamingResponse(
        fotogramas(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )