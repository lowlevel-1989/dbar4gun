# dbar4gun 0.11.0

dbar4gun is a Linux userspace driver for the wiimote with DolphinBar support, specifically designed to function as 4 light guns.

## Recommendation

This software works best with wiimote models with integrated wiimotion plus support. It is advised to avoid using generic or knockoff wiimotes as they may exhibit erratic behavior.

It is important to remember to disconnect the Wiimote using the power button at the end of playing to increase the lifespan of the infrared LEDs.

We recommend using DolphinBar as the main controller because, in mode 4, the bar stays on until we turn off the Wiimote. This way, we avoid having to manually connect or disconnect the USB every time we want to play with the Wiimote.

For additional Wiimotes, connect them directly via Bluetooth since DolphinBar becomes slow if more than one Wiimote is connected.

## Feature support

- Bluetooth
- Only DolphinBar in mode 4
- N Mayflash Dolphinbar  (recommended at the moment)
- 4 wiimote x Dolphinbar (slow with a single bar)
- wiimote with individual buttons
- multiplayer
- nunchuck
- calibration
- systemd
- Standard configuration for Wii sensor
- dbar4gun supports maximum resolution and sensitivity without causing cursor jumps
- wiimote led -> index mouse (bin number)
- auto key
- Smoothed cursor
- works on linux
- works on retropie
- works on raspbian

![Standard configuration for Wii sensor](docs/setup.jpeg)

| device   | button    | map           | shared | mame default        |
|----------|-----------|---------------|--------|---------------------|
| wiimote  | ir        | mouse cursor  | false  | cursor              |
| wiimote  | a         | auto key      | false  | bomb                |
| wiimote  | b         | mouse left    | false  | trigger             |
| wiimote  | home      | mouse middle  | false  |                     |
| wiimote  | 1         | auto key      | false  |                     |
| wiimote  | 2         | mouse right   | false  | reload (retroarch)  |
| wiimote  | plus      | auto key      | false  | start               |
| wiimote  | minus     | auto key      | false  | 1 coin              |
| wiimote  | d-pad     | auto key      | false  | direction           |
| nunchuck | stick     | wiimote d-pad | false  | direction           |
| nunchuck | z         | auto key      | false  |                     |
| nunchuck | c         | auto key      | false  |                     |
| combo    | b + minus | key esc       | true   | exit (retroarch)    |
| combo    | b + plus  | key enter     | true   | select              |
| combo    | b + home  | key tab       | true   | menu                |
| combo    | b + 1     | key =         | true   | machine volume up   |
| combo    | b + 2     | key -         | true   | machine volume down |
| combo    | a + plus  |               | false  | start calibration   |
| combo    | a + minus |               | false  | reset calibration   |

## Calibration wherever

- **Initiate Calibration:** Press the **A + plus** buttons simultaneously. When LED 2 and 3 light up, calibration has begun.
- **Step 1:** Shoot at the **center** of the screen. LEDs 1 and 4 will light up.
- **Step 2:** Shoot at the **top-left** corner of the screen.

Once you've completed these steps, your Light Gun will be calibrated and ready to use.

### Memory Consumption of the dbar4gun

Currently, the dbar4gun consumes ~24 MB. For each Wiimote connected via Bluetooth, an additional ~19 MB is consumed, as a dedicated process is generated to manage each Wiimote.

In the case of the DolphinBar, it is detected as four Wiimotes, even if they are not connected, resulting in an additional consumption of ~76 MB.

## Summary of Memory Consumption

| Item                                  | Memory Consumption |
|---------------------------------------|--------------------|
| dbar4gun                              | ~24 MB             |
| monitor                               | ~19 MB             |
| Per Wiimote connected via Bluetooth   | ~19 MB             |
| DolphinBar (detected as 4 Wiimotes)   | ~19 MB             |

## To Do

3. Class Manage Device
4. Class Log System
5. Docker Version

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

### stop service
```
*Manage packages \~ driver \~ dbar4gun \~ Configuration \~ Disable dbar4gun*  
```

### status service
```
systemctl status dbar4gun
```


### Bluetooth

You have a Raspberry Pi 3 or for Raspberry Pi 2 and below, you need a Bluetooth dongle (sometimes called Bluetooth adapter). For a list of dongles known to work with Raspberry Pi see [https://elinux.org/RPi_USB_Bluetooth_adapters#Working_Bluetooth_adapters](https://elinux.org/RPi_USB_Bluetooth_adapters#Working_Bluetooth_adapters) ).

[adding-a-bluetooth-controller-to-retropie](https://retropie.org.uk/docs/Bluetooth-Controller/#adding-a-bluetooth-controller-to-retropie)

## Install manually

### System dependencies

- git
- python
- bluez >= 5.0

### Python dependencies

- evdev>=0.3.0
- pyudev>=0.16

### Steps with root

#### build

```
cd dbar4gun
python -m venv $(pwd)
source $(pwd)/bin/activate
pip install $(pwd)
```

### Use

#### run service with root

```
dbar4gun --width 1920 --height 1080
```

#### restart service with root

```
dbar4gun --width 1920 --height 1080
```

#### check version

```
dbar4gun version
```

#### stop service with root

```
dbar4gun stop
```

### Bluetooth

Pair the wiimote with this command, replace the XX data with your MAC address

~~~
hcitool scan
sudo hcitool cc XX:XX:XX:XX:XX:XX
sudo python bluez/simple-agent -c "DisplayYesNo" hci0 "XX:XX:XX:XX:XX:XX"
~~~

If you are having trouble re-pairing the Wiimote via Bluetooth, all you need to do is execute the following command and repeat the previous steps.

~~~
sudo bluetoothctl remove XX:XX:XX:XX:XX:XX
~~~


## Install with Docker (it does not work)

### Dependencies

- git
- docker or podman

### Steps

#### build

```
git clone https://github.com/lowlevel-1989/dbar4gun.git
docker build -t dbar4gun:0.3.2 dbar4gun
```

### Use

#### run service

```
docker container run --name dbar4gun -d --restart unless-stopped --privileged dbar4gun:0.3.2 --width 1920 --height 1080
```

#### stop

```
docker container stop dbar4gun
```

#### remove

```
docker container rm dbar4gun
```

#### logs

```
docker container logs dbar4gun
```

## References

The wiimote report format is not open and had to be reverse engineered. These resources have been very helpful when creating dbar4gun:

- <https://www.wiibrew.org/wiki/Wiimote>
- <https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL>
