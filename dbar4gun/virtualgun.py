import os
import evdev

VIRTUALGUN_BUTTON_LEFT_MASK   = 0x01
VIRTUALGUN_BUTTON_RIGHT_MASK  = 0x02
VIRTUALGUN_BUTTON_DOWN_MASK   = 0x04
VIRTUALGUN_BUTTON_UP_MASK     = 0x08
VIRTUALGUN_BUTTON_PLUS_MASK   = 0x10

VIRTUALGUN_BUTTON_TWO_MASK    = 0x01
VIRTUALGUN_BUTTON_ONE_MASK    = 0x02
VIRTUALGUN_BUTTON_B_MASK      = 0x04
VIRTUALGUN_BUTTON_A_MASK      = 0x08
VIRTUALGUN_BUTTON_MINUS_MASK  = 0x10
VIRTUALGUN_BUTTON_HOME_MASK   = 0x80

_X = 0
_Y = 1

# wiimote d-pad, stick
# wiimote plus
# wiimote minus

_MAP_INDEX_LEFT  = 0
_MAP_INDEX_RIGHT = 1
_MAP_INDEX_DOWN  = 2
_MAP_INDEX_UP    = 3
_MAP_INDEX_PLUS  = 4
_MAP_INDEX_MINUS = 5
_MAP_INDEX_TWO   = 6
_MAP_INDEX_ONE   = 7
_MAP_INDEX_MAX   = 8

# TODO: add 16 gun
_MAP = [
    # gun 1
    evdev.ecodes.KEY_LEFT,         evdev.ecodes.KEY_RIGHT,
    evdev.ecodes.KEY_DOWN,         evdev.ecodes.KEY_UP,
    evdev.ecodes.KEY_1,            evdev.ecodes.KEY_5,
    evdev.ecodes.KEY_B,            evdev.ecodes.KEY_SPACE,

    # gun 2
    evdev.ecodes.KEY_D,            evdev.ecodes.KEY_G,
    evdev.ecodes.KEY_F,            evdev.ecodes.KEY_R,
    evdev.ecodes.KEY_2,            evdev.ecodes.KEY_6,
    evdev.ecodes.KEY_S,            evdev.ecodes.KEY_Q,

    # gun 3
    evdev.ecodes.KEY_J,            evdev.ecodes.KEY_L,
    evdev.ecodes.KEY_K,            evdev.ecodes.KEY_I,
    evdev.ecodes.KEY_3,            evdev.ecodes.KEY_7,
    evdev.ecodes.KEY_RIGHTSHIFT,   evdev.ecodes.KEY_ENTER,

    # gun 4
    evdev.ecodes.KEY_KP4,          evdev.ecodes.KEY_KP6,
    evdev.ecodes.KEY_KP2,          evdev.ecodes.KEY_KP8,
    evdev.ecodes.KEY_4,            evdev.ecodes.KEY_8,
    evdev.ecodes.KEY_KPDOT,        evdev.ecodes.KEY_KPENTER,
]

class VirtualGunDevice(object):
    def __init__(self, width, height):
        self.cursor     = [0, 0]
        self.buttons    = b"\x00\x00"
        self.index      = 0
        self.index_map  = 0
        self.width  = width
        self.height = height

    def __get_capabilities(self):

        l   = len(_MAP) // _MAP_INDEX_MAX
        off = ( ( self.index - 1 ) % l ) * _MAP_INDEX_MAX

        self.index_map = off

        keys = []
        for key in range(off, off + _MAP_INDEX_MAX):
            keys.append(_MAP[key])

        gun_cap = {
            evdev.ecodes.EV_KEY: [
                evdev.ecodes.BTN_LEFT,           # WIIMOTE BUTTON B
                evdev.ecodes.BTN_RIGHT,          # WIIMOTE BUTTON A
                evdev.ecodes.BTN_MIDDLE,         # BUTTON HOME
            ] + keys,
            evdev.ecodes.EV_ABS: [
                # mouse cursor
                (evdev.ecodes.ABS_X, evdev.AbsInfo(value=0,
                        min=0, max=self.width, fuzz=0, flat=0, resolution=0)),
                (evdev.ecodes.ABS_Y, evdev.AbsInfo(value=0,
                        min=0, max=self.height, fuzz=0, flat=0, resolution=0)),
            ],
        }

        return gun_cap

    def create_virtual_device(self):
        gunname = "VirtualGun {:03X}".format(self.index)
        self.virtualgun = evdev.UInput(self.__get_capabilities(),
                                    name=gunname)
        print(gunname)
        print(self.virtualgun.capabilities(verbose=True))

    def get_index(self):
        self.index = len(self.get_list_mice()) + 1
        return self.index

    def get_list_mice(self):
        mice = []
        input_dir = '/dev/input/'
        for entry in os.listdir(input_dir):
            if 'mouse' in entry:
                mice.append(os.path.join(input_dir, entry))
        return mice

    def set_buttons(self, buttons):
        self.buttons = buttons

    def set_cursor(self, cursor):
        self.cursor = cursor

    def sync(self):
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_LEFT],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_LEFT_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_RIGHT],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_RIGHT_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_UP],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_UP_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_DOWN],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_DOWN_MASK)))


        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_PLUS],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_PLUS_MASK)))

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_MINUS],
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_MINUS_MASK)))

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_ONE],
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_ONE_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_TWO],
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_TWO_MASK)))

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_RIGHT,
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_A_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_LEFT,
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_B_MASK)))

        # cursor
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_X, self.cursor[_X])
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_Y, self.cursor[_Y])

        self.virtualgun.syn()

