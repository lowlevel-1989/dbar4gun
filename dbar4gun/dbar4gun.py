import time
import sys
import io
import os
import signal
import argparse

from io          import FileIO
from collections import deque

from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Lock

PATH_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PATH_ROOT)

from dbar4gun            import info
from dbar4gun            import calibration
from dbar4gun.wiimote    import WiiMoteDevice
from dbar4gun.virtualgun import VirtualGunDevice
from dbar4gun.monitor    import Monitor

__main_pid  = os.getpid()
__hidraw_io = []
__workers   = []
__queue     = Queue()

def virtualgun_worker(hidraw_io, lock, config, Calibration):

    wiimote = WiiMoteDevice(hidraw_io, Calibration, config.width, config.height)

    # virtualgun -> mouse / key
    virtualgun = VirtualGunDevice(config.width, config.height)
    time.sleep(0.1)
    lock.release()

    while 1:
        index = virtualgun.get_index()
        if wiimote.update_index(index):
            virtualgun.create_virtual_device()
            break
        time.sleep(0.3)

    try:
        history_x = deque(maxlen=config.smoothing_level)
        history_y = deque(maxlen=config.smoothing_level)

        while 1:
            wiimote.check_is_alive()
            buttons, ir, nunchuck = wiimote.read()
            history_x.append(ir["pos_mid_nor"][0])
            history_y.append(ir["pos_mid_nor"][1])

            ir["pos_mid_nor"][0] = sum(history_x) / config.smoothing_level
            ir["pos_mid_nor"][1] = sum(history_y) / config.smoothing_level

            cursor = wiimote.get_cursor_position(ir)

            virtualgun.set_buttons(buttons, nunchuck)
            virtualgun.set_cursor(cursor)
            virtualgun.sync()
    except Exception as e:
        print(e)
    finally:
        print("bye VirtualGun {:03X}".format(wiimote.player))

def remove_virtualgun_worker(hidraw_path, lock):
    pass

def create_virtualgun_worker(hidraw_path, lock, config, Calibration):
    lock.acquire()

    fd        = os.open(hidraw_path, os.O_RDWR)
    hidraw_io = io.FileIO(fd, "rb+", closefd=False)

    worker = Process(
                target=virtualgun_worker, args=(hidraw_io, lock, config, Calibration))

    worker.start()

    __hidraw_io.append([fd, hidraw_io])
    __workers.append(worker)

def monitor_handle_events(queue, config, Calibration):

    # handle exceptions for (controlled termination)
    try:
        lock = Lock() # events, register new virtualgun device
        while 1:
            event = queue.get()
            if event[0] == "__EXIT__":
                break
            elif event[0] == "remove":
                remove_virtualgun_worker(event[1], lock)
            else:
                create_virtualgun_worker(event[1], lock, config, Calibration)

            print("monitor: {} {}".format(*event))
    except Exception as e:
        print(e)
    finally:
        free()
        print("bye monitor")

def free():
    for hidraw_io in __hidraw_io:
        try:
            hidraw_io[1].close()
            os.close(hidraw_io[0])
            print("free: {:04d} {}".format(hidraw_io[0], hidraw_io[2]),)

        except:
            pass

        for work in __workers:
            try:
                work.kill()
            except:
                pass

def SignalHandler(SignalNumber, Frame):
    free()
    exit(0)


def dbar4gun_run():

    if len(sys.argv) > 1 and sys.argv[1].lower() == "version":
        print("{} v{}".format(info.__title__,  info.__version__))
        exit(0)

    if os.path.exists("/var/run/dbar4gun.pid"):
        with open("/var/run/dbar4gun.pid", "r") as f:
            try:
                pid = int(f.readline())
                os.kill(pid, signal.SIGTERM)
                if len(sys.argv) > 1 and sys.argv[1].lower() == "stop":
                    print("ok")
                    exit(0)
            except Exception as e:
                print(e)
                exit(1)

    signal.signal(signal.SIGINT,  SignalHandler)
    signal.signal(signal.SIGTERM, SignalHandler)

    parser = argparse.ArgumentParser(
                prog=info.__title__,
                description="dbar4gun is a Linux userspace driver for the DolphinBar x4 Wiimote")

    parser.add_argument("--width",           type=int, default=1920, help="Width of the screen")
    parser.add_argument("--height",          type=int, default=1080, help="Width of the screen")
    parser.add_argument("--smoothing-level", type=int, default=3,    help="smoothing level")

    config = parser.parse_args()

    if config.smoothing_level < 1:
        config.smoothing_level = 1

    monitor = Monitor(queue = __queue)

    Calibration = calibration.CalibrationCenterTopLeftPoint

    monitor_event_process = Process(
            target=monitor_handle_events,
            args=(monitor.queue, config, Calibration))

    monitor_event_process.start()

    print("{} v{}".format(info.__title__,  info.__version__))
    print("\t\t{}".format(info.__repo___))
    print("\t\tSCREEN {}x{}".format(config.width, config.height))
    print("\t\tmonitor started, ctrl+c to exit or sudo kill -SIGTERM {}".format(__main_pid))

    with open("/var/run/dbar4gun.pid", "w") as f:
        f.write(str(__main_pid))

    # handle exceptions for (controlled termination)
    try:
        monitor.run()
    except:
        pass
    finally:
        __queue.put(["__EXIT__", "__EXIT__"])
        free()
        if os.path.exists("/var/run/dbar4gun.pid"):
            os.remove("/var/run/dbar4gun.pid")
        print("\nbye")

if __name__ == '__main__':
    dbar4gun_run()
