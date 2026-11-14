# daemon

[English](README.md) | Español

El servicio (`dbar4gun start`). Espera a los Wiimotes y lanza un proceso
(worker) por cada uno. El worker lee su Wiimote y mueve su VirtualGun.

## Una clase en varios archivos

`Dbar4Gun` (en `service.py`) es una sola clase. Está repartida por tareas:
cada archivo tiene una parte de la clase y `Dbar4Gun` las junta todas:

```python
class Dbar4Gun(Options, Devices, Worker, SingleProcess, GunOrder, Commands):
```

Todas las partes usan el mismo `self`. Por ejemplo, `devices.py` llama a
`self.store()`, que está en `options.py`.

| archivo       | de qué se encarga                                                   |
|---------------|---------------------------------------------------------------------|
| `service.py`  | `Dbar4Gun`: arrancar (`run`), parar (`stop`), cerrar el daemon anterior (`kill`) |
| `options.py`  | opciones de la línea de comandos, `hardware.json` y `profiles.cfg`; opciones del pipeline |
| `devices.py`  | Wiimotes que llegan y se van: crea y quita los workers              |
| `worker.py`   | el proceso de un Wiimote: emparejar, leer, mover la VirtualGun, responder comandos |
| `commands.py` | socket de control: `status`, `area`, `calibrate`, `hw`...           |
| `order.py`    | mantiene el orden de encendido de las pistolas en RetroArch         |
| `single.py`   | modo experimental `--single-process`: todos los Wiimotes en un proceso |

Ayudas (funciones, no son parte de la clase):

| archivo      | de qué se encarga                                                    |
|--------------|----------------------------------------------------------------------|
| `ports.py`   | qué VirtualGun (01, 02...) le toca a cada Wiimote                    |
| `pidfile.py` | archivo PID; reconoce un daemon anterior antes de pararlo            |
| `pipes.py`   | fork para los workers, y un pipe entre hilos para `single.py`        |

## Qué pasa al conectar un Wiimote

1. `monitor.py` (udev) ve un `hidraw` nuevo y lo pone en la cola.
2. `devices.py` lo abre, elige su puerto (`ports.py`) y lanza un worker.
3. `worker.py` espera a que el Wiimote responda, crea su VirtualGun y
   después, en cada report: lee el Wiimote, mueve la VirtualGun y manda el
   paquete UDP al calibrator.
4. Cada pocos segundos, `order.py` comprueba que RetroArch numera las
   pistolas en el orden de encendido.

Si un Wiimote de Bluetooth se desconecta, su worker y su VirtualGun se
conservan hasta que vuelve el mismo Wiimote (`devices.py`: detach /
reattach). El juego no pierde la pistola.

## Comandos

`dbar4gun status`, el calibrator, etc. hablan con el servicio por el socket
de control (`control.py`). `commands.py` los atiende. Un comando que afecta a
un Wiimote se manda a su worker por un pipe, y el worker lo responde en
`worker.py` (`_worker_command`).
