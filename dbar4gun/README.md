# dbar4gun (code)

English | [Español](README.es.md)

The code of the driver. How to install and use it is in the
[main README](../README.md).

## How it works

```
Wiimote --hidraw--> wiimote.py --> core/ (where it points) --> virtualgun.py --uinput--> games
                        ^                                            |
               daemon/ (one worker per Wiimote)                      +--UDP--> gui/ (calibrator)
                        ^
   monitor.py (udev: a Wiimote is connected or disconnected)

command.py / gui/ --control socket (control.py)--> daemon/
```

1. `monitor.py` sees that a Wiimote is connected.
2. `daemon/` starts one process (worker) for it.
3. The worker reads the Wiimote (`wiimote.py`), `core/` calculates where it
   points, and `virtualgun.py` moves the gun that the games see.

## Folders

| folder    | what it does                                                               |
|-----------|----------------------------------------------------------------------------|
| `daemon/` | the service: one worker per Wiimote, control socket, gun order ([README](daemon/README.md)) |
| `core/`   | the pipeline, without I/O: from the IR dots to the cursor ([README](core/README.md)) |
| `gui/`    | the calibrator (`dbar4gun gui`, pygame) ([README](gui/README.md))          |

## Files

| file            | what it does                                                         |
|-----------------|----------------------------------------------------------------------|
| `command.py`    | the `dbar4gun` command: options, start/stop the service, the calibrator, commands to the service |
| `wiimote.py`    | talks to a Wiimote through hidraw: IR camera, LEDs, Nunchuk, rumble, reports |
| `virtualgun.py` | the VirtualGun (uinput): absolute mouse, clicks and keys (auto key, combos) |
| `monitor.py`    | udev: tells when a Wiimote is connected or disconnected              |
| `control.py`    | control socket: one text line in, one JSON line out                  |
| `protocol.py`   | UDP packet from the service to the calibrator (`docs/PROTOCOL.md`)   |
| `store.py`      | saved calibrations and `hardware.json` (one key per Wiimote)         |
| `profiles.py`   | area profile per game (`profiles.cfg`, RetroPie runcommand hooks)    |
| `mouseindex.py` | number of each VirtualGun in RetroArch (the player of the gun)       |
| `inputgrab.py`  | Bluetooth: blocks the gamepad that the kernel creates for the Wiimote |
| `info.py`       | name, version, author and license                                    |

