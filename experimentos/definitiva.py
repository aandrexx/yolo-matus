import cv2
from collections import deque
from ultralytics import YOLO

FUENTE = "frascos.mp4"            # un video, 0 para la webcam, o "rtsp://..." para una cámara
MODELO = "modelo_anterior.pt"
CONF = 0.30                   # umbral de confianza
IMGSZ = 960                   # 640 es más rápido, 960 detecta mejor lo pequeño
ROTAR = None                  # cv2.ROTATE_90_CLOCKWISE si el video se ve de lado

# Lógica de alerta: se activa con ENCENDER detecciones en las últimas VENTANA lecturas
VENTANA, ENCENDER, APAGAR = 20, 6, 2
COLOR = {"fire": (0, 0, 255), "smoke": (200, 200, 200)}

model = YOLO(MODELO)
cap = cv2.VideoCapture(FUENTE)
if not cap.isOpened():
    print(f"No se pudo abrir la fuente: {FUENTE}")
    raise SystemExit(1)

historial = {n: deque(maxlen=VENTANA) for n in COLOR}
alerta = {n: False for n in COLOR}

cv2.namedWindow("Deteccion", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Deteccion", 960, 540)

while True:
    ok, frame = cap.read()
    if not ok:
        break
    if ROTAR is not None:
        frame = cv2.rotate(frame, ROTAR)

    r = model.predict(frame, conf=CONF, imgsz=IMGSZ, verbose=False)[0]
    vistos = {model.names[int(b.cls)] for b in r.boxes}
    imagen = r.plot()

    y = 40
    for nombre in COLOR:
        historial[nombre].append(1 if nombre in vistos else 0)
        total = sum(historial[nombre])
        if total >= ENCENDER:
            alerta[nombre] = True
        elif total <= APAGAR:
            alerta[nombre] = False
        if alerta[nombre]:
            cv2.putText(imagen, f"ALERTA: {nombre.upper()}", (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, COLOR[nombre], 3)
            y += 40

    cv2.imshow("Deteccion", imagen)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()