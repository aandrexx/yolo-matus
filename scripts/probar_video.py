import sys
import cv2
from app.core.detector import Detector
from app.core.motor_alertas import MotorAlertas

ruta_video = sys.argv[1]
ruta_modelo = sys.argv[2]

detector = Detector(ruta_modelo, conf=0.3, imgsz=960)
motor = MotorAlertas(ventana=15, minimo=5, espera_seg=30)

cap = cv2.VideoCapture(ruta_video)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
salto = max(1, round(fps / 5))   # procesar ~5 fotogramas por segundo

i = 0
procesados = con_deteccion = 0
alertas = []

while True:
    ok, frame = cap.read()
    if not ok:
        break
    if i % salto == 0:
        t = i / fps
        dets = detector.detectar(frame)
        procesados += 1
        con_deteccion += bool(dets)
        if motor.evaluar(dets, t):
            alertas.append(t)
            print(f"ALERTA en {t:.1f}s: {[(d.clase, round(d.confianza, 2)) for d in dets]}")
    i += 1

cap.release()
print(f"\nFotogramas procesados: {procesados}")
print(f"Con alguna detección: {con_deteccion} ({100*con_deteccion/max(procesados,1):.0f}%)")
print(f"Alertas: {len(alertas)} -> en los segundos {[round(a,1) for a in alertas]}")