from ultralytics import YOLO

model = YOLO("yolo11n.pt")  # se descarga solo la primera vez
#Para probar con la webcam, cambia source="video.mp4" por source=0.
model.predict(source="fuego.mp4", show=True, conf=0.4)