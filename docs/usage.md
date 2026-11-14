# Options and commands

English | [Español](usage.es.md)

## Service options

Every option: `dbar4gun start --help`.

| option | default | |
|---|---|---|
| `--calibration {0,1,2,3}` | 2 | 0 disabled, 1 center + top-left, 2 three points, 3 four points (homography) |
| `--width`, `--height` | 1920, 1080 | screen size (gun ABS range) |
| `--disable-tilt-correction` | | |
| `--no-distance-compensation` | | the precision then depends on keeping the calibration distance |
| `--no-input-grab` | | Bluetooth: do not block the kernel gamepads of the Wiimote and the Nunchuk (their buttons then arrive twice) |
| `--smoothing-level N` | 3 | One Euro filter: 0 off, higher is smoother |
| `--area` | full | `full`, `4:3`, `custom:x0,y0,w,h` |
| `--useful-zone` | 0.85 | fraction of the screen height with targets |
| `--calibration-targets x1,y1,x2,y2,x3,y3` | | 3-point targets in gun space |
| `--ir-sensitivity {1..5,marcan,cliff}` | marcan | IR camera sensitivity (wiibrew levels) |
| `--config-dir` | per platform | calibrations and `profiles.cfg` |
| `--socket` | /run/dbar4gun.sock | control socket |
| `--port` | 35460 | UDP port for the calibrator |
| `--log-level` | info | |
| `--single-process` | | experimental: one process for every Wiimote |
| `--experimental-ir-extended` | | allow the extended IR mode (dot size) |

### start (or restart) the service, as root

```
dbar4gun start --width 1920 --height 1080
```

### check version

```
dbar4gun version
dbar4gun --version
```

### visual calibrator (needs pygame: `pip install pygame`)
```
dbar4gun gui              # full screen, Wiimote only (Home to exit)
dbar4gun gui --windowed --width 1280 --height 720
dbar4gun gui --lang es    # Spanish
```

### stop the service, as root

```
dbar4gun stop
```

### attach one device, as root

```
dbar4gun attach /dev/hidraw0
```

## Control commands

They talk to the running service through `/run/dbar4gun.sock` and do not need root.

```
dbar4gun status                 # Wiimotes, battery, Hz, calibration, distance (JSON)
dbar4gun area 4:3               # area profile now
dbar4gun calibrate [2] [--quick]
dbar4gun cancel
dbar4gun reload                 # reload the saved calibrations and hardware.json
dbar4gun hw [fov 38.5] [acc_x_sign -1] [bar_width 0.20] [ir_sensitivity 4|default]   # measured hardware values
dbar4gun check --area 4:3 --useful-zone 0.85   # validate option values (no daemon needed)
dbar4gun profile start <system> <emulator> [rom]   # used by the runcommand hooks
dbar4gun hooks install|uninstall
```

The protocol (also the UDP packet for the calibrator) is in [docs/PROTOCOL.md](PROTOCOL.md).
Install on Linux without RetroPie: [install-linux.md](install-linux.md).

## Memory

Currently, the dbar4gun consumes ~24 MB. For each Wiimote connected via Bluetooth, an additional ~19 MB is consumed, as a dedicated process is generated to manage each Wiimote.

In the case of the DolphinBar, it is detected as four Wiimotes, even if they are not connected, resulting in an additional consumption of ~76 MB.

### Summary of memory consumption

| Item                                  | Memory Consumption |
|---------------------------------------|--------------------|
| dbar4gun                              | ~24 MB             |
| monitor                               | ~19 MB             |
| Per Wiimote connected via Bluetooth   | ~19 MB             |
| DolphinBar (detected as 4 Wiimotes)   | ~76 MB             |

If the address of your wiimote(s) is already known (e.g. `/dev/hidraw0`), it can be attached directly using the `attach` subcommand. In that case, the monitor is not needed, and memory consumption is reduced drastically.

| Item                                  | Memory Consumption |
|---------------------------------------|--------------------|
| dbar4gun attach                       | ~24 MB             |
