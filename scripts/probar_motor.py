from app.core.motor_alertas import MotorAlertas


def correr(motor, tramos, fps=5):
    """tramos = [(segundos, hay_deteccion), ...]; devuelve los segundos de cada alerta."""
    alertas, t = [], 0.0
    for segundos, hay in tramos:
        for _ in range(int(segundos * fps)):
            if motor.evaluar([object()] if hay else [], t):
                alertas.append(round(t, 1))
            t += 1 / fps
    return alertas


print("60 s continuos:                 ", correr(MotorAlertas(15, 5, 10), [(60, True)]))
print("20 s, pausa 15 s, 20 s:         ", correr(MotorAlertas(15, 5, 10), [(20, True), (15, False), (20, True)]))
print("20 s, pausa 5 s, 20 s:          ", correr(MotorAlertas(15, 5, 10), [(20, True), (5, False), (20, True)]))