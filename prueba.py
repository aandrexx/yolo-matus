import argparse
import time
from collections import deque
from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
CLASES_OBJETIVO = {"fire", "smoke"}


def main():
    parser = argparse.ArgumentParser(description="Prueba YOLO con un video o cámara.")
    parser.add_argument("--video", default=str(ROOT / "videos" / "0"))
    parser.add_argument("--modelo", default=str(ROOT / "modelos" / "best.pt"))
    parser.add_argument("--conf", type=float, default=0.3)
    parser.add_argument("--imgsz", type=int, default=960)
    args = parser.parse_args()

    ruta_modelo = Path(args.modelo).expanduser().resolve()
    if not ruta_modelo.is_file():
        parser.error(f"No existe el modelo: {ruta_modelo}")

    model = YOLO(str(ruta_modelo))
    nombres = model.names
    ids_objetivo = [
        int(class_id)
        for class_id, nombre in nombres.items()
        if str(nombre).strip().casefold() in CLASES_OBJETIVO
    ]
    if not ids_objetivo:
        parser.error(
            f"El modelo no contiene las clases fire/smoke. Clases disponibles: {nombres}"
        )

    fuente = 0 if args.video == "0" else str(Path(args.video).expanduser().resolve())
    if isinstance(fuente, str) and not Path(fuente).is_file():
        parser.error(f"No existe el video: {fuente}")

    cap = cv2.VideoCapture(fuente)
    if not cap.isOpened():
        cap.release()
        parser.error(f"No se pudo abrir la fuente de video: {fuente}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    historial = deque(maxlen=15)
    cv2.namedWindow("Deteccion de fuego y humo", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Deteccion de fuego y humo", 960, 540)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            inicio = time.perf_counter()
            resultado = model.predict(
                frame,
                conf=args.conf,
                imgsz=args.imgsz,
                classes=ids_objetivo,
                verbose=False,
            )[0]
            historial.append(bool(resultado.boxes))

            anotado = resultado.plot()
            if sum(historial) >= 5:
                cv2.putText(
                    anotado,
                    "ALERTA: FUEGO/HUMO",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    3,
                )

            cv2.imshow("Deteccion de fuego y humo", anotado)
            espera_ms = max(1, round(1000 / fps - (time.perf_counter() - inicio) * 1000))
            if cv2.waitKey(espera_ms) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
