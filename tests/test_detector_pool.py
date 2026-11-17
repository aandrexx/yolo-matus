import threading
import time
import unittest
from unittest.mock import patch

import numpy as np

import app.core.detector as detector_module


class FakeBox:
    def __init__(self):
        self.cls = 0
        self.conf = 0.91
        self.xyxy = [np.array([10, 20, 100, 200], dtype=float)]


class FakeResult:
    names = {0: "smoke"}
    boxes = [FakeBox()]


class FakeYOLO:
    created = []
    lock = threading.Lock()
    active = 0
    max_active = 0

    def __init__(self, ruta_modelo):
        self.ruta_modelo = ruta_modelo
        self.predict_calls = 0
        self.active_calls = 0
        self.max_active_calls = 0
        FakeYOLO.created.append(self)

    def predict(self, frame, conf=None, imgsz=None, verbose=False):
        with FakeYOLO.lock:
            FakeYOLO.active += 1
            FakeYOLO.max_active = max(FakeYOLO.max_active, FakeYOLO.active)
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        time.sleep(0.02)
        self.predict_calls += 1
        with FakeYOLO.lock:
            FakeYOLO.active -= 1
            self.active_calls -= 1
        return [FakeResult()]


class DetectorPoolTests(unittest.TestCase):
    def setUp(self):
        FakeYOLO.created.clear()
        FakeYOLO.active = 0
        FakeYOLO.max_active = 0

    def test_detector_creates_pool_and_detects(self):
        with patch.object(detector_module, "YOLO", FakeYOLO):
            detector = detector_module.Detector("fake-model.pt", workers=3)
            detecciones = detector.detectar(
                np.zeros((480, 640, 3), dtype=np.uint8)
            )

        self.assertEqual(detector.workers, 3)
        self.assertEqual(len(FakeYOLO.created), 3)
        self.assertEqual(detecciones[0].clase, "smoke")
        self.assertEqual(detecciones[0].confianza, 0.91)

    def test_each_model_is_used_by_only_one_call_at_a_time(self):
        with patch.object(detector_module, "YOLO", FakeYOLO):
            detector = detector_module.Detector("fake-model.pt", workers=2)
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            threads = [
                threading.Thread(target=detector.detectar, args=(frame,))
                for _ in range(6)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(sum(m.predict_calls for m in FakeYOLO.created), 6)
        self.assertLessEqual(FakeYOLO.max_active, 2)
        self.assertTrue(all(m.max_active_calls == 1 for m in FakeYOLO.created))

    def test_cancelled_camera_does_not_wait_for_a_model(self):
        cancelar = threading.Event()
        cancelar.set()
        with patch.object(detector_module, "YOLO", FakeYOLO):
            detector = detector_module.Detector("fake-model.pt", workers=1)
            detecciones = detector.detectar(
                np.zeros((64, 64, 3), dtype=np.uint8),
                cancelar=cancelar,
            )

        self.assertEqual(detecciones, [])
        self.assertEqual(FakeYOLO.created[0].predict_calls, 0)


if __name__ == "__main__":
    unittest.main()
