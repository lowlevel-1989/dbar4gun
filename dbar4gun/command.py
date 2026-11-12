import os
import sys
import signal
import argparse
import logging

PATH_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# E9: al final, para no tapar los paquetes del venv con los del sistema
sys.path.append("/usr/lib/python3/dist-packages")
sys.path.append(PATH_ROOT)

from dbar4gun import info
from dbar4gun import calibration
from dbar4gun import irsetup

from dbar4gun.dbar4gun   import Dbar4Gun
from dbar4gun.wiimote    import WiiMoteDevice
from dbar4gun.virtualgun import VirtualGunDevice
from dbar4gun.monitor    import Monitor
from dbar4gun.control    import SOCKET_PATH, send_command
from dbar4gun.core.area  import AreaProfile
from dbar4gun.core.gun   import DEFAULT_USEFUL_ZONE, parse_targets

DBAR4GUN_DESC = """
dbar4gun is a Linux userspace driver for the wiimote with DolphinBar support,
specifically designed to be small and function as 4 light guns.
"""

# --setup N usa IR_SETUP_LIST[N - 1]
IR_SETUP_LIST = [
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
3: TopLeft, TopRight, BottomRight, BottomLeft (homography)
"""


USEFUL_ZONE_RANGE = (0.3, 1.0)


def validate_options(area, useful_zone, aspect=16.0 / 9.0):
    """ValueError si el area profile o la useful zone no valen (start y check)."""
    if not area or not area.strip():
        raise ValueError("area: empty (full, 4:3 or custom:x0,y0,w,h)")
    AreaProfile.parse(area, aspect)
    if not USEFUL_ZONE_RANGE[0] <= useful_zone <= USEFUL_ZONE_RANGE[1]:
        raise ValueError("useful zone: {} .. {}".format(*USEFUL_ZONE_RANGE))

class Command(object):
    def __init__(self):
        self.dbar4gun = None

        signal.signal(signal.SIGINT,  self.free)
        signal.signal(signal.SIGTERM, self.free)

    def add_start_arguments(self, parser):
        parser.add_argument('--calibration',     type=int, default=2,  choices=range(4), help=CALIBRATION_HELP)
        parser.add_argument('--setup',           type=int, default=1,  choices=range(1, len(IR_SETUP_LIST) + 1), help=IR_SETUP_HELP)
        parser.add_argument("--width",           type=int, default=1920, help="1920")
        parser.add_argument("--height",          type=int, default=1080, help="1080")
        parser.add_argument("--disable-tilt-correction", action='store_true')
        parser.add_argument("--port",            type=int, default=35460, help="35460")
        parser.add_argument("--smoothing-level", type=int, default=3,
                            help="One Euro filter: 0 = off, 3 = default, higher = smoother")
        parser.add_argument("--no-distance-compensation", action="store_true",
                            help="disable distance compensation (C9)")
        parser.add_argument("--area",            type=str, default="full",
                            help="gun area profile: full (default), 4:3, custom:x0,y0,w,h")
        parser.add_argument("--useful-zone",     type=float, default=DEFAULT_USEFUL_ZONE,
                            help="fraction of the screen height with targets ({} default)".format(DEFAULT_USEFUL_ZONE))
        parser.add_argument("--bar",             type=str, default="top", choices=["top", "bottom"],
                            help="sensor bar position: top (default) or bottom")
        parser.add_argument("--calibration-targets", type=str, default=None,
                            help="3-point targets in gun space: x1,y1,x2,y2,x3,y3")
        parser.add_argument("--config-dir",      type=str, default=None,
                            help="config directory (default: RetroPie configs, else /var/lib/dbar4gun)")
        parser.add_argument("--socket",          type=str, default=SOCKET_PATH, help=SOCKET_PATH)
        parser.add_argument("--log-level", type=str, default="info",
                            choices=["debug", "info", "warning", "error"],
                            help="log level (stderr, journald)")
        parser.add_argument("--ir-sensitivity", type=str, default="marcan",
                            choices=["1", "2", "3", "4", "5", "marcan", "cliff"],
                            help="IR camera sensitivity (wiibrew levels), marcan = v0.18 default")
        parser.add_argument("--single-process", action="store_true",
                            help="experimental: one process reads every Wiimote with select")
        parser.add_argument("--experimental-ir-extended", action="store_true",
                            help="allow 'irmode extended' (dot size, report 0x33, no Nunchuk); unverified")

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

        # P1: comandos al daemon por el socket de control
        command_area      = subparsers.add_parser("area",      help="set the gun area profile")
        command_status    = subparsers.add_parser("status",    help="print the daemon status (JSON)")
        command_calibrate = subparsers.add_parser("calibrate", help="start a calibration")
        command_cancel    = subparsers.add_parser("cancel",    help="cancel running calibrations")
        command_reload    = subparsers.add_parser("reload",    help="reload saved calibrations")
        command_check     = subparsers.add_parser("check",     help="validate option values (exit 2 if invalid)")
        command_check.add_argument("--area", type=str, default="full")
        command_check.add_argument("--useful-zone", type=float, default=DEFAULT_USEFUL_ZONE)
        command_hw        = subparsers.add_parser("hw",        help="show or set the measured hardware values")
        command_hw.add_argument("values", nargs="*",
                                help="fov <deg> | acc_x_sign <1|-1> | bar_width <m> (pairs)")

        # P2: runcommand de RetroPie
        command_profile = subparsers.add_parser("profile", help="apply the area profile of a game (runcommand)")
        command_profile.add_argument("event", choices=["start", "end"])
        command_profile.add_argument("system",   nargs="?", default="")
        command_profile.add_argument("emulator", nargs="?", default="")
        command_profile.add_argument("rom",      nargs="?", default="")
        command_profile.add_argument("--profiles", type=str, default=None,
                                     help="profiles.cfg (default: <config dir>/profiles.cfg)")
        command_profile.add_argument("--socket", type=str, default=SOCKET_PATH, help=SOCKET_PATH)

        command_hooks = subparsers.add_parser("hooks", help="install/uninstall the runcommand hooks")
        command_hooks.add_argument("action", choices=["install", "uninstall"])
        command_hooks.add_argument("--configs-dir", type=str, default="/opt/retropie/configs/all")
        command_hooks.add_argument("--bin", type=str, default=None, help="dbar4gun executable used by the hooks")

        command_area.add_argument("profile", type=str, help="full, 4:3, custom:x0,y0,w,h")
        command_calibrate.add_argument("virtualgun", type=int, nargs="?", help="VirtualGun number (all if omitted)")
        command_calibrate.add_argument("--quick", action="store_true", help="2-point recalibration")
        for c in (command_area, command_status, command_calibrate, command_cancel, command_reload, command_hw):
            c.add_argument("--socket", type=str, default=SOCKET_PATH, help=SOCKET_PATH)

        self.add_start_arguments(parser)
        self.add_start_arguments(command_start)
        self.add_start_arguments(command_attach)

        command_attach.add_argument("device",  type=str, help="wiimote device (/dev/hidraw0)")

        command_gui.add_argument("--width",  type=int, default=0,     help="0 = native resolution")
        command_gui.add_argument("--height", type=int, default=0,     help="0 = native resolution")
        command_gui.add_argument("--port",   type=int, default=35460, help="35460")
        command_gui.add_argument("--windowed", action="store_true", help="window instead of full screen")
        command_gui.add_argument("--socket", type=str, default=SOCKET_PATH, help=SOCKET_PATH)

        config = parser.parse_args()

        command = "start"
        if config.command:
            command = config.command

        if command == "version":
            print("{} v{}".format(info.__title__,  info.__version__))
            exit(0)

        if command in ("area", "status", "calibrate", "cancel", "reload", "hw"):
            exit(self.client(command, config))

        if command == "check":
            try:
                validate_options(config.area, config.useful_zone)
            except ValueError as e:
                print(e)
                exit(2)
            print("ok")
            exit(0)

        if command == "profile":
            exit(self.profile(config))

        if command == "hooks":
            exit(self.hooks(config))

        print("{} v{}".format(info.__title__,  info.__version__))
        print("\t\t{}".format(info.__repo___))

        if command == "gui":
            from dbar4gun.gui import GUI

            gui = GUI(width=config.width, height=config.height, port=config.port,
                      fullscreen=not config.windowed, socket_path=config.socket)

            gui.open()
            gui.loop()
            gui.close()

            exit(0)

        # E10: logging con niveles (journald recoge stderr)
        logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO),
                            format="%(levelname)s %(name)s: %(message)s")

        if os.geteuid() > 0:
            print("user root is required")
            exit(1)

        # 0 desactiva el filter (C13)
        if config.smoothing_level < 0:
            config.smoothing_level = 0

        try:
            validate_options(config.area, config.useful_zone,
                             float(config.width) / float(config.height))
            if config.calibration_targets:
                parse_targets(config.calibration_targets)
        except ValueError as e:
            print(e)
            exit(2)

        Calibration = calibration.CalibrationDummy
        if config.calibration < len(CALIBRATION_LIST):
            Calibration = CALIBRATION_LIST[config.calibration]

        IRSetup = IR_SETUP_LIST[config.setup - 1]

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

    def client(self, command, config):
        import json

        line = command
        if command == "area":
            line = "area {}".format(config.profile)
        elif command == "calibrate":
            if config.virtualgun:
                line += " {}".format(config.virtualgun)
            line += " quick" if config.quick else " full"
        elif command == "hw" and config.values:
            line += " " + " ".join(config.values)

        try:
            reply = send_command(line, config.socket)
        except (OSError, ValueError) as e:
            print("dbar4gun daemon not reachable ({}): {}".format(config.socket, e))
            return 1

        print(json.dumps(reply, indent=2, sort_keys=True))
        return 0 if reply.get("ok") else 1

    def profile(self, config):
        from dbar4gun import profiles

        path = config.profiles
        if not path:
            # el profiles.cfg del daemon (su --config-dir), si responde
            try:
                path = send_command("status", config.socket).get("profiles")
            except (OSError, ValueError):
                path = None
        path = path or profiles.default_profiles_path()
        table = profiles.load_profiles(path)
        if config.event == "start":
            area = profiles.resolve_profile(table, config.system, config.emulator, config.rom)
        else:
            area = profiles.resolve_profile(table)
        try:
            reply = send_command("area {}".format(area), config.socket)
        except (OSError, ValueError) as e:
            print("dbar4gun daemon not reachable ({}): {}".format(config.socket, e))
            return 1
        print("area {}: {}".format(area, "ok" if reply.get("ok") else reply.get("error")))
        return 0 if reply.get("ok") else 1

    def hooks(self, config):
        from dbar4gun import profiles

        try:
            if config.action == "install":
                bin_path = config.bin or os.path.abspath(sys.argv[0])
                touched = profiles.install_hooks(config.configs_dir, bin_path)
            else:
                touched = profiles.uninstall_hooks(config.configs_dir)
        except OSError as e:
            print("hooks: {}".format(e))
            return 1
        for path in touched:
            print(path)
        return 0

    def free(self, SignalNumber=-1, Frame=None):
        if self.dbar4gun:
            self.dbar4gun.stop()
        exit(0)

def dbar4gun_run():
    command = Command()
    command.parser()
    command.free()

if __name__ == '__main__':
    dbar4gun_run()
