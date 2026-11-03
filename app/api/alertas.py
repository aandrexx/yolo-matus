import os
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alerta, EstadoAlerta
from app.schemas import AlertaActualizar, AlertaSalida

router = APIRouter(prefix="/alertas", tags=["Alertas"])
DB = Annotated[Session, Depends(get_db)]


def _obtener(db: Session, alerta_id: int) -> Alerta:
    alerta = db.get(Alerta, alerta_id)
    if alerta is None:
        raise HTTPException(404, "Alerta no encontrada")
    return alerta


@router.get("", response_model=list[AlertaSalida])
def listar(
    db: DB,
    estado: Optional[EstadoAlerta] = None,
    camara_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    consulta = select(Alerta).order_by(Alerta.fecha.desc(), Alerta.id.desc())
    if estado is not None:
        consulta = consulta.where(Alerta.estado == estado)
    if camara_id is not None:
        consulta = consulta.where(Alerta.camara_id == camara_id)
    return db.scalars(consulta.limit(limit).offset(offset)).all()


@router.get("/{alerta_id}", response_model=AlertaSalida)
def obtener(alerta_id: int, db: DB):
    return _obtener(db, alerta_id)


@router.patch("/{alerta_id}", response_model=AlertaSalida)
def actualizar(alerta_id: int, datos: AlertaActualizar, db: DB):
    alerta = _obtener(db, alerta_id)
    cambios = datos.model_dump(exclude_unset=True)

    if cambios.get("estado") is not None:
        alerta.estado = cambios["estado"]
        alerta.revisada_en = (
            None if alerta.estado == EstadoAlerta.nueva else datetime.now(timezone.utc)
        )
    if "notas" in cambios:
        alerta.notas = cambios["notas"]

    db.commit()
    db.refresh(alerta)
    return alerta


@router.get("/{alerta_id}/imagen")
def imagen(alerta_id: int, db: DB):
    alerta = _obtener(db, alerta_id)
    if not alerta.imagen_ruta or not os.path.isfile(alerta.imagen_ruta):
        raise HTTPException(404, "La alerta no tiene imagen")
    return FileResponse(alerta.imagen_ruta, media_type="image/jpeg")