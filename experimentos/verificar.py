from ultralytics import YOLO

m = YOLO("friend2.pt")
print("Clases:", m.names)

ck = m.ckpt
args = ck.get("train_args", {})
print("Modelo base :", args.get("model"))
print("Dataset     :", args.get("data"))
print("Épocas pedidas:", args.get("epochs"), "| imgsz:", args.get("imgsz"))
print("Nombre del entrenamiento:", args.get("name"))
print("Época guardada:", ck.get("epoch"))
print("Métricas guardadas:", ck.get("train_metrics"))