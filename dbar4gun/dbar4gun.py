import time
import sys
import io
import os
import signal
import argparse
import struct
import socket

from io          import FileIO

from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Lock

PATH_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PATH_ROOT)

from dbar4gun            import info
from dbar4gun            import calibration
from dbar4gun            import irsetup
from dbar4gun.wiimote    import WiiMoteDevice
from dbar4gun.virtualgun import VirtualGunDevice
from dbar4gun.monitor    import Monitor


IR_SETUP_LIST = [
    irsetup.IRSetupStandard,
    irsetup.IRSetupStandard,
]

IR_SETUP_HELP = """
mode
1: Standard (sensorbar, dolphinbar)
"""

CALIBRATION_LIST = [
    calibration.CalibrationDummy,
    calibration.CalibrationCenterTopLeftPoint,
    calibration.CalibrationTopLeftTopRightBottomCenterPoint,
]

CALIBRATION_HELP = """
mode
0: disabled
1: Center,  TopLeft
2: TopLeft, TopRight, BottomCenter (default)
"""

STRUCT_DATA       = "!BH12e12e2e"
STRUCT_DATA_SIZE  = struct.calcsize(STRUCT_DATA)

__main_pid  = os.getpid()
__hidraw_io = []
__workers   = []
__queue     = Queue()

__sock      = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def virtualgun_worker(hidraw_io, lock, config, Calibration, IRSetup):

    wiimote = WiiMoteDevice(hidraw_io, Calibration, IRSetup)
    wiimote.set_tilt_correction(not config.disable_tilt_correction)

    # virtualgun -> mouse / key
    virtualgun = VirtualGunDevice(config.width, config.height)
    time.sleep(0.1)
    lock.release()

    index = 0
    while 1:
        # test conexion con wiimote
        if wiimote.update_index(0xf):
            index = virtualgun.create_virtual_device()
            # update index
            wiimote.update_index(index)
            break
        time.sleep(0.3)

    try:

        while 1:
            wiimote.check_is_alive()
            buttons, ir_raw, ir, acc, nunchuck_buttons, nunchuck_joy = wiimote.read()

            cursor = wiimote.get_cursor()

            data = struct.pack(STRUCT_DATA,
                        index, buttons,
                        ir_raw[0][0], ir_raw[0][1], ir_raw[0][2],
                        ir_raw[1][0], ir_raw[1][1], ir_raw[1][2],
                        ir_raw[2][0], ir_raw[2][1], ir_raw[2][2],
                        ir_raw[3][0], ir_raw[3][1], ir_raw[3][2],
                        ir[0][0],     ir[0][1],     ir[0][2],
                        ir[1][0],     ir[1][1],     ir[1][2],
                        ir[2][0],     ir[2][1],     ir[2][2],
                        ir[3][0],     ir[3][1],     ir[3][2],
                        cursor[0], cursor[1])

            __sock.sendto(data, ("127.0.0.1", config.port))

            virtualgun.set_buttons(buttons, nunchuck_buttons, nunchuck_joy)
            virtualgun.set_cursor(cursor)
            virtualgun.sync()
    except Exception as e:
        print(e)
    finally:
        print("bye VirtualGun {:03X}".format(wiimote.player))

def remove_virtualgun_worker(hidraw_path, lock):
    pass

def create_virtualgun_worker(hidraw_path, lock, config, Calibration, IRSetup):
    lock.acquire()

    fd        = os.open(hidraw_path, os.O_RDWR)
    hidraw_io = io.FileIO(fd, "rb+", closefd=False)

    worker = Process(
                target=virtualgun_worker, args=(hidraw_io, lock, config, Calibration, IRSetup))

    worker.start()

    __hidraw_io.append([fd, hidraw_io])
    __workers.append(worker)

def monitor_handle_events(queue, config, Calibration, IRSetup):

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
                create_virtualgun_worker(event[1], lock, config, Calibration, IRSetup)

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
            __sock.close()
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

def add_start_arguments(parser):
    parser.add_argument('--calibration',     type=int, default=2,  choices=range(len(CALIBRATION_LIST)), help=CALIBRATION_HELP)
    parser.add_argument('--setup',           type=int, default=1,  choices=range(1, len(IR_SETUP_LIST)), help=IR_SETUP_HELP)
    parser.add_argument("--width",           type=int, default=1920, help="1920")
    parser.add_argument("--height",          type=int, default=1080, help="1080")
    parser.add_argument("--disable-tilt-correction", action='store_true')
    parser.add_argument("--port",            type=int, default=35460, help="35460")

def dbar4gun_run():

    DBAR4GUN_DESC = """
dbar4gun is a Linux userspace driver for the wiimote with DolphinBar support,
specifically designed to be small and function as 4 light guns.
    """

    print("{} v{}".format(info.__title__,  info.__version__))
    print("\t\t{}".format(info.__repo___))


    parser = argparse.ArgumentParser(
                prog=info.__title__,
                formatter_class=argparse.RawTextHelpFormatter,
                description=DBAR4GUN_DESC)

    subparsers = parser.add_subparsers(dest="command")

    command_start   = subparsers.add_parser("start")
    command_stop    = subparsers.add_parser("stop")
    command_version = subparsers.add_parser("version")
    command_gui     = subparsers.add_parser("gui")

    add_start_arguments(parser)
    add_start_arguments(command_start)

    command_gui.add_argument("--width",  type=int, default=1280,  help="1280")
    command_gui.add_argument("--height", type=int, default=720,   help="720")
    command_gui.add_argument("--port",   type=int, default=35460, help="35460")

    config = parser.parse_args()

    # TODO: optimize call from array
    command = "start"
    if config.command:
        command = config.command

    if command in ["start", "stop"] and os.path.exists("/var/run/dbar4gun.pid"):
        with open("/var/run/dbar4gun.pid", "r") as f:
            try:
                pid = int(f.readline())
                os.kill(pid, signal.SIGTERM)
                if command == "stop":
                    print("ok")
                    exit(0)
            except Exception as e:
                print(e)
                exit(1)

    if command == "version":
        print("{} v{}".format(info.__title__,  info.__version__))
        exit(0)

    elif command == "gui":
        from dbar4gun.gui import GUI

        gui = GUI(width=config.width, height=config.height, port=config.port)

        gui.open()
        gui.loop()
        gui.close()

        exit(0)

    if os.geteuid() > 0:
        print("user root is required")
        exit(1)

    print("\t\tSCREEN {}x{}".format(config.width, config.height))
    print("\t\tmonitor started, ctrl+c to exit or sudo kill -SIGTERM {}".format(__main_pid))

    signal.signal(signal.SIGINT,  SignalHandler)
    signal.signal(signal.SIGTERM, SignalHandler)

    monitor = Monitor(queue = __queue)

    Calibration = calibration.CalibrationDummy
    if config.calibration < len(CALIBRATION_LIST):
        Calibration = CALIBRATION_LIST[config.calibration]

    IRSetup = irsetup.IRSetupStandard
    if config.setup < len(IR_SETUP_LIST):
        IRSetup = IR_SETUP_LIST[config.setup]

    monitor_event_process = Process(
            target=monitor_handle_events,
            args=(monitor.queue, config, Calibration, IRSetup))

    monitor_event_process.start()

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
