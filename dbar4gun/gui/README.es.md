# gui

[English](README.md) | Español

El calibrator (`dbar4gun gui`). Se maneja solo con el Wiimote y necesita
pygame (`pip install pygame`).

En cada frame, `app.py` lee los paquetes que el daemon manda de cada
Wiimote, y después actualiza y dibuja la pantalla activa.

| archivo       | de qué se encarga                                                        |
|---------------|--------------------------------------------------------------------------|
| `__init__.py` | `GUI`: entrada de `dbar4gun gui` (pone el idioma y abre `App`)           |
| `app.py`      | `App`: ventana, bucle a 60 fps, cambio de pantalla, `status` del daemon  |
| `draw.py`     | colores y dibujo compartido (textos, vista de la cámara, targets...)     |
| `i18n.py`     | textos de cada idioma                                                    |

## logic/

Sin pygame: estos archivos se pueden probar con el simulador (`tests/`).

| archivo          | de qué se encarga                                                     |
|------------------|-----------------------------------------------------------------------|
| `wiimotes.py`    | lee los paquetes del daemon; estado y botones de cada Wiimote         |
| `calibration.py` | distancia, inclinación y posición de la barra; reach test; targets del wizard |
| `gallery.py`     | galería de tiro: targets, error de cada disparo y análisis            |
| `tune.py`        | ajuste automático del smoothing (One Euro): `fc_min` y `beta`         |
| `hardware.py`    | comprobación de hardware: enlace, IR, acelerómetro, FOV, barra, desconexión |

## screens/

Una pantalla por archivo. `update(now)` lee los botones y `draw(surf)` la
dibuja. Las funciones de dibujo se usan con `self.app`.

| archivo          | pantalla (opción del menú)                                      |
|------------------|-----------------------------------------------------------------|
| `base.py`        | `Screen` y `GunScreen` (pantalla de un Wiimote; Home vuelve)    |
| `menu.py`        | menú principal                                                  |
| `hardware.py`    | Comprobación de hardware                                        |
| `wizard.py`      | Calibrar                                                        |
| `gallery.py`     | Galería de tiro                                                 |
| `tune.py`        | Ajuste automático del smoothing                                 |
| `reach.py`       | Prueba de alcance                                               |
| `install.py`     | Instalación (distancia, nivel, centro)                          |
| `diagnostics.py` | Diagnóstico IR                                                  |
| `players.py`     | Jugadores y botones                                             |
| `profiles.py`    | Perfil de área                                                  |
| `history.py`     | Historial de calibraciones                                      |

Para añadir una pantalla: crea un archivo en `screens/` con una clase que
herede de `GunScreen`, y después añádela a `ITEMS` y `SCREENS` en `menu.py`, y
sus textos a `i18n.py`.
