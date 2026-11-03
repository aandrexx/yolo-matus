import cv2
import numpy as np
from ultralytics import YOLO

VIDEO = "fyh.mp4"             # cambia por el video que quieras probar
MODELO_A = "modelo_anterior.pt"   # izquierda: ANTERIOR
MODELO_B = "yolo26.pt"      # derecha: NUEVO
CONF = 0.30
ANCHO = 640                        # ancho de cada mitad

a = YOLO(MODELO_A)
b = YOLO(MODELO_B)
cap = cv2.VideoCapture(VIDEO)
if not cap.isOpened():
    print(f"No se pudo abrir: {VIDEO}")
    raise SystemExit(1)

def anotar(modelo, frame, titulo):
    r = modelo.predict(frame, conf=CONF, verbose=False)[0]
    img = r.plot()
    h, w = img.shape[:2]
    img = cv2.resize(img, (ANCHO, int(h * ANCHO / w)))
    cv2.putText(img, f"{titulo}: {len(r.boxes)} detecciones", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    return img

cv2.namedWindow("Comparacion", cv2.WINDOW_NORMAL)
while True:
    ok, frame = cap.read()
    if not ok:
        break
    izq = anotar(a, frame.copy(), "ANTERIOR")
    der = anotar(b, frame.copy(), "NUEVO")
    cv2.imshow("Comparacion", np.hstack([izq, der]))
    if cv2.waitKey(1) & 0xFF == ord("q"):
        
        break

cap.release()
cv2.destroyAllWindows()