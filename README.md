# Vigía — detección de fuego y humo

Backend y panel web para monitorear fuentes de video y detectar fuego y humo
con un modelo YOLO entrenado. El panel permite administrar cámaras, ver sus
fotogramas y estados, y revisar las alertas guardadas.

## Requisitos

- Windows 10/11 (los comandos de esta guía usan PowerShell).
- Python 3.12 recomendado.
- Cámara web, archivo de video o cámara IP/RTSP accesible desde el equipo.
- El checkpoint `modelos/best.pt` en la carpeta del proyecto. Debe contener
  las clases `fire` y `smoke`; asegúrate de incluirlo al publicar el repo.

El rendimiento depende del hardware, la resolución y la cantidad de cámaras.
El valor inicial procesa hasta 2 fotogramas por segundo por cámara y usa un
pool de 4 instancias YOLO. Aumentar `workers` consume más memoria; mide el
rendimiento con tu equipo antes de conectar muchas cámaras.

## Instalación y ejecución

Abre PowerShell en la carpeta raíz del proyecto:

```powershell
cd D:\yolo-ia\yolo-matus
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abre el panel en <http://127.0.0.1:8000>. La documentación interactiva de la
API está en <http://127.0.0.1:8000/docs> y el chequeo básico del servicio en
<http://127.0.0.1:8000/salud>.

Ejecuta el servidor desde la raíz del proyecto para que encuentre
`config.yaml`, el modelo y la base de datos. Para desarrollo puedes agregar
`--reload` al comando de Uvicorn.

## Configuración

Los valores iniciales están en `config.yaml`:

```yaml
modelo:
  ruta: modelos/best.pt
  conf: 0.3
  imgsz: 960
  workers: 4

motor:
  ventana: 15
  minimo: 5
  cierre_seg: 30

evidencias: evidencias
camaras:
  fps_proceso: 2
```

- `modelo.ruta`: ruta al checkpoint YOLO, relativa a la raíz del repositorio.
  Las clases deben llamarse `fire` y `smoke`; el backend avisa al iniciar si
  el modelo no las contiene y descarta las demás clases.
- `modelo.conf`: confianza predeterminada del modelo.
- `modelo.imgsz`: tamaño de entrada usado por YOLO.
- `modelo.workers`: cantidad de instancias del modelo que pueden inferir en
  paralelo. Cada instancia requiere memoria adicional.
- `camaras.fps_proceso`: máximo de fotogramas analizados por segundo y cámara.
- `motor.ventana` y `motor.minimo`: una alerta inicia cuando se detecta fuego
  o humo en al menos `minimo` de las últimas `ventana` lecturas.
- `motor.cierre_seg`: segundos sin detecciones para cerrar el evento y permitir
  una alerta posterior.
- `evidencias`: carpeta local donde se guardan las imágenes de las alertas.

Reinicia el backend después de cambiar esta configuración.

## Uso del panel

1. Pulsa **Agregar cámara**.
2. Escribe un nombre y una fuente de video:
   - `0` para la primera cámara web disponible.
   - Una URL RTSP, por ejemplo `rtsp://usuario:clave@host:554/ruta`.
   - Una ruta a un archivo de video accesible en ese equipo, por ejemplo
     `D:\videos\incendio.mp4`.
3. Ajusta por separado los umbrales de confianza para humo y fuego.
4. Usa **Pausar/Activar** para detener o iniciar la lectura, y **Eliminar** para
   borrar la cámara y sus registros de alertas asociados.

Las tarjetas muestran el fotograma más reciente, el estado de conexión y las
detecciones actuales. La lista de alertas muestra eventos, no cada fotograma:
se registra una alerta al inicio de un evento sostenido. Actualmente fuego y
humo comparten el ciclo de evento por cámara; la alerta se etiqueta con la
detección de mayor confianza en el fotograma que inicia ese evento.

## API principal

| Método | Ruta | Uso |
| --- | --- | --- |
| `GET` | `/salud` | Comprueba que la API responde. |
| `GET`, `POST` | `/camaras` | Lista o agrega cámaras. |
| `GET`, `PATCH`, `DELETE` | `/camaras/{id}` | Consulta, actualiza o elimina una cámara. |
| `GET` | `/camaras/estado` | Consulta el estado de todas las cámaras. |
| `GET` | `/camaras/{id}/estado` | Consulta el estado de una cámara. |
| `GET` | `/camaras/{id}/ultimo-frame` | Obtiene el fotograma JPEG más reciente. |
| `GET` | `/alertas` | Lista alertas; acepta `estado`, `camara_id`, `limit` y `offset`. |
| `GET`, `PATCH` | `/alertas/{id}` | Consulta o revisa una alerta. |
| `GET` | `/alertas/{id}/imagen` | Obtiene la evidencia JPEG de una alerta. |
| `GET` | `/monitoreo/resumen` | Devuelve conteos y alertas recientes para el panel. |

Estados de cámara: `conectando`, `normal`, `alerta`, `sin_conexion` e
`inactiva`. Estados de alerta: `nueva`, `confirmada` y `falsa_alarma`.

## Pruebas

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas cubren el pool de inferencia, el filtrado de clases de fuego/humo,
el resumen de monitoreo y la eliminación de cámaras.

## Datos locales y despliegue

- `datos.db` se crea localmente al iniciar; no se incluye en el repositorio.
  Una instalación nueva empieza sin cámaras ni alertas, así que hay que
  agregarlas de nuevo.
- Las evidencias se guardan en `evidencias/` y tampoco se sincronizan con Git.
- Las rutas de videos y direcciones RTSP deben ser válidas desde el equipo
  donde corre el servidor.
- Para evitar abrir dos veces las cámaras, ejecuta una sola instancia de
  Uvicorn (`--workers 1`, valor predeterminado). No escales procesos de API sin
  separar antes el servicio de captura/inferencia.
- El backend no incluye autenticación ni roles. No lo expongas directamente a
  Internet; úsalo solo en un entorno de confianza hasta añadir controles de
  acceso.
- Las notificaciones están configuradas para consola.
