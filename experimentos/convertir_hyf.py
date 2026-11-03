from datasets import load_dataset
from pathlib import Path

ds = load_dataset("hiennguyen9874/Robotoflow-FireAndSmokeDataset", split="train")
print(ds.features)                       # confirma los nombres de las columnas
print("Total de imágenes:", len(ds))

ds = ds.shuffle(seed=42).select(range(300))   # muestra de 300 al azar

COLUMNA = "objects"

# 1) qué categorías existen en la muestra
cats = {}
for ej in ds:
    for c in ej[COLUMNA]["category"]:
        cats[c] = cats.get(c, 0) + 1
print("Categorías en la muestra:", cats)

# 2) convertir a formato YOLO (solo fire y smoke)
MAPA = {"fire": 0, "smoke": 1}
OUT = Path("hf_yolo")
(OUT / "images").mkdir(parents=True, exist_ok=True)
(OUT / "labels").mkdir(parents=True, exist_ok=True)

for i, ej in enumerate(ds):
    img = ej["image"].convert("RGB")
    w, h = img.size
    objs = ej[COLUMNA]
    lineas = []
    for (x, y, bw, bh), cat in zip(objs["bbox"], objs["category"]):
        if cat not in MAPA:
            continue
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + bw, w), min(y + bh, h)
        if x2 <= x1 or y2 <= y1:
            continue
        cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
        lineas.append(f"{MAPA[cat]} {cx:.6f} {cy:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}")
    nombre = f"hf_{i:06d}"
    img.save(OUT / "images" / f"{nombre}.jpg")
    (OUT / "labels" / f"{nombre}.txt").write_text("\n".join(lineas))

print("Listo:", len(ds), "imágenes convertidas en la carpeta", OUT)