from abc import ABC, abstractmethod


class Notificador(ABC):
    @abstractmethod
    def notificar(self, alerta) -> None:
        ...


class NotificadorConsola(Notificador):
    def notificar(self, alerta) -> None:
        print(f"[ALERTA #{alerta.id}] {alerta.clase} ({alerta.confianza:.0%}) "
              f"cámara {alerta.camara_id} | {alerta.fecha:%Y-%m-%d %H:%M:%S} | {alerta.imagen_ruta}")