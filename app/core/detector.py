import threading
from dataclasses import dataclass
from typing import Optional

from ultralytics import YOLO


@dataclass
class Deteccion:
    clase: str
    confianza: float
    caja: tuple  # x1, y1, x2, y2


class Detector:
    def __init__(self, ruta_modelo: str, conf: float = 0.3, imgsz: int = 960):
        self.model = YOLO(ruta_modelo)
        self.conf = conf
        self.imgsz = imgsz
        self._lock = threading.Lock()   # un fotograma a la vez, aunque haya varias cámaras

    def detectar(self, frame, conf: Optional[float] = None) -> list[Deteccion]:
        with self._lock:
            r = self.model.predict(
                frame,
                conf=self.conf if conf is None else conf,
                imgsz=self.imgsz,
                verbose=False,
            )[0]
        return [
            Deteccion(r.names[int(b.cls)], float(b.conf), tuple(b.xyxy[0].tolist()))
            for b in r.boxes
        ]