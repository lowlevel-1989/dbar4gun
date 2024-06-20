# dbar4gun

dbar4gun is a Linux userspace driver for the DolphinBar x4 Wiimote, specifically designed to be small and function as 4 light guns.

## Feature support
- N Mayflash Dolphinbar
- 4 wiimote x Dolphinbar
- wiimote with individual buttons
- working in linux
- working in retropie
- working in raspbian

## Installing with Docker
### Dependencies
- git
- docker or podman

### Steps
#### build
~~~
$ git clone https://github.com/lowlevel-1989/dbar4gun.git
$ docker build -t dbar4gun:0.3.0 dbar4gun
~~~

### Use
#### run service
~~~
$ docker container run --name dbar4gun -d --restart unless-stopped --privileged dbar4gun:0.3.0
~~~
#### stop
~~~
$ docker container stop dbar4gun
~~~
#### remove
~~~
$ docker container rm dbar4gun
~~~
#### logs
~~~
$ docker container logs dbar4gun
~~~

## Installing without Docker
### Dependencies
- git
- python

### Steps with root
#### build
~~~
$ cd dbar4gun
$ python -m venv env
$ source env/bin/activate
$ pip install .
~~~

### Use
#### run service with root
~~~
$ dbar4gun
~~~

## To Do

1. Update README
2. Smoothed axes
3. Support nunchuck

## References

The wiimote report format is not open and had to be reverse engineered. These resources have been very helpful when creating dbar4gun:

- <https://www.wiibrew.org/wiki/Wiimote>
- <https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL>
