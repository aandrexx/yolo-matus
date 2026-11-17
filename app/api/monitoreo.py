from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.gestor_camaras import GestorCamaras
from app.core.lector_camara import EstadoCamara
from app.db import get_db
from app.models import Alerta, Camara, EstadoAlerta
from app.schemas import AlertaReciente, ResumenMonitoreo

router = APIRouter(prefix="/monitoreo", tags=["Monitoreo"])
DB = Annotated[Session, Depends(get_db)]


def get_gestor(request: Request) -> GestorCamaras:
    return request.app.state.gestor


Gestor = Annotated[GestorCamaras, Depends(get_gestor)]


@router.get("/resumen", response_model=ResumenMonitoreo)
def resumen(db: DB, gestor: Gestor):
    camaras = db.scalars(select(Camara)).all()
    estados_camara = {
        estado.value: 0
        for estado in EstadoCamara
    }
    estados_camara["total"] = len(camaras)
    estados_camara["activas"] = sum(camara.activa for camara in camaras)

    for camara in camaras:
        datos = gestor.estado(camara.id)
        estado = datos["estado"] if datos else EstadoCamara.inactiva
        estados_camara[estado.value] += 1

    conteos_alerta = {
        estado.value: 0
        for estado in EstadoAlerta
    }
    for estado, cantidad in db.execute(
        select(Alerta.estado, func.count(Alerta.id)).group_by(Alerta.estado)
    ):
        conteos_alerta[estado.value] = cantidad
    conteos_alerta["total"] = sum(conteos_alerta.values())

    recientes = db.execute(
        select(Alerta, Camara.nombre)
        .join(Camara, Camara.id == Alerta.camara_id)
        .order_by(Alerta.fecha.desc(), Alerta.id.desc())
        .limit(8)
    ).all()
    ultimas_alertas = [
        AlertaReciente(
            id=alerta.id,
            camara_id=alerta.camara_id,
            clase=alerta.clase,
            confianza=alerta.confianza,
            fecha=alerta.fecha,
            estado=alerta.estado,
            notas=alerta.notas,
            revisada_en=alerta.revisada_en,
            modelo_version=alerta.modelo_version,
            imagen_ruta=alerta.imagen_ruta,
            camara_nombre=nombre,
        )
        for alerta, nombre in recientes
    ]

    return ResumenMonitoreo(
        camaras=estados_camara,
        alertas=conteos_alerta,
        ultimas_alertas=ultimas_alertas,
    )
