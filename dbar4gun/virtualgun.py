import re
import os
import evdev

VIRTUALGUN_BUTTON_TWO_MASK   = 1 << 0x0
VIRTUALGUN_BUTTON_ONE_MASK   = 1 << 0x1
VIRTUALGUN_BUTTON_B_MASK     = 1 << 0x2
VIRTUALGUN_BUTTON_A_MASK     = 1 << 0x3
VIRTUALGUN_BUTTON_MINUS_MASK = 1 << 0x4

VIRTUALGUN_BUTTON_UNK_03     = 1 << 0x5
VIRTUALGUN_BUTTON_UNK_04     = 1 << 0x6

VIRTUALGUN_BUTTON_HOME_MASK  = 1 << 0x7

VIRTUALGUN_BUTTON_LEFT_MASK  = 1 << 0x8
VIRTUALGUN_BUTTON_RIGHT_MASK = 1 << 0x9
VIRTUALGUN_BUTTON_DOWN_MASK  = 1 << 0xa
VIRTUALGUN_BUTTON_UP_MASK    = 1 << 0xb
VIRTUALGUN_BUTTON_PLUS_MASK  = 1 << 0xc

VIRTUALGUN_CORE_BUTTON_UNK_00 = 1 << 0xd
VIRTUALGUN_CORE_BUTTON_UNK_01 = 1 << 0xe
VIRTUALGUN_CORE_BUTTON_UNK_02 = 1 << 0xf

VIRTUALGUN_BUTTON_Z_MASK = 1 << 0
VIRTUALGUN_BUTTON_C_MASK = 1 << 1

_X = 0
_Y = 1

_MAP_INDEX_LEFT  =  0
_MAP_INDEX_RIGHT =  1
_MAP_INDEX_DOWN  =  2
_MAP_INDEX_UP    =  3
_MAP_INDEX_PLUS  =  4
_MAP_INDEX_MINUS =  5
_MAP_INDEX_A     =  6
_MAP_INDEX_Z     =  7
_MAP_INDEX_C     =  8
_MAP_INDEX_MAX   =  9


_MAP = [
    # gun 1
    evdev.ecodes.KEY_LEFT,         evdev.ecodes.KEY_RIGHT,
    evdev.ecodes.KEY_DOWN,         evdev.ecodes.KEY_UP,
    evdev.ecodes.KEY_1,            evdev.ecodes.KEY_5,
    evdev.ecodes.KEY_LEFTALT,      evdev.ecodes.KEY_B,
    evdev.ecodes.KEY_LEFTSHIFT,

    # gun 2
    evdev.ecodes.KEY_D,            evdev.ecodes.KEY_G,
    evdev.ecodes.KEY_F,            evdev.ecodes.KEY_R,
    evdev.ecodes.KEY_2,            evdev.ecodes.KEY_6,
    evdev.ecodes.KEY_S,            evdev.ecodes.KEY_Q,
    evdev.ecodes.KEY_W,

    # gun 3
    evdev.ecodes.KEY_J,            evdev.ecodes.KEY_L,
    evdev.ecodes.KEY_K,            evdev.ecodes.KEY_I,
    evdev.ecodes.KEY_3,            evdev.ecodes.KEY_7,
    evdev.ecodes.KEY_RIGHTSHIFT,   evdev.ecodes.KEY_ENTER,
    evdev.ecodes.KEY_KP1,

    # gun 4
    evdev.ecodes.KEY_KP4,          evdev.ecodes.KEY_KP6,
    evdev.ecodes.KEY_KP2,          evdev.ecodes.KEY_KP8,
    evdev.ecodes.KEY_4,            evdev.ecodes.KEY_8,
    evdev.ecodes.KEY_KPDOT,        evdev.ecodes.KEY_KPENTER,
    evdev.ecodes.KEY_KP5,
]

