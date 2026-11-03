import cv2


def dibujar_detecciones(frame, detecciones):
    """Devuelve una copia del fotograma con las cajas dibujadas."""
    img = frame.copy()
    for d in detecciones:
        x1, y1, x2, y2 = map(int, d.caja)
        color = (0, 0, 255) if d.clase == "fire" else (255, 255, 0)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, f"{d.clase} {d.confianza:.2f}", (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return img