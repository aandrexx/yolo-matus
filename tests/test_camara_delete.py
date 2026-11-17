import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.camaras import eliminar
from app.db import Base
from app.models import Alerta, Camara, EstadoAlerta


class FakeGestor:
    def __init__(self):
        self.eliminadas = []

    def eliminar(self, camara_id):
        self.eliminadas.append(camara_id)


class EliminarCamaraTests(unittest.TestCase):
    def test_delete_stops_camera_and_cascades_alerts(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        gestor = FakeGestor()

        with Session(engine) as db:
            camara = Camara(nombre="Entrada", url="0", activa=True)
            db.add(camara)
            db.flush()
            camara_id = camara.id
            db.add(Alerta(
                camara_id=camara_id,
                clase="fire",
                confianza=0.9,
                estado=EstadoAlerta.nueva,
            ))
            db.commit()

            response = eliminar(camara_id, db, gestor)

            self.assertEqual(response.status_code, 204)
            self.assertEqual(gestor.eliminadas, [camara_id])
            self.assertIsNone(db.get(Camara, camara_id))
            self.assertEqual(
                db.scalars(select(Alerta).where(Alerta.camara_id == camara_id)).all(),
                [],
            )


if __name__ == "__main__":
    unittest.main()
