import unittest

from app.core.detector import Deteccion
from app.core.lector_camara import filtrar_detecciones_objetivo


class FiltrarDeteccionesObjetivoTests(unittest.TestCase):
    def test_only_fire_and_smoke_above_their_thresholds_are_kept(self):
        detecciones = [
            Deteccion("donut", 0.99, (0, 0, 10, 10)),
            Deteccion("fire hydrant", 0.95, (0, 0, 10, 10)),
            Deteccion("fire", 0.39, (0, 0, 10, 10)),
            Deteccion("FIRE", 0.8, (0, 0, 10, 10)),
            Deteccion("Smoke", 0.6, (0, 0, 10, 10)),
        ]

        result = filtrar_detecciones_objetivo(
            detecciones,
            conf_humo=0.5,
            conf_fuego=0.4,
        )

        self.assertEqual([deteccion.clase for deteccion in result], ["FIRE", "Smoke"])


if __name__ == "__main__":
    unittest.main()
