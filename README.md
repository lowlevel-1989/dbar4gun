# dbar4gun 0.3.4

dbar4gun is a Linux userspace driver for the DolphinBar x4 Wiimote, specifically designed to be small and function as 4 light guns.

## Feature support
- Only DolphinBar in mode 4
- N Mayflash Dolphinbar
- 4 wiimote x Dolphinbar
- wiimote with individual buttons
- working in linux
- working in retropie
- working in raspbian

| device    | button    | map           | state                              |
|-----------|-----------|---------------|------------------------------------|
| wiimote   | a         | mouse right   | ok                                 |
| wiimote   | b         | mouse left    | ok                                 |
| wiimote   | 1         | mouse middle  | ok                                 |
| wiimote   | 2         | mouse touch   | ok                                 |
| wiimote   | hat       | mouse wheel   | working                            |
| wiimote   | ir        | mouse cursor  | ok                                 |
| wiimote   | plus      | mouse side    | ok                                 |
| wiimote   | minus     | mouse extra   | ok                                 |
| wiimote   | home      | mouse forward | working<br />add support retroarch |
| nunchuck  | z         | mouse back    | working<br />add support retroarch |
| nunchuck  | c         | mouse task    | working add support retroarch      |
| nunchuck  | stick     | mouse wheel   | working                            |
| combo     | b + minus | key escape    | working                            |
| combo     | b + plus  | key enter     | working                            |
| combo     | b + home  | key tab       | working                            |

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
