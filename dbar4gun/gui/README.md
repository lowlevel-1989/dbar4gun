# gui

English | [Español](README.es.md)

The calibrator (`dbar4gun gui`). It is used with the Wiimote only and needs
pygame (`pip install pygame`).

Each frame, `app.py` reads the Wiimote packets that the daemon sends, then
updates and draws the active screen.

| file          | what it does                                                          |
|---------------|-----------------------------------------------------------------------|
| `__init__.py` | `GUI`: entry point of `dbar4gun gui` (sets the language, opens `App`) |
| `app.py`      | `App`: window, 60 fps loop, screen changes, `status` from the daemon  |
| `draw.py`     | colors and shared drawing (text, camera view, targets...)             |
| `i18n.py`     | texts in each language                                                |

## logic/

No pygame: these files can be tested with the simulator (`tests/`).

| file             | what it does                                                  |
|------------------|---------------------------------------------------------------|
| `wiimotes.py`    | reads the daemon packets; state and buttons of each Wiimote   |
| `calibration.py` | bar distance, tilt and position; reach test; wizard targets   |
| `gallery.py`     | shooting gallery: targets, error of each shot and analysis    |
| `tune.py`        | smoothing auto-tune (One Euro): `fc_min` and `beta`           |
| `hardware.py`    | hardware check: link, IR, accelerometer, FOV, bar, disconnect |

## screens/

One screen per file. `update(now)` reads the buttons and `draw(surf)` draws
it. The drawing helpers are reached through `self.app`.

| file             | screen (menu option)                                             |
|------------------|------------------------------------------------------------------|
| `base.py`        | `Screen` and `GunScreen` (screen of one Wiimote; Home goes back) |
| `menu.py`        | main menu                                                        |
| `hardware.py`    | Hardware check                                                   |
| `wizard.py`      | Calibrate                                                        |
| `gallery.py`     | Shooting gallery                                                 |
| `tune.py`        | Smoothing auto-tune                                              |
| `reach.py`       | Reach test                                                       |
| `install.py`     | Installation (distance, level, center)                           |
| `diagnostics.py` | IR diagnostics                                                   |
| `players.py`     | Players and buttons                                              |
| `profiles.py`    | Area profile                                                     |
| `history.py`     | Calibration history                                              |

To add a screen: create a file in `screens/` with a class that inherits from
`GunScreen`, then add it to `ITEMS` and `SCREENS` in `menu.py`, and its texts
to `i18n.py`.
