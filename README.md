# dbar4gun 0.7.0

dbar4gun is a Linux userspace driver for the DolphinBar, specifically designed to be small and function as 4 light guns.

## Recommendation

This software works best with wiimote models with integrated wiimotion plus support. It is advised to avoid using generic or knockoff wiimotes as they may exhibit erratic behavior.

It is important to remember to disconnect the Wiimote using the power button at the end of playing to increase the lifespan of the infrared LEDs.

## Feature support

- Only DolphinBar in mode 4
- N Mayflash Dolphinbar
- 4 wiimote x Dolphinbar
- wiimote with individual buttons
- multiplayer
- nunchuck
- calibration
- Standard configuration for Wii sensor
- dbar4gun supports maximum resolution and sensitivity without causing cursor jumps
- wiimote led -> index mouse (bin number)
- auto key
- Smoothed cursor
- works on linux
- works on retropie
- works on raspbian

![Standard configuration for Wii sensor](.docs/setup.jpeg)

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
| nunchuck | z         | auto key      | false  | aux a (retroarch)   |
| nunchuck | c         | auto key      | false  |                     |
| combo    | b + minus | key esc       | true   | exit (retroarch)    |
| combo    | b + plus  | key enter     | true   | select              |
| combo    | b + home  | key tab       | true   | menu                |
| combo    | b + 1     | key -         | true   | machine volume down |
| combo    | b + 2     | key =         | true   | machine volume up   |
| combo    | a + plus  |               | false  | start calibration   |
| combo    | a + minus |               | false  | reset calibration   |

## Calibration wherever

- **Initiate calibration:** Press the A + plus button simultaneously. When all four LEDs light up, calibration has begun.
- **Step 1:** Shoot at the center of the screen. The first LED will light up.
- **Step 2:** Shoot at the top-left corner of the screen. The second LED will light up.
- **Step 3:** Shoot at the top-right corner of the screen. The third LED will light up.
- **Step 4:** Shoot at the bottom-left corner of the screen. The fourth LED will light up.
- **Step 5:** Shoot at the bottom-right corner of the screen.  
    
Once you've completed these steps, your Light Gun will be calibrated and ready to use.

## To Do

1. Retropie Setup
2. Systemd
3. Class Manage Device
4. Class Log System
5. Docker Version
6. Bluetooth (low priority)

## Installing without Docker

### System dependencies

- git
- python

### Python dependencies

- evdev>=0.3.0
- pyudev>=0.16
- numpy>=2.0.0
- opencv-python>=4.10.0

### Steps with root

#### build

```
cd dbar4gun
python -m venv $(pwd)
source $(pwd)/bin/activate
pip install $(pwd)
deactivate
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

#### stop service with root

```
dbar4gun stop
```

## Installing with Docker (it does not work)

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
