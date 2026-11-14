# daemon

English | [Español](README.es.md)

The service (`dbar4gun start`). It waits for Wiimotes and starts one process
(worker) for each one. The worker reads its Wiimote and moves its VirtualGun.

## One class in several files

`Dbar4Gun` (in `service.py`) is a single class. It is split by task: each
file has one part of the class, and `Dbar4Gun` joins them all:

```python
class Dbar4Gun(Options, Devices, Worker, SingleProcess, GunOrder, Commands):
```

Every part uses the same `self`. For example, `devices.py` calls
`self.store()`, which is in `options.py`.

| file          | what it does                                                        |
|---------------|---------------------------------------------------------------------|
| `service.py`  | `Dbar4Gun`: start (`run`), stop (`stop`), close the previous daemon (`kill`) |
| `options.py`  | options from the command line, `hardware.json` and `profiles.cfg`; options of the pipeline |
| `devices.py`  | Wiimotes that arrive and leave: creates and removes the workers     |
| `worker.py`   | the process of one Wiimote: pair, read, move the VirtualGun, answer commands |
| `commands.py` | control socket: `status`, `area`, `calibrate`, `hw`...              |
| `order.py`    | keeps the power-on order of the guns in RetroArch                   |
| `single.py`   | experimental `--single-process` mode: every Wiimote in one process  |

Helpers (functions, no part of the class):

| file         | what it does                                                         |
|--------------|----------------------------------------------------------------------|
| `ports.py`   | which VirtualGun (01, 02...) each Wiimote gets                       |
| `pidfile.py` | PID file; recognizes a previous daemon before stopping it            |
| `pipes.py`   | fork for the workers, and a pipe between threads for `single.py`     |

## What happens when a Wiimote is connected

1. `monitor.py` (udev) sees a new `hidraw` and puts it in the queue.
2. `devices.py` opens it, chooses its port (`ports.py`) and starts a worker.
3. `worker.py` waits until the Wiimote answers, creates its VirtualGun and
   then, for every report: reads the Wiimote, moves the VirtualGun and sends
   the UDP packet to the calibrator.
4. Every few seconds, `order.py` checks that RetroArch numbers the guns in the
   power-on order.

If a Bluetooth Wiimote is disconnected, its worker and its VirtualGun are kept
until the same Wiimote comes back (`devices.py`: detach / reattach). The game
does not lose the gun.

## Commands

`dbar4gun status`, the calibrator, etc. talk to the service through the
control socket (`control.py`). `commands.py` answers them. A command that
affects one Wiimote is sent to its worker through a pipe, and the worker
answers it in `worker.py` (`_worker_command`).
