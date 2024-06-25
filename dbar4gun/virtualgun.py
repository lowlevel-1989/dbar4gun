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

VIRTUALGUN_BUTTON_Z_MASK      = 0x01
VIRTUALGUN_BUTTON_C_MASK      = 0x02

_X = 0
_Y = 1

_MAP_INDEX_LEFT  =  0
_MAP_INDEX_RIGHT =  1
_MAP_INDEX_DOWN  =  2
_MAP_INDEX_UP    =  3
_MAP_INDEX_PLUS  =  4
_MAP_INDEX_MINUS =  5
_MAP_INDEX_A     =  6
_MAP_INDEX_ONE   =  7
_MAP_INDEX_C     =  8
_MAP_INDEX_Z     =  9
_MAP_INDEX_MAX   = 10

# TODO: add 16 gun
_MAP = [
    # gun 1
    evdev.ecodes.KEY_LEFT,         evdev.ecodes.KEY_RIGHT,
    evdev.ecodes.KEY_DOWN,         evdev.ecodes.KEY_UP,
    evdev.ecodes.KEY_1,            evdev.ecodes.KEY_5,
    evdev.ecodes.KEY_LEFTALT,      evdev.ecodes.KEY_B,
    evdev.ecodes.KEY_LEFTSHIFT,    evdev.ecodes.KEY_Z,

    # gun 2
    evdev.ecodes.KEY_D,            evdev.ecodes.KEY_G,
    evdev.ecodes.KEY_F,            evdev.ecodes.KEY_R,
    evdev.ecodes.KEY_2,            evdev.ecodes.KEY_6,
    evdev.ecodes.KEY_S,            evdev.ecodes.KEY_Q,
    evdev.ecodes.KEY_W,            evdev.ecodes.KEY_E,

    # gun 3
    evdev.ecodes.KEY_J,            evdev.ecodes.KEY_L,
    evdev.ecodes.KEY_K,            evdev.ecodes.KEY_I,
    evdev.ecodes.KEY_3,            evdev.ecodes.KEY_7,
    evdev.ecodes.KEY_RIGHTSHIFT,   evdev.ecodes.KEY_ENTER,
    evdev.ecodes.KEY_KP1,          evdev.ecodes.KEY_KP3,

    # gun 4
    evdev.ecodes.KEY_KP4,          evdev.ecodes.KEY_KP6,
    evdev.ecodes.KEY_KP2,          evdev.ecodes.KEY_KP8,
    evdev.ecodes.KEY_4,            evdev.ecodes.KEY_8,
    evdev.ecodes.KEY_KPDOT,        evdev.ecodes.KEY_KPENTER,
    evdev.ecodes.KEY_KP5,          evdev.ecodes.KEY_KP7,
]

class VirtualGunDevice(object):
    NUNCHUK_JOY_THRESHOLD   = 35
    NUNCHUK_JOY_CENTER_X    = 128
    NUNCHUK_JOY_CENTER_Y    = 128

    def __init__(self, width, height):
        self.cursor           = [0, 0]
        self.buttons          = b"\x00\x00"
        self.nunchuck_joy_x   = 0xff
        self.nunchuck_joy_y   = 0xff
        self.nunchuck_buttons = 0xff
        self.index            = 0
        self.index_map        = 0
        self.width            = width
        self.height           = height

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

                # combos
                evdev.ecodes.KEY_ENTER,  # b + plus
                evdev.ecodes.KEY_ESC,    # b + minus
                evdev.ecodes.KEY_TAB,    # b + home
                evdev.ecodes.KEY_MINUS,  # b + 1
                evdev.ecodes.KEY_EQUAL,  # b + 2
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

    def set_buttons(self, buttons, nunchuck):
        self.buttons  = buttons
        self.nunchuck_joy_x   = nunchuck["joy_x"]
        self.nunchuck_joy_y   = nunchuck["joy_y"]
        self.nunchuck_buttons = nunchuck["buttons"]

    def set_cursor(self, cursor):
        self.cursor = cursor

    def get_nunchuk_direction(self):

        if ((self.nunchuck_joy_x + self.nunchuck_joy_y) / 2  ) == 0xff:
            return [False, False, False, False]

        if self.nunchuck_joy_x < self.NUNCHUK_JOY_CENTER_X - self.NUNCHUK_JOY_THRESHOLD:
            left = True
        else:
            left = False

        if self.nunchuck_joy_x > self.NUNCHUK_JOY_CENTER_X + self.NUNCHUK_JOY_THRESHOLD:
            right = True
        else:
            right = False

        if self.nunchuck_joy_y < self.NUNCHUK_JOY_CENTER_Y - self.NUNCHUK_JOY_THRESHOLD:
            down = True
        else:
            down = False

        if self.nunchuck_joy_y > self.NUNCHUK_JOY_CENTER_Y + self.NUNCHUK_JOY_THRESHOLD:
            up   = True
        else:
            up   = False

        return [left, right, up, down]

    def sync(self):
        nunchuck_dir = self.get_nunchuk_direction()

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_LEFT],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_LEFT_MASK)) | nunchuck_dir[0])
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_RIGHT],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_RIGHT_MASK)) | nunchuck_dir[1])
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_UP],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_UP_MASK)) | nunchuck_dir[2])
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_DOWN],
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_DOWN_MASK)) | nunchuck_dir[3])

        # cursor
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_X, self.cursor[_X])
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_Y, self.cursor[_Y])

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_A],
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_A_MASK)))

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_C],
                (not (self.nunchuck_buttons & VIRTUALGUN_BUTTON_C_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_Z],
                (not (self.nunchuck_buttons & VIRTUALGUN_BUTTON_Z_MASK)))

        # with combo
        button_b     = (not not (self.buttons[1] & VIRTUALGUN_BUTTON_B_MASK))
        button_home  = (not not (self.buttons[1] & VIRTUALGUN_BUTTON_HOME_MASK))
        button_one   = (not not (self.buttons[1] & VIRTUALGUN_BUTTON_ONE_MASK))
        button_two   = (not not (self.buttons[1] & VIRTUALGUN_BUTTON_TWO_MASK))
        button_plus  = (not not (self.buttons[0] & VIRTUALGUN_BUTTON_PLUS_MASK))
        button_minus = (not not (self.buttons[1] & VIRTUALGUN_BUTTON_MINUS_MASK))

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_ENTER, button_b & button_plus)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_ESC,   button_b & button_minus)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_TAB,   button_b & button_home)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_MINUS, button_b & button_one)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_EQUAL, button_b & button_two)

        if button_b  & button_home  or \
            button_b & button_plus  or \
            button_b & button_minus or \
            button_b & button_one   or \
            button_b & button_two:
            self.virtualgun.syn()
            return

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_LEFT,                   button_b)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_MIDDLE,                 button_home)

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_ONE],   button_one)
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_RIGHT,                  button_two)

        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_PLUS],  button_plus)
        self.virtualgun.write(evdev.ecodes.EV_KEY, _MAP[self.index_map + _MAP_INDEX_MINUS], button_minus)


        """
            THRESHOLD = 35


            print("nunchuck")
            print(nunchuck_joy_x)
            print(nunchuck_joy_y)
            print("left  ",  left)
            print("right ", right)
            print("up    ",    up)
            print("down  ",  down)
            print(not (nunchuck_buttons & 0x01))
            print(not (nunchuck_buttons & 0x02))
        """

        self.virtualgun.syn()

