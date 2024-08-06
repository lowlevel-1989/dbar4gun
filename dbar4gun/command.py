import os
import sys
import signal
import argparse

PATH_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PATH_ROOT)

from dbar4gun import info
from dbar4gun import calibration
from dbar4gun import irsetup

from dbar4gun.dbar4gun   import Dbar4Gun
from dbar4gun.wiimote    import WiiMoteDevice
from dbar4gun.virtualgun import VirtualGunDevice
from dbar4gun.monitor    import Monitor

DBAR4GUN_DESC = """
dbar4gun is a Linux userspace driver for the wiimote with DolphinBar support,
specifically designed to be small and function as 4 light guns.
"""

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

class Command(object):
    def __init__(self):
        self.dbar4gun = None

        signal.signal(signal.SIGINT,  self.free)
        signal.signal(signal.SIGTERM, self.free)

    def add_start_arguments(self, parser):
        parser.add_argument('--calibration',     type=int, default=2,  choices=range(len(CALIBRATION_LIST)), help=CALIBRATION_HELP)
        parser.add_argument('--setup',           type=int, default=1,  choices=range(1, len(IR_SETUP_LIST)), help=IR_SETUP_HELP)
        parser.add_argument("--width",           type=int, default=1920, help="1920")
        parser.add_argument("--height",          type=int, default=1080, help="1080")
        parser.add_argument("--disable-tilt-correction", action='store_true')
        parser.add_argument("--port",            type=int, default=35460, help="35460")
        parser.add_argument("--smoothing-level", type=int, default=5,     help="5 (default)")

    def parser(self):
        parser = argparse.ArgumentParser(
                    prog=info.__title__,
                    formatter_class=argparse.RawTextHelpFormatter,
                    description=DBAR4GUN_DESC)

        subparsers = parser.add_subparsers(dest="command")

        command_start   = subparsers.add_parser("start")
        command_attach  = subparsers.add_parser("attach")
        command_stop    = subparsers.add_parser("stop")
        command_version = subparsers.add_parser("version")
        command_gui     = subparsers.add_parser("gui")

        self.add_start_arguments(parser)
        self.add_start_arguments(command_start)
        self.add_start_arguments(command_attach)

        command_attach.add_argument("device",  type=str, help="wiimote device (/dev/hidraw0)")

        command_gui.add_argument("--width",  type=int, default=1280,  help="1280")
        command_gui.add_argument("--height", type=int, default=720,   help="720")
        command_gui.add_argument("--port",   type=int, default=35460, help="35460")

        config = parser.parse_args()

        command = "start"
        if config.command:
            command = config.command

        if command == "version":
            print("{} v{}".format(info.__title__,  info.__version__))
            exit(0)

        print("{} v{}".format(info.__title__,  info.__version__))
        print("\t\t{}".format(info.__repo___))

        if command == "gui":
            from dbar4gun.gui import GUI

            gui = GUI(width=config.width, height=config.height, port=config.port)

            gui.open()
            gui.loop()
            gui.close()

            exit(0)

        if os.geteuid() > 0:
            print("user root is required")
            exit(1)

        if config.smoothing_level < 1:
            config.smoothing_level = 1

        Calibration = calibration.CalibrationDummy
        if config.calibration < len(CALIBRATION_LIST):
            Calibration = CALIBRATION_LIST[config.calibration]

        IRSetup = irsetup.IRSetupStandard
        if config.setup < len(IR_SETUP_LIST):
            IRSetup = IR_SETUP_LIST[config.setup]

        self.dbar4gun = Dbar4Gun(
                            config,
                            Monitor,
                            WiiMoteDevice,
                            VirtualGunDevice,
                            Calibration,
                            IRSetup)

        if command == "stop":
            if self.dbar4gun.kill() <= 0:
                print("Ok")
                exit(0)
            else:
                exit(1)

        if command == "attach":
            self.dbar4gun.create_virtualgun(config.device, attach=True)
            self.dbar4gun.stop()
            exit(0)

        self.dbar4gun.run()

    def free(self, SignalNumber, Frame):
        if self.dbar4gun:
            self.dbar4gun.stop()
        exit(0)

def dbar4gun_run():
    command = Command()
    command.parser()
    command.free()

if __name__ == '__main__':
    dbar4gun_run()
