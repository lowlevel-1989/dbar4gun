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

class VirtualGunDevice(object):
    def __init__(self, width, height):
        self.cursor  = [0, 0]
        self.buttons = b"\x00\x00"
        self.index   = 0

        self.gun_cap = {
            evdev.ecodes.EV_KEY: [
                evdev.ecodes.BTN_LEFT,           # WIIMOTE BUTTON B
                evdev.ecodes.BTN_RIGHT,          # WIIMOTE BUTTON A
                evdev.ecodes.BTN_MIDDLE,         # BUTTON 1
                evdev.ecodes.BTN_TOUCH,          # BUTTON 2
                evdev.ecodes.BTN_SIDE,           # WIIMOTE BUTTON +
                evdev.ecodes.BTN_EXTRA,          # WIIMOTE BUTTON -
                # evdev.ecodes.BTN_MODE,         # WIIMOTE BUTTON HOME
            ],
            evdev.ecodes.EV_REL: [
                evdev.ecodes.REL_WHEEL,
                evdev.ecodes.REL_HWHEEL,
            ],
            evdev.ecodes.EV_ABS: [
                # mouse cursor
                (evdev.ecodes.ABS_X, evdev.AbsInfo(value=0,
                        min=0, max=width, fuzz=0, flat=0, resolution=0)),
                (evdev.ecodes.ABS_Y, evdev.AbsInfo(value=0,
                        min=0, max=height, fuzz=0, flat=0, resolution=0)),

                # joy d-pad
                # (evdev.ecodes.ABS_HAT0X, evdev.AbsInfo(value=0,
                #        min=-1, max=1, fuzz=0, flat=0, resolution=0)),
                # (evdev.ecodes.ABS_HAT0Y, evdev.AbsInfo(value=0,
                #        min=-1, max=1, fuzz=0, flat=0, resolution=0)),
            ],
        }

    def create_virtual_device(self):
        self.virtualgun = evdev.UInput(self.gun_cap, name="VirtualGun {:03X}".format(self.index))

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
        # d-pad
        self.virtualgun.write(evdev.ecodes.EV_REL, evdev.ecodes.REL_WHEEL,
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_RIGHT_MASK)) - \
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_LEFT_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_REL, evdev.ecodes.REL_HWHEEL,
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_DOWN_MASK)) - \
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_UP_MASK)))

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_SIDE,
                (not not (self.buttons[0] & VIRTUALGUN_BUTTON_PLUS_MASK)))

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_EXTRA,
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_MINUS_MASK)))

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_RIGHT,
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_A_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_LEFT,
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_B_MASK)))

        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_MIDDLE,
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_ONE_MASK)))
        self.virtualgun.write(evdev.ecodes.EV_KEY, evdev.ecodes.BTN_TOUCH,
                (not not (self.buttons[1] & VIRTUALGUN_BUTTON_TWO_MASK)))

        # cursor
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_X, self.cursor[_X])
        self.virtualgun.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_Y, self.cursor[_Y])

        self.virtualgun.syn()

