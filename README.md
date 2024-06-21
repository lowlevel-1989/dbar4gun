# dbar4gun 0.5.1

dbar4gun is a Linux userspace driver for the DolphinBar x4 Wiimote, specifically designed to be small and function as 4 light guns.

## Feature support
- Only DolphinBar in mode 4
- N Mayflash Dolphinbar
- 4 wiimote x Dolphinbar
- wiimote with individual buttons
- multiplayer
- works on linux
- works on retropie
- works on raspbian

| device    | button    | map                  | shared | state                              |
|-----------|-----------|----------------------|--------|------------------------------------|
| wiimote   | ir        | mouse cursor         | false  | ok                                 |
| wiimote   | a         | mouse right          | false  | ok                                 |
| wiimote   | b         | mouse left           | false  | ok                                 |
| wiimote   | home      | mouse middle         | false  | working                            |
| wiimote   | 1         | auto key             | false  | ok                                 |
| wiimote   | 2         | auto key             | false  | ok                                 |
| wiimote   | plus      | auto key             | false  | ok                                 |
| wiimote   | minus     | auto key             | false  | ok                                 |
| wiimote   | d-pad     | auto key             | false  | ok                                 |
| nunchuck  | z         | auto key             | false  | working add support retroarch      |
| nunchuck  | c         | auto key             | false  | working add support retroarch      |
| nunchuck  | stick     | wiimote d-pad        | false  | working add support retroarch      |
| wiimote   | 1         | mouse forward        | false  | working add support retroarch      |
| wiimote   | 2         | mouse touch          | false  | working add support retroarch      |
| wiimote   | d-pad     | mouse wheel          | false  | working add support retroarch      |
| wiimote   | plus      | mouse side           | false  | working add support retroarch      |
| wiimote   | minus     | mouse extra          | false  | working add support retroarch      |
| nunchuck  | z         | mouse back           | false  | working add support retroarch      |
| nunchuck  | c         | mouse task           | false  | working add support retroarch      |
| combo     | b + minus | key escape           | true   | working                            |
| combo     | b + plus  | key enter            | true   | working                            |
| combo     | b + home  | key tab              | true   | working                            |
| combo     | b + 1     | - (Mame Volume Down) | true   | working                            |
| combo     | b + 2     | = (Mame Volume Up)   | true   | working                            |

## To Do
1. Support all buttons
2. Support nunchuck
3. wiimote led -> index mouse
4. Class Manage Device
5. Update README
6. Smoothed axes
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
