# dbar4gun 0.6.0
dbar4gun is a Linux userspace driver for the DolphinBar x4 Wiimote, specifically designed to be small and function as 4 light guns.

## Recommendation
This software works best with modern wiimote models with integrated wiimotion plus support. Older wiimotes with an external wiimotion accessory are discouraged as they tend to behave erratically.

It is important to remember to disconnect the Wiimote using the power button at the end of playing to increase the lifespan of the infrared LEDs.

## Feature support
- Only DolphinBar in mode 4
- N Mayflash Dolphinbar
- 4 wiimote x Dolphinbar
- wiimote with individual buttons
- multiplayer
- wiimote led -> index mouse (bin number)
- auto key
- works on linux
- works on retropie
- works on raspbian

| device    | button    | map            | shared | mame default        | state                     |
|-----------|-----------|----------------|--------|---------------------|---------------------------|
| wiimote   | ir        | mouse cursor   | false  | cursor              | ok                        |
| wiimote   | a         | auto key       | false  | bomb                | ok                        |
| wiimote   | b         | mouse left     | false  | trigger             | ok                        |
| wiimote   | home      | mouse middle   | false  |                     | ok                        |
| wiimote   | 1         | auto key       | false  |                     | ok                        |
| wiimote   | 2         | mouse right    | false  | reload (retroarch)  | ok                        |
| wiimote   | plus      | auto key       | false  | start               | ok                        |
| wiimote   | minus     | auto key       | false  | 1 coin              | ok                        |
| wiimote   | d-pad     | auto key       | false  | direction           | ok                        |
| combo     | b + minus | key esc        | true   | exit (retroarch)    | ok                        |
| combo     | b + plus  | key enter      | true   | select              | ok                        |
| combo     | b + home  | key tab        | true   | menu                | ok                        |
| combo     | b + 1     | key -          | true   | machine volume down | ok                        |
| combo     | b + 2     | key =          | true   | machine volume up   | ok                        |
| nunchuck  | z         | auto key       | false  |                     | working support retroarch |
| nunchuck  | c         | auto key       | false  |                     | working support retroarch |
| nunchuck  | stick     | wiimote d-pad  | false  | direction           | working support retroarch |
| wiimote   | 1         | mouse forward  | false  |                     | working support retroarch |
| wiimote   | 2         | mouse touch    | false  |                     | working support retroarch |
| wiimote   | d-pad     | mouse wheel    | false  |                     | working support retroarch |
| wiimote   | plus      | mouse side     | false  |                     | working support retroarch |
| wiimote   | minus     | mouse extra    | false  |                     | working support retroarch |
| nunchuck  | z         | mouse back     | false  |                     | working support retroarch |
| nunchuck  | c         | mouse task     | false  |                     | working support retroarch |

## To Do
2. Smoothed cursor
3. Haptic Mode
4. Support nunchuck
5. Class Manage Device
6. Class Log System
7. Docker Version

## Installing without Docker
### System dependencies
- git
- python
### Python dependencies
- evdev>=0.3.0
- pyudev>=0.16

### Steps with root
#### build
~~~
cd dbar4gun
python -m venv env
source env/bin/activate
pip install .
~~~

### Use
#### run service with root
~~~
dbar4gun --width 1920 --height 1080
~~~

## Installing with Docker (it does not work)
### Dependencies
- git
- docker or podman

### Steps
#### build
~~~
git clone https://github.com/lowlevel-1989/dbar4gun.git
docker build -t dbar4gun:0.3.2 dbar4gun
~~~

### Use
#### run service
~~~
docker container run --name dbar4gun -d --restart unless-stopped --privileged dbar4gun:0.3.2 --width 1920 --height 1080
~~~
#### stop
~~~
docker container stop dbar4gun
~~~
#### remove
~~~
docker container rm dbar4gun
~~~
#### logs
~~~
docker container logs dbar4gun
~~~

## References

The wiimote report format is not open and had to be reverse engineered. These resources have been very helpful when creating dbar4gun:

- <https://www.wiibrew.org/wiki/Wiimote>
- <https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL>