class VirtualGunDevice(object):
    NUNCHUK_JOY_TOLERANCE = 0.2
    NUNCHUK_JOY_NEUTRAL   = 0.5

    def __init__(self, width : int, height : int, port: int):
        self.cursor           = [0.5, 0.5]
        self.buttons          = 0x00
        self.nunchuck_joy     = [0.5, 0.5]
        self.nunchuck_buttons = 0xff
        self.index            = port
        self.index_map        = 0
        self.width            = width
        self.height           = height

    def __get_capabilities(self):

        gun_cap = {
            evdev.ecodes.EV_KEY: [
                evdev.ecodes.BTN_LEFT,           # WIIMOTE BUTTON B
                evdev.ecodes.BTN_RIGHT,          # WIIMOTE BUTTON A
                evdev.ecodes.BTN_MIDDLE,         # WIIMOTE BUTTON ONE
                evdev.ecodes.KEY_F1,             # WIIMOTE BUTTON HOME

                # combos
                evdev.ecodes.KEY_ENTER,  # b + plus
                evdev.ecodes.KEY_ESC,    # b + minus
                evdev.ecodes.KEY_TAB,    # b + home
                evdev.ecodes.KEY_SPACE,  # b + 1
                evdev.ecodes.KEY_2,      # b + 2
            ] + _MAP,
            evdev.ecodes.EV_ABS: [
                # mouse cursor
                (evdev.ecodes.ABS_X, evdev.AbsInfo(value=0,
                        min=0, max=self.width, fuzz=0, flat=0, resolution=0)),
                (evdev.ecodes.ABS_Y, evdev.AbsInfo(value=0,
                        min=0, max=self.height, fuzz=0, flat=0, resolution=0)),
            ],
        }

        return gun_cap

    def get_real_mouse(self) -> int:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

        dev_c = 0
        for dev in devices:
            # solo cantamos los que no sean virtualgun
            if "virtualgun" in dev.name.lower():
                continue

            event = os.path.basename(dev.path)
            for entry in os.listdir(f"/sys/class/input/{event}/device/"):
                if "mouse" in entry:
                    dev_c = dev_c + 1
                    break

        return dev_c


    def create_virtual_device(self) -> int:
        gunname = "VirtualGun {:02}".format(self.index + 1)
        self.virtualgun = evdev.UInput(self.__get_capabilities(),
                                    name=gunname)
        print(gunname)
        # print(self.virtualgun.capabilities(verbose=True))

        l   = len(_MAP) // _MAP_INDEX_MAX
        off = ( ( self.index ) % l ) * _MAP_INDEX_MAX

        self.index_map = off

        # inportante debajo del off, para no tener en cuenta
        # el index para los botones.
        # agregamos los mouse reales a los indices
        index = self.get_real_mouse() + self.index

        return index + 1

    def set_buttons(self, buttons, nunchuck_buttons, nunchuck_joy):
        self.buttons          = buttons
        self.nunchuck_joy     = nunchuck_joy
        self.nunchuck_buttons = nunchuck_buttons

    def set_cursor(self, cursor):
        self.cursor = cursor

    def get_nunchuk_direction(self):

        x, y = self.nunchuck_joy

        if x < self.NUNCHUK_JOY_NEUTRAL - self.NUNCHUK_JOY_TOLERANCE:
            left = True
        else:
            left = False

        if x > self.NUNCHUK_JOY_NEUTRAL + self.NUNCHUK_JOY_TOLERANCE:
            right = True
        else:
            right = False

        if y < self.NUNCHUK_JOY_NEUTRAL - self.NUNCHUK_JOY_TOLERANCE:
            down = True
        else:
            down = False

        if y > self.NUNCHUK_JOY_NEUTRAL + self.NUNCHUK_JOY_TOLERANCE:
            up   = True
        else:
            up   = False

        return [left, right, up, down]

    def sync(self) -> None:
        nunchuck_dir = self.get_nunchuk_direction()

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_LEFT],
                (bool(self.buttons & VIRTUALGUN_BUTTON_LEFT_MASK)) | nunchuck_dir[0])
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_RIGHT],
                (bool(self.buttons & VIRTUALGUN_BUTTON_RIGHT_MASK)) | nunchuck_dir[1])
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_UP],
                (bool(self.buttons & VIRTUALGUN_BUTTON_UP_MASK)) | nunchuck_dir[2])
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_DOWN],
                (bool(self.buttons & VIRTUALGUN_BUTTON_DOWN_MASK)) | nunchuck_dir[3])

        # cursor
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_X, int(self.cursor[_X] * self.width))
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_Y, int(self.cursor[_Y] * self.height))

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_C],
                (bool(self.nunchuck_buttons & VIRTUALGUN_BUTTON_C_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_Z],
                (bool(self.nunchuck_buttons & VIRTUALGUN_BUTTON_Z_MASK)))

        # with combo
        button_a     = (bool(self.buttons & VIRTUALGUN_BUTTON_A_MASK))
        button_b     = (bool(self.buttons & VIRTUALGUN_BUTTON_B_MASK))
        button_home  = (bool(self.buttons & VIRTUALGUN_BUTTON_HOME_MASK))
        button_one   = (bool(self.buttons & VIRTUALGUN_BUTTON_ONE_MASK))
        button_two   = (bool(self.buttons & VIRTUALGUN_BUTTON_TWO_MASK))
        button_plus  = (bool(self.buttons & VIRTUALGUN_BUTTON_PLUS_MASK))
        button_minus = (bool(self.buttons & VIRTUALGUN_BUTTON_MINUS_MASK))

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_F1,    button_a & button_home)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_ESC,   button_b & button_minus)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_TAB,   button_b & button_home)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_SPACE, button_b & button_one)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_2,     button_b & button_two)

        if button_b  & button_home  or \
            button_b & button_plus  or \
            button_b & button_minus or \
            button_b & button_one   or \
            button_b & button_two   or \
            button_a & button_home  or \
            button_a & button_plus  or \
            button_a & button_minus:
            self.virtualgun.syn()
            return

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_ENTER,                  button_home)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_LEFT,                   button_b)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_MIDDLE,                 button_one)

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_RIGHT,                  button_two)

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_A],     button_a)

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_PLUS],  button_plus)
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_MINUS], button_minus)

        self.virtualgun.syn()

