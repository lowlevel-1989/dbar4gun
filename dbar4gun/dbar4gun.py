import time

import io
import os
import signal

from io import FileIO
from multiprocessing import Process, Queue

import info

from device  import WiiMoteDevice
from monitor import Monitor

__main_pid  = os.getpid()
__hidraw_io = []
__workers   = []

def virtualgun_worker(hidraw_io, queue):
    device = WiiMoteDevice(hidraw_io, Queue())

def remove_virtualgun_worker(hidraw_path):
    pass

def create_virtualgun_worker(hidraw_path):
    fd        = os.open(hidraw_path, os.O_RDWR | os.O_NONBLOCK)
    hidraw_io = io.FileIO(fd, "rb+", closefd=False)


    worker = Process(
                target=virtualgun_worker, args=(hidraw_io, Queue()))

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
    if monitor_event_process.is_alive() and __main_pid == os.getpid():
        monitor_event_process.join()
    exit(0)

if __name__ == '__main__':
    print("{} v{}".format(info.__title__,  info.__version__))
    print("\t\tmonitor started, ctrl+c to exit.")

    signal.signal(signal.SIGINT,  SignalHandler)
    signal.signal(signal.SIGTERM, SignalHandler)

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
