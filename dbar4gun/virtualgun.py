import evdev
import uuid

VIRTUALGUN_BUTTON_LEFT_MASK  = 0x01
VIRTUALGUN_BUTTON_RIGHT_MASK = 0x02
VIRTUALGUN_BUTTON_DOWN_MASK  = 0x04
VIRTUALGUN_BUTTON_UP_MASK    = 0x08
VIRTUALGUN_BUTTON_PLUS_MASK  = 0x10

VIRTUALGUN_BUTTON_TWO_MASK   = 0x01
VIRTUALGUN_BUTTON_ONE_MASK   = 0x02
VIRTUALGUN_BUTTON_B_MASK     = 0x04
VIRTUALGUN_BUTTON_A_MASK     = 0x08
VIRTUALGUN_BUTTON_MINUS_MASK = 0x10
VIRTUALGUN_BUTTON_HOME_MASK  = 0x80

_X = 0
_Y = 1

class VirtualGunDevice(object):
    def __init__(self, player, width, height):
        self.player = player
        self.cursor = [0, 0]

        gun_cap = {
            evdev.ecodes.EV_KEY: [evdev.ecodes.BTN_LEFT, evdev.ecodes.BTN_RIGHT],
            evdev.ecodes.EV_ABS: [
                (evdev.ecodes.ABS_X, evdev.AbsInfo(value=0,
                        min=0, max=width, fuzz=0, flat=0, resolution=0)),
                (evdev.ecodes.ABS_Y, evdev.AbsInfo(value=0,
                        min=0, max=height, fuzz=0, flat=0, resolution=0)),
            ]
        }

        self.virtualgun = evdev.UInput(gun_cap, name="VirtualGun {}".format(uuid.uuid1()))

        print(self.virtualgun.device.path)

    def set_cursor(self, cursor):
        self.cursor = cursor

    def sync(self):
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_X, self.cursor[_X])
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_Y, self.cursor[_Y])
        self.virtualgun.syn()

