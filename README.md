# dbar4gun 1.0.0

English | [Español](README.es.md)

dbar4gun is a Linux userspace driver for the wiimote with DolphinBar support, specifically designed to function as 4 light guns.

[!["Buy Me A Coffee"](docs/coffee.png)](https://ko-fi.com/lowlevel1989)

If you'd like to see updates and active support for this driver continue as quickly as possible, consider supporting the project — you can buy me a coffee ☕ to help keep things running!

## Recommendation

We recommend using DolphinBar as the main controller because, in mode 4, the bar stays on until we turn off the Wiimote. This way, we avoid having to manually connect or disconnect the USB every time we want to play with the Wiimote.

It is important to remember to disconnect the Wiimote using the power button at the end of playing to increase the lifespan of the infrared LEDs.

***for more precision, place the sensor bar over the screen***

## Feature support

- Only DolphinBar in mode 4
- N Mayflash Dolphinbar
- 4 wiimote x Dolphinbar (very fast with a single bar)
- Bluetooth
- wiimote with individual buttons
- multiplayer
- nunchuck
- tilt correction
- distance compensation
- calibration two, three (default) and four points
- calibration saved per Wiimote
- area profiles (full, 4:3, custom) per game
- visual calibrator (pygame) with hardware check
- control socket and CLI commands
- Standard configuration for Wii sensor
- wiimote led -> index mouse
- auto key
- systemd
- Smoothed cursor (One Euro)
- setup ir as Component
- calibration as Component
- Generic wiimote
- works on linux
- works on retropie
- works on raspbian

![Standard configuration for Wii sensor](docs/setup.jpeg)

| device   | button    | map           | only cursor          | shared        | mame default                      |
|----------|-----------|---------------|----------------------|---------------|-----------------------------------|
| wiimote  | ir        | mouse cursor  | same                 | false         | cursor                            |
| wiimote  | a         | auto key      | btn a    (Bluetooth) | false         | bomb                              |
| wiimote  | b         | mouse left    | same                 | false         | trigger                           |
| wiimote  | home      | key enter     | btn home (Bluetooth) | true / false  | select                            |
| wiimote  | 1         | mouse middle  | btn 1    (Bluetooth) | false         |                                   |
| wiimote  | 2         | mouse right   | btn 2    (Bluetooth) | false         | reload (retroarch)                |
| wiimote  | plus      | auto key      | key next (Bluetooth) | false / true  | start                             |
| wiimote  | minus     | auto key      | key prev (Bluetooth) | false / true  | 1 coin                            |
| wiimote  | d-pad     | auto key      | arrows   (Bluetooth) | false / true  | direction                         |
| nunchuck | stick     | wiimote d-pad | abs hat  (Bluetooth) | false         | direction                         |
| nunchuck | z         | auto key      | btn z    (Bluetooth) | false         |                                   |
| nunchuck | c         | auto key      | btn c    (Bluetooth) | false         |                                   |
| combo    | b + home  | key tab       | same                 | true          | menu (mame,flycast)               |
| combo    | b + plus  |               | same                 | false         | disable/enable ir (useful in gui) |
| combo    | b + minus | key esc       | same                 | true          | exit (retroarch)                  |
| combo    | b + 1     | key space     | same                 | true          | fast forward                      |
| combo    | b + 2     | key 2         | same                 | true          | start (P2)                        |
| combo    | a + home  | key f1        | same                 | true          | menu (retroarch)                  |
| combo    | a + plus  |               | same                 | false         | calibration (quick 2-point recalibration if already calibrated) |
| combo    | a + minus |               | same                 | false         | reset calibration (back to the uncalibrated map) |



## Known Issues

### 1. Failure of IR LEDs on the DolphinBar

**Issue:** The DolphinBar has infrared LEDs that can burn out easily, making it impossible to aim correctly.  
**Solution:** Replace the damaged LEDs or swap the bar for a new one. The calibrator's *IR diagnostics* shows each dot; with `--experimental-ir-extended` it also shows the dot size (a weak LED looks smaller).

### 2. I can move the pointer, but I can't shoot

**Issue:** If you can move the pointer but can't shoot, the driver may be detecting a keyboard or mouse as a second light gun.  
**Solution:** Change the "mouse index" in the emulator settings to match the light gun's index and avoid conflicts. The calibrator's *Players and buttons* screen shows the LED → VirtualGun → mouse index map and the keys each button emits.

~~~
wiimote led 1  -> mouse index 0 (and 4, 8...)
wiimote led 2  -> mouse index 1
wiimote led 3  -> mouse index 2
wiimote led 4  -> mouse index 3
~~~

The LED shows the mouse index the way RetroArch numbers mice (udev): every
mouse in the system counts, in libudev's order. The keys of each gun are the
ones of the player with that mouse index, so in RetroArch the gun works for
that player without changing anything. The index is checked every 3 seconds:
if a mouse is plugged in or removed, the LED and the keys follow it. A
Wiimote connected by Bluetooth keeps its VirtualGun (and its place in the
list) when it disconnects and comes back.

When the driver takes a Wiimote (and every time it reconnects), the Wiimote
rumbles briefly and its LEDs sweep 1-2-3-4-all before showing its own LED. The
DolphinBar only lights a fixed LED, so the sweep tells you the driver has it.

### 3. The pointer becomes unstable for no apparent reason

**Issue:** The pointer moves erratically for no apparent reason.  
**Possible Cause:** Sunlight, a lamp or a reflection interferes with the infrared sensor.  
**Solution:** Check it with *IR diagnostics* in the calibrator (extra IR sources are drawn in red). Reflections and other sources are usually ignored now; if not, try another `--ir-sensitivity` level.

### 4. Calibration issues

**Issue:** Difficulties in calibrating the Wiimote properly.  
**Possible Causes and solutions:**
- Two short rumbles: the capture was rejected (unsteady aim, or the bar was not visible). Hold still and shoot again.
- You are too close to the TV: the bottom of the screen is out of the camera's reach. Run the *Reach test* in the calibrator; it tells you how far to move back.
- If using DolphinBar, one of the IR LEDs may be damaged (see 1).

### 5. The crosshair does not reach the edges of the game

**Issue:** In 4:3 games on a 16:9 TV the gun range covers the whole TV.  
**Solution:** With RetroArch (`lr-*` cores) use the `full` profile: RetroArch maps the gun to the game image itself. With a standalone emulator that stretches the gun range over the image, use the `4:3` area profile (`dbar4gun area 4:3`, the `--area` option or per game in `profiles.cfg`).

## Calibration

Calibrate from where you play. The calibration is saved per Wiimote (Bluetooth
MAC or DolphinBar slot) in `calibration.json` and loaded every time the driver
starts. During the calibration the in-game crosshair shows the target, a short
rumble confirms each capture and two short rumbles mean it was rejected (repeat
that point).

The easiest way is the visual calibrator (*Ports → dbar4gun calibrator*
or `dbar4gun gui`): it adapts the targets to your reach, shows the steadiness of
your aim, checks the result and lets you calibrate every player in a row.

From the game:

### mode 2 (default): 3 points
- **A + plus** (LED 1): shoot at the **top-left** target.
- LED 4: shoot at the **top-right** target.
- LEDs 2 and 3: shoot at the **bottom-center** target (at the useful zone height).

Once calibrated, **A + plus** does a quick 2-point recalibration (top-left and
top-right; bottom corners if the bar is below the TV). It is useful if the bar
moved. **A + minus** goes back to the uncalibrated map; the next **A + plus**
does the full calibration.

### mode 1: 2 points
- **A + plus** (LEDs 2 and 3): shoot at the **center**.
- LED 1: shoot at the **top-left** target.

### mode 3: 4 points (homography)
- **A + plus**: shoot at the top-left (LED 1), top-right (LED 4),
  bottom-right (LEDs 3+4) and bottom-left (LEDs 1+2) targets. More precise at the
  corners and when you do not sit in front of the TV.

### mode 0: disabled

## Light Gun Configuration Manual for Specific Core Ga   
Refer to the [specific README for light gun configuration](retroarch) to ln how to configure games in RetroArch.
  
## List of No-Crosshair Games: Perfect Performance with wiimote (tested)   
    
| game                     | ROM / disc                     | emulator (RetroPie)  | resolution | smoothing level | note                       |
|--------------------------|--------------------------------|----------------------|------------|-----------------|----------------------------|
| Operation Wolf           | `opwolf`                       | lr-mame              | 320x240    |  0              |                            |
| Point Blank              | `ptblank`                      | lr-mame              | 288x224    |  0              |                            |
| Point Blank 2            | `ptblank2`                     | lr-mame              | 320x240    |  0              |                            |
| Point Blank 3            | `ptblank3`                     | lr-mame              | 320x240    |  0              |                            |
| Ghoul Panic              | `ghlpanic`                     | lr-mame              | 512x480    |  0              |                            |
| Time Crisis              | `timecris`                     | lr-mame              | 640x480    |  0              |                            |
| Golly! Ghost!            | `gollygho`                     | lr-mame              | 288x224    |  0              |                            |
| VS. Hogan's Alley        | `hogalley`                     | lr-mame              | 256x240    |  0              | low precision in the bonus |
| Lucky & Wild             | `luckywld`                     | lr-mame2015          | 288x224    |  0              |                            |
| Area 51                  | `area51`                       | lr-mame2003-plus     | 320x240    |  0              |                            |
| House of the Dead 2      | `House of the Dead 2, The (USA).gdi` | flycast (standalone) | 640x480    |  0              |                            |
| Virtua Cop 2             | `Virtua Cop 2 (Japan).gdi`     | lr-flycast           | 640x480    |  0              |                            |

How they were tested: RetroPie on a Raspberry Pi 5 (Debian 12), RetroArch 1.19.1,
dbar4gun 0.18.2 with `--smoothing-level 0`, each game with the emulator above.
Gun options of the cores: `mame_current_xy_type = "lightgun"` (lr-mame),
`mame2003-plus_xy_device = "lightgun"`, `mame2015_mouse_mode = "lightgun"`.

### Change the emulator of a game with the Wiimote (RetroPie)

1. Start the game from EmulationStation.
2. While "Launching..." is on screen, press **home** (`key enter`): the runcommand menu opens.
3. Move with the **d-pad**, choose **Select emulator for ROM** and then the emulator, confirming with **home**.
4. Choose **Launch**. From then on, that game always starts with that emulator.

To leave the game: **b + minus** (`key esc`).

### Raspberry Pi 5: Point Blank 3 and the lr-mame version

Emulation speed of Point Blank 3 (`ptblank3`) on a Raspberry Pi 5 with lr-mame,
measured without video or sound output. The game needs 60 fps.

| lr-mame core                                                   | measures (fps)                          | average | always above 60 |
|----------------------------------------------------------------|-----------------------------------------|---------|-----------------|
| 0.289, full (arcade, as RetroPie installs it)                  | 56.0, 57.3, 57.7                        | 57.0    | no              |
| 0.289, 54 light gun drivers                                    | 56.8, 57.0, 57.0                        | 56.9    | no              |
| 0.289, only Namco System 10/12                                 | 60.6, 61.6, 60.5, 60.1, 57.2            | 60.0    | no              |
| 0.278, only Namco System 10/12                                 | 61.8, 58.5, 64.8, 58.9                  | 61.0    | no              |
| 0.276, the 8 drivers of the lr-mame games in this list         | 62.0, 58.9, 61.5                        | 60.8    | no              |
| 0.276, only Namco System 10/12                                 | 62.3, 62.5, 67.2, 61.3, 61.6, 62.0      | 62.8    | yes             |
| 0.276, only Namco System 10/12, built for the Pi 5             | 66.4, 63.5, 67.5                        | 65.8    | yes             |

Conclusion:

- The full lr-mame core (0.289) never reaches full speed with Point Blank 3 on a Pi 5.
- A core built only with the drivers the game needs is faster. With many
  drivers (54) that advantage is lost.
- Since lr-mame 0.278 the game is slower and less steady.
- The best one is lr-mame 0.276 built only with Namco System 10/12 and for the
  Pi 5 CPU (`OPTIMIZE=3 ARCHOPTS=-mcpu=cortex-a76`): always above 60 fps, with
  margin, and played in the game it runs at full speed. How to build it: [docs/lr-mame-pi5.md](docs/lr-mame-pi5.md).

Point Blank 2, Ghoul Panic and Golgo 13 run on Namco System 12, so the same core
covers them.

Test setup: Raspberry Pi 5 (4 GB) with RetroPie and RetroArch 1.19.1, overclocked
in `/boot/firmware/config.txt`:

```
arm_freq=2600
over_voltage_delta=50000
```

## Memory Consumption of the dbar4gun

Currently, the dbar4gun consumes ~24 MB. For each Wiimote connected via Bluetooth, an additional ~19 MB is consumed, as a dedicated process is generated to manage each Wiimote.

In the case of the DolphinBar, it is detected as four Wiimotes, even if they are not connected, resulting in an additional consumption of ~76 MB.

### Summary of Memory Consumption

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

## Area profiles

With RetroArch (every `lr-*` core) keep `full`: RetroArch already turns the gun
position into the game image (also a 4:3 game on a 16:9 TV), and aiming outside
the image is "offscreen", to reload. A standalone emulator that stretches the
gun range over the game image needs the game's aspect (`4:3`).

- Default profile: `--area full|4:3|custom:x0,y0,w,h` (RetroPie-Setup → dbar4gun →
  *default area profile*).
- Per game: `profiles.cfg` in the config dir (`/opt/retropie/configs/all/dbar4gun/`
  on RetroPie). Priority: `rom:<name>` > `system/emulator` > `emulator` > `system`
  > `default`. RetroPie's runcommand hooks apply it when a game starts and go back
  to the default when it ends.
- Live: `dbar4gun area 4:3`, or the *Area profile* screen of the calibrator.
- **Useful zone** (`--useful-zone 0.85`): the part of the screen height with
  targets (the bottom is usually HUD). The calibration and the reach test use it.

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

The protocol (also the UDP packet for the calibrator) is in [docs/PROTOCOL.md](docs/PROTOCOL.md).
Desktop Linux: [docs/PLATFORMS.md](docs/PLATFORMS.md).

## Development

`tests/` runs without a Wiimote: `tests/sim/` simulates the IR camera (TV, sensor
bar, player position and aim) and measures the error on a 7x7 grid.

```
pip install .[gui] pytest
SDL_VIDEODRIVER=dummy python -m pytest -s
```

The old hardware test scripts are in `tools/`.

## To Do

1. diamond ir setup
2. square ir setup

## Install with RetroPie-Setup

### Download dbar4gun installer

```
cd ~/RetroPie-Setup/scriptmodules/supplementary
curl -LO https://raw.githubusercontent.com/lowlevel-1989/dbar4gun/master/retropie/dbar4gun.sh
```

### Open RetroPie-Setup

```
*Manage packages \~ driver \~ dbar4gun \~ Install*  
```

### Run service

```
*Manage packages \~ driver \~ dbar4gun \~ Configuration \~ Enable/Restart dbar4gun*  
```

### Stop service
```
*Manage packages \~ driver \~ dbar4gun \~ Configuration \~ Disable dbar4gun*  
```

### Status service
```
systemctl status dbar4gun
```

### Bluetooth

You have a Raspberry Pi 3 or for Raspberry Pi 2 and below, you need a Bluetooth dongle (sometimes called Bluetooth adapter). For a list of dongles known to work with Raspberry Pi see [https://elinux.org/RPi_USB_Bluetooth_adapters#Working_Bluetooth_adapters](https://elinux.org/RPi_USB_Bluetooth_adapters#Working_Bluetooth_adapters) ).

[adding-a-bluetooth-controller-to-retropie](https://retropie.org.uk/docs/Bluetooth-Controller/#adding-a-bluetooth-controller-to-retropie)

## Install manually

### System dependencies

- git
- python >= 3.7
- bluez >= 5.0

### Python dependencies

- evdev>=0.3.0
- pyudev>=0.16
- pygame (only for the calibrator, `pip install .[gui]`)

### Steps with root

#### build

```
cd dbar4gun
python -m venv $(pwd)
source $(pwd)/bin/activate
pip install $(pwd)
```

### Use

#### help service
```
dbar4gun start --help
```

| option | default | |
|---|---|---|
| `--calibration {0,1,2,3}` | 2 | 0 disabled, 1 center + top-left, 2 three points, 3 four points (homography) |
| `--setup {1}` | 1 | IR setup: standard sensor bar / DolphinBar |
| `--width`, `--height` | 1920, 1080 | screen size (gun ABS range) |
| `--disable-tilt-correction` | | |
| `--no-distance-compensation` | | the precision then depends on keeping the calibration distance |
| `--smoothing-level N` | 3 | One Euro filter: 0 off, higher is smoother |
| `--area` | full | `full`, `4:3`, `custom:x0,y0,w,h` |
| `--useful-zone` | 0.85 | fraction of the screen height with targets |
| `--bar {top,bottom}` | top | sensor bar position |
| `--calibration-targets x1,y1,x2,y2,x3,y3` | | 3-point targets in gun space |
| `--ir-sensitivity {1..5,marcan,cliff}` | marcan | IR camera sensitivity (wiibrew levels) |
| `--config-dir` | per platform | calibrations and `profiles.cfg` |
| `--socket` | /run/dbar4gun.sock | control socket |
| `--port` | 35460 | UDP port for the calibrator |
| `--log-level` | info | |
| `--single-process` | | experimental: one process for every Wiimote |
| `--experimental-ir-extended` | | allow the extended IR mode (dot size) |

#### run service with root
```
dbar4gun start --width 1920 --height 1080
```

#### restart service with root

```
dbar4gun start --width 1920 --height 1080
```

#### check version

```
dbar4gun version
```

#### visual calibrator (needs pygame: `pip install .[gui]`)
```
dbar4gun gui              # full screen, Wiimote only (Home to exit)
dbar4gun gui --windowed --width 1280 --height 720
dbar4gun gui --lang es    # Spanish
```

#### stop service with root

```
dbar4gun stop
```

#### attach device with root

```
dbar4gun attach /dev/hidraw0
```

### Bluetooth

Press the red SYNC button of the Wiimote (under the battery cover) and run right
away:

~~~
bluez/pair-wiimote.sh
~~~

It finds the Wiimote in SYNC mode by itself (no need to know its MAC address),
pairs it with `bluez/simple-agent` (if it asks for a PIN code, just press Enter)
and marks it as trusted, so from then on it reconnects when you press any button.
Pair each Wiimote the same way, one at a time.

The same steps by hand (`hcitool` is no longer shipped by most distributions),
with the MAC address that the scan shows for `Nintendo RVL-CNT-01`:

~~~
sudo -v
bluetoothctl --timeout 20 scan on & sleep 6; sudo python3 bluez/simple-agent -c DisplayYesNo hci0 XX:XX:XX:XX:XX:XX
bluetoothctl trust XX:XX:XX:XX:XX:XX
~~~

If you are having trouble re-pairing the Wiimote via Bluetooth, remove it and
repeat the previous steps:

~~~
bluetoothctl remove XX:XX:XX:XX:XX:XX
~~~

## References

The wiimote report format is not open and had to be reverse engineered. These resources have been very helpful when creating dbar4gun:

- [https://www.wiibrew.org/wiki/Wiimote](https://www.wiibrew.org/wiki/Wiimote)
- [https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL](https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL)
