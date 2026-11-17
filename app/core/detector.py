import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event
from typing import Optional

from ultralytics import YOLO


@dataclass
class Deteccion:
    clase: str
    confianza: float
    caja: tuple  # x1, y1, x2, y2


class Detector:
    def __init__(self, ruta_modelo: str, conf: float = 0.3, imgsz: int = 960,
                 workers: Optional[int] = None):
        self.conf = conf
        self.imgsz = imgsz

        # Cada instancia procesa una inferencia a la vez; el pool permite
        # ejecutar varias cámaras en paralelo sin compartir estado del modelo.
        default_workers = max(1, min(8, os.cpu_count() or 1))
        if workers is not None and workers < 1:
            raise ValueError("workers debe ser al menos 1")
        self.workers = default_workers if workers is None else workers
        self._modelos = [YOLO(ruta_modelo) for _ in range(self.workers)]
        self.model = self._modelos[0]
        self._modelos_disponibles = Queue(maxsize=self.workers)
        for modelo in self._modelos:
            self._modelos_disponibles.put(modelo)
        self._executor = ThreadPoolExecutor(
            max_workers=self.workers,
            thread_name_prefix="yolo",
        )
        self._inferencias_disponibles = threading.BoundedSemaphore(self.workers)

    def detectar_async(self, frame, conf: Optional[float] = None,
                       cancelar: Optional[Event] = None) -> Optional[Future[list[Deteccion]]]:
        if not self._inferencias_disponibles.acquire(blocking=False):
            return None
        try:
            future = self._executor.submit(
                self.detectar,
                frame.copy(),
                conf,
                cancelar,
            )
        except Exception:
            self._inferencias_disponibles.release()
            raise
        future.add_done_callback(lambda _: self._inferencias_disponibles.release())
        return future

    def cerrar(self):
        self._executor.shutdown(wait=True, cancel_futures=True)

    def detectar(self, frame, conf: Optional[float] = None,
                 cancelar: Optional[Event] = None) -> list[Deteccion]:
        while True:
            if cancelar is not None and cancelar.is_set():
                return []
            try:
                modelo = self._modelos_disponibles.get(timeout=0.1)
                break
            except Empty:
                continue

        try:
            r = modelo.predict(
                frame,
                conf=self.conf if conf is None else conf,
                imgsz=self.imgsz,
                verbose=False,
            )[0]
        finally:
            self._modelos_disponibles.put(modelo)
        return [
            Deteccion(r.names[int(b.cls)], float(b.conf), tuple(b.xyxy[0].tolist()))
            for b in r.boxes
        ]