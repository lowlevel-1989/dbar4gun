# Install on Linux (without RetroPie)

English | [Español](install-linux.es.md)

With RetroPie, follow [retropie/README.md](../retropie/README.md) instead.

## 1. Dependencies

- git, python >= 3.7, bluez >= 5.0
- pygame, only for the calibrator: `pip install pygame` or the package of your
  distro

## 2. Install

```
git clone https://github.com/lowlevel-1989/dbar4gun
cd dbar4gun
python -m venv $(pwd)
source $(pwd)/bin/activate
pip install $(pwd)
```

This also installs evdev and pyudev.

## 3. Start the service (as root)

```
dbar4gun start --width 1920 --height 1080
```

`--width` and `--height` are the size of your screen. Every option and command:
[usage.md](usage.md).

To start it with the system, copy `platforms/desktop/dbar4gun.service` to
`/etc/systemd/system/`, change the path of `dbar4gun` (the one of your venv)
and the options, and run:

```
sudo systemctl daemon-reload
sudo systemctl enable --now dbar4gun
```

The calibrator and the control commands do not need root:
`dbar4gun gui --windowed`, `dbar4gun area 4:3`.

## 4. Pair the Wiimote (Bluetooth)

With the DolphinBar (mode 4) there is nothing to pair.

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

## Where the settings are

| platform | config dir (default)                 | area profile per game |
|----------|--------------------------------------|-----------------------|
| RetroPie | `/opt/retropie/configs/all/dbar4gun` | runcommand hooks (installed by the RetroPie module, `dbar4gun hooks install`) |
| desktop  | `/var/lib/dbar4gun`                  | wrapper `platforms/desktop/dbar4gun-run.sh` |

`--config-dir` changes the folder. It has `calibration.json` (calibrations,
history, filter), `hardware.json` (values measured with the hardware check),
`hardware_report.json` and `profiles.cfg` (area profile per game).

To change the area profile per game on a desktop, start the emulator with the
wrapper:

```
platforms/desktop/dbar4gun-run.sh arcade mame ghoul.zip -- mame ghoul
```

Batocera and Recalbox are not supported for now.
