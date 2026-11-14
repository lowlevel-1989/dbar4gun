# dbar4gun on RetroPie

English | [Español](README.es.md)

`dbar4gun.sh` is the RetroPie-Setup module of dbar4gun: it installs the driver,
starts it as a service and adds the calibrator to Ports.

## 1. Install

Download the module into RetroPie-Setup:

```
cd ~/RetroPie-Setup/scriptmodules/supplementary
curl -LO https://raw.githubusercontent.com/lowlevel-1989/dbar4gun/master/retropie/dbar4gun.sh
```

Open RetroPie-Setup (`sudo ~/RetroPie-Setup/retropie_setup.sh`) and choose:

*Manage packages → driver → dbar4gun → Install*

## 2. Start the service

*Manage packages → driver → dbar4gun → Configuration → Enable dbar4gun*

1. Choose the resolution of your TV (1080p, 720p or manual).
2. Choose the calibration mode (the first one, 3 points, is the default).
3. In the options menu, check the values and choose **dbar4gun start**.

From then on the service starts with the system. The options of that menu:

| option | what it does |
|---|---|
| width / height | size of your screen |
| smoothing level | smoothing of the cursor: 0 off, higher is smoother |
| tilt correction | the cursor does not move when the Wiimote is tilted |
| default area profile | `full` (default), `4:3` or `custom:...`: [area profiles](../docs/area-profiles.md) |
| useful zone | part of the screen height with targets (0.85) |
| distance compensation | the calibration keeps working if you move closer or further |
| calibrator in Ports | adds or removes *Ports → dbar4gun calibrator* |
| area profiles per game | runcommand applies the profile of each game (`profiles.cfg`) |
| calibrator resolution / language | `native` or `1280x720` if it is slow; `en` or `es` |
| Bluetooth: double input | see [Bluetooth](#4-bluetooth) |

To stop it: *Configuration → Disable dbar4gun*. To see its state:

```
systemctl status dbar4gun
```

## 3. Before playing

- Turn off the RetroArch hotkeys that clash with the guns: see
  [Before playing: RetroArch](../README.md#before-playing-retroarch).
- Calibrate from where you play: *Ports → dbar4gun calibrator*. How:
  [calibration](../docs/calibration.md).

## 4. Bluetooth

With the DolphinBar (mode 4) there is nothing to pair.

The Raspberry Pi 3 and newer have Bluetooth. A Raspberry Pi 2 or older needs a
Bluetooth dongle: [dongles known to work](https://elinux.org/RPi_USB_Bluetooth_adapters#Working_Bluetooth_adapters).

Pair the Wiimote from RetroPie:
[adding-a-bluetooth-controller-to-retropie](https://retropie.org.uk/docs/Bluetooth-Controller/#adding-a-bluetooth-controller-to-retropie)

Over Bluetooth the kernel also creates a gamepad for the Wiimote (and another
one for the Nunchuk), so EmulationStation and RetroArch would get every button
twice: from that gamepad and as a key of dbar4gun. dbar4gun blocks those two
gamepads while it uses the Wiimote, so the buttons only arrive once. To keep
both inputs: options menu → *Bluetooth: allow the double input* (or the
`--no-input-grab` option). With the DolphinBar there is no such gamepad.

## 5. Update

Download `dbar4gun.sh` again (step 1) and, in the same menu, choose *Update*
(or *Install*). The calibrations and the settings are kept.
