from collections import deque


class MotorAlertas:
    """Dispara UNA alerta por evento. Un evento termina cuando pasan
    `cierre_seg` segundos sin ninguna detección."""

    def __init__(self, ventana=15, minimo=5, cierre_seg=10):
        self.historial = deque(maxlen=ventana)
        self.minimo = minimo
        self.cierre_seg = cierre_seg
        self.evento_activo = False
        self.ultima_deteccion = None

    def evaluar(self, detecciones, t: float) -> bool:
        """t = tiempo en segundos (del video o del reloj real).
        Devuelve True solo cuando empieza un evento nuevo."""
        if detecciones:
            self.ultima_deteccion = t

        # cerrar el evento si lleva cierre_seg sin detecciones
        if self.evento_activo and t - self.ultima_deteccion >= self.cierre_seg:
            self.evento_activo = False
            self.historial.clear()   # el próximo evento debe volver a ganarse la alerta

        self.historial.append(1 if detecciones else 0)

        if not self.evento_activo and sum(self.historial) >= self.minimo:
            self.evento_activo = True
            return True
        return False