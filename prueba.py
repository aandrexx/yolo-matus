import cv2
from collections import deque
from ultralytics import YOLO

model = YOLO("modelo_anterior.pt")
cap = cv2.VideoCapture("fyh.mp4")  # o 0 para la webcam

VENTANA = 15       # fotogramas que se miran hacia atrás
MINIMO = 5         # detecciones necesarias dentro de la ventana
historial = deque(maxlen=VENTANA)
cv2.namedWindow("Deteccion", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Deteccion", 960, 540)
while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break

    resultado = model.predict(frame, conf=0.3, imgsz=960, verbose=False)[0]
    historial.append(1 if len(resultado.boxes) > 0 else 0)

    anotado = resultado.plot()
    if sum(historial) >= MINIMO:
        cv2.putText(anotado, "ALERTA: FUEGO/HUMO", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    cv2.imshow("Deteccion", anotado)    
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()