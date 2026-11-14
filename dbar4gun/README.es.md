# dbar4gun (código)

[English](README.md) | Español

El código del driver. Cómo instalarlo y usarlo está en el
[README principal](../README.es.md).

## Cómo funciona

```
Wiimote --hidraw--> wiimote.py --> core/ (a dónde apunta) --> virtualgun.py --uinput--> juegos
                        ^                                            |
               daemon/ (un worker por Wiimote)                       +--UDP--> gui/ (calibrator)
                        ^
   monitor.py (udev: se conecta o desconecta un Wiimote)

command.py / gui/ --socket de control (control.py)--> daemon/
```

1. `monitor.py` ve que se ha conectado un Wiimote.
2. `daemon/` lanza un proceso (worker) para él.
3. El worker lee el Wiimote (`wiimote.py`), `core/` calcula a dónde apunta
   y `virtualgun.py` mueve la pistola que ven los juegos.

## Carpetas

| carpeta   | de qué se encarga                                                          |
|-----------|----------------------------------------------------------------------------|
| `daemon/` | el servicio: un worker por Wiimote, socket de control, orden de las pistolas ([README](daemon/README.es.md)) |
| `core/`   | el pipeline, sin I/O: de los dots IR al cursor ([README](core/README.es.md)) |
| `gui/`    | el calibrator (`dbar4gun gui`, pygame) ([README](gui/README.es.md))        |

## Archivos

| archivo         | de qué se encarga                                                    |
|-----------------|----------------------------------------------------------------------|
| `command.py`    | el comando `dbar4gun`: opciones, arrancar/parar el servicio, el calibrator, comandos al servicio |
| `wiimote.py`    | habla con un Wiimote por hidraw: cámara IR, LEDs, Nunchuk, rumble, reports |
| `virtualgun.py` | la VirtualGun (uinput): ratón absoluto, clicks y teclas (auto key, combos) |
| `monitor.py`    | udev: avisa cuando se conecta o desconecta un Wiimote                |
| `control.py`    | socket de control: entra una línea de texto, sale una línea JSON     |
| `protocol.py`   | paquete UDP del servicio al calibrator (`docs/PROTOCOL.md`)          |
| `store.py`      | calibraciones guardadas y `hardware.json` (una clave por Wiimote)    |
| `profiles.py`   | area profile por juego (`profiles.cfg`, hooks de runcommand de RetroPie) |
| `mouseindex.py` | número de cada VirtualGun en RetroArch (el jugador de la pistola)    |
| `inputgrab.py`  | Bluetooth: bloquea el mando que crea el kernel para el Wiimote       |
| `info.py`       | nombre, versión, autor y licencia                                    |

