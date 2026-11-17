from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.gestor_camaras import GestorCamaras
from app.core.lector_camara import EstadoCamara
from app.db import get_db
from app.models import Camara
from app.schemas import (CamaraActualizar, CamaraCrear, CamaraSalida,
                         EstadoCamaraSalida)

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