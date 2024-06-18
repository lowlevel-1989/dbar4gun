import time

import io
import os
import signal
import argparse

from io import FileIO
from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Value

import info

from wiimote    import WiiMoteDevice
from virtualgun import VirtualGunDevice
from monitor    import Monitor

__main_pid  = os.getpid()
__hidraw_io = []
__workers   = []

config = None

def virtualgun_worker(hidraw_io):
    player = Value("i", 0)

    wiimote = WiiMoteDevice(hidraw_io, player, config.width, config.height)

    # virtualgun -> mouse / joy
    virtualgun = VirtualGunDevice(player, config.width, config.height)

    while 1:
        button, ir = wiimote.read()
        cursor = wiimote.get_cursor_position()
        virtualgun.set_cursor(cursor)
        virtualgun.sync()

        print(cursor)

def remove_virtualgun_worker(hidraw_path):
    pass

def create_virtualgun_worker(hidraw_path):
    fd        = os.open(hidraw_path, os.O_RDWR)
    hidraw_io = io.FileIO(fd, "rb+", closefd=False)

    worker = Process(
                target=virtualgun_worker, args=(hidraw_io,))

    worker.start()

    __hidraw_io.append([fd, hidraw_io])
    __workers.append(worker)

def monitor_handle_events(queue):
    # handle exceptions for (controlled termination)
    try:
        while 1:
            event = queue.get()
            if event[0] == "remove":
                remove_virtualgun_worker(event[1])
            else:
                create_virtualgun_worker(event[1])

            print("monitor: {} {}".format(*event))
    except:
        pass
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

def SignalHandler(SignalNumber, Frame):
    print()
    free()

    # wait finish main process
    if __main_pid == os.getpid() and __main_pid == os.getpid():
        monitor_event_process.join()
    exit(0)

if __name__ == '__main__':
    print("{} v{}".format(info.__title__,  info.__version__))
    print("\t\tmonitor started, ctrl+c to exit.")

    signal.signal(signal.SIGINT,  SignalHandler)
    signal.signal(signal.SIGTERM, SignalHandler)

    parser = argparse.ArgumentParser(
                prog=info.__title__,
                description="dbar4gun is a Linux userspace driver for the DolphinBar x4 Wiimote")

    parser.add_argument("--width",  type=int, default=1920, help="Width of the screen")
    parser.add_argument("--height", type=int, default=1080, help="Width of the screen")

    config = parser.parse_args()

    monitor = Monitor(queue = Queue())

    monitor_event_process = Process(
            target=monitor_handle_events, args=(monitor.queue,))

    monitor_event_process.start()

    # handle exceptions for (controlled termination)
    try:
        monitor.run()
    except:
        pass
    finally:
        free()
        print("bye")
