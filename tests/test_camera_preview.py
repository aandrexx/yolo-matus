import time
import unittest
from concurrent.futures import Future
from unittest.mock import patch

import numpy as np

from app.core.lector_camara import CamaraCfg, LectorCamara


class FakeCapture:
    def __init__(self, source):
        self.frames = 0

    def isOpened(self):
        return True

    def get(self, prop):
        return 30

    def grab(self):
        time.sleep(0.005)
        self.frames += 1
        return True

    def retrieve(self):
        return True, np.full((32, 32, 3), self.frames % 255, dtype=np.uint8)

    def release(self):
        pass


class FakeDetector:
    def detectar_async(self, frame, conf=None, cancelar=None):
        result = Future()
        result.set_result([])
        return result


class CameraPreviewTests(unittest.TestCase):
    def test_preview_keeps_updating_between_inference_frames(self):
        lector = LectorCamara(
            CamaraCfg(1, "Prueba", "0", 0.3, 0.3),
            detector=FakeDetector(),
            servicio=None,
            ventana=15,
            minimo=5,
            cierre_seg=30,
            fps_proceso=1,
            fps_vista=24,
        )

        with patch("app.core.lector_camara.cv2.VideoCapture", FakeCapture):
            lector.start()
            time.sleep(0.5)
            lector.parar()
            lector.join(timeout=1)

        self.assertFalse(lector.is_alive())
        _, version = lector.fotograma()
        procesados = lector.estado()["fotogramas_procesados"]
        self.assertGreaterEqual(version, 8)
        self.assertGreaterEqual(procesados, 1)
        self.assertGreater(version, procesados)


if __name__ == "__main__":
    unittest.main()
