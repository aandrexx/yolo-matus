import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.monitoreo import resumen
from app.core.lector_camara import EstadoCamara
from app.db import Base
from app.models import Alerta, Camara, EstadoAlerta


class FakeGestor:
    def __init__(self, estados):
        self.estados = estados

    def estado(self, camara_id):
        return self.estados.get(camara_id)


class MonitoreoTests(unittest.TestCase):
    def test_summary_counts_camera_and_alert_states(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([
                Camara(id=1, nombre="Entrada", url="0", activa=True),
                Camara(id=2, nombre="Patio", url="1", activa=False),
            ])
            db.flush()
            db.add(Alerta(
                camara_id=1,
                clase="fire",
                confianza=0.93,
                estado=EstadoAlerta.nueva,
                imagen_ruta="evidencias/fuego.jpg",
            ))
            db.commit()

            result = resumen(db, FakeGestor({
                1: {"estado": EstadoCamara.alerta},
            }))

        self.assertEqual(result.camaras["total"], 2)
        self.assertEqual(result.camaras["activas"], 1)
        self.assertEqual(result.camaras["alerta"], 1)
        self.assertEqual(result.camaras["inactiva"], 1)
        self.assertEqual(result.alertas["nueva"], 1)
        self.assertEqual(result.alertas["total"], 1)
        self.assertEqual(result.ultimas_alertas[0].camara_nombre, "Entrada")
        self.assertEqual(result.ultimas_alertas[0].imagen_url, "/alertas/1/imagen")


if __name__ == "__main__":
    unittest.main()
