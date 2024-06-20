import os
import io
import time
import struct
import evdev
import math

from pprint import pprint

mouse_cap = {
    evdev.ecodes.EV_KEY: [
        evdev.ecodes.BTN_LEFT, evdev.ecodes.BTN_RIGHT,
        ],
    evdev.ecodes.EV_ABS: [
        (evdev.ecodes.ABS_X, evdev.AbsInfo(value=0,
                min=0, max=1920, fuzz=0, flat=0, resolution=0)),
        (evdev.ecodes.ABS_Y, evdev.AbsInfo(value=0,
                min=0, max=1080, fuzz=0, flat=0, resolution=0)),
    ]
}

mouse = evdev.UInput(mouse_cap,
                     name="VirtualGun mouse",
                     ID_INPUT_JOYSTICK=1,
                     product=0x19, vendor=0x89, version=0x01)


print(mouse.name)
print(mouse.product)
print(mouse.vendor)
print(mouse.version)
print(mouse.phys)
print(mouse.device)
print(mouse.device.path)
print(mouse.devnode)

while 1:
    time.sleep(1)

WIIMOTE_CORE_BUTTON_LEFT_MASK  = 0x01
WIIMOTE_CORE_BUTTON_RIGHT_MASK = 0x02
WIIMOTE_CORE_BUTTON_DOWN_MASK  = 0x04
WIIMOTE_CORE_BUTTON_UP_MASK    = 0x08
WIIMOTE_CORE_BUTTON_PLUS_MASK  = 0x10

WIIMOTE_CORE_BUTTON_TWO_MASK   = 0x01
WIIMOTE_CORE_BUTTON_ONE_MASK   = 0x02
WIIMOTE_CORE_BUTTON_B_MASK     = 0x04
WIIMOTE_CORE_BUTTON_A_MASK     = 0x08
WIIMOTE_CORE_BUTTON_MINUS_MASK = 0x10
WIIMOTE_CORE_BUTTON_HOME_MASK  = 0x80

_X = 0
_Y = 1

# REF: https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL
class WiiMoteDevice(object):

    REPORT_MODE = b"\x36"
    DATA_FORMAT = ">B2s5s5s9x"

    def __init__(self, device):
        # TODO: colocar a False y trabajar el flujo de conexiones
        self.is_pair = True
        self.device = device

        ##                     ID     BB   IR_L   IR_R   OTHER
        self.buf = bytearray(0x01 + 0x02 + 0x05 + 0x05 + 0x09 )

        self.buttons_status = b"\x00\x00"
        self.ir_status = {
            "dot_ok":       [False, False],
            "pos_raw":     [[0xfff, 0xfff], [0xfff, 0xfff]],
            "pos_nor":     [[  1.0,   1.0], [  1.0,   1.0]],
            "pos_mid_raw":  [0xfff, 0xfff],
            "pos_mid_nor":  [  1.0,   1.0],
        }

        time.sleep(0.1)
        self.device.write(bytearray(b"\x11\xf0"))

        # request state
        # time.sleep(0.1)
        # self.device.write(bytearray(b"\x15\x00"))
        # time.sleep(0.1)
        # self.device.write(bytearray(b"\x15\x00"))

        self.enable_ir()

    def enable_ir(self):
        # ENABLE IR
        # REF: https://www.wiibrew.org/wiki/Wiimote
        # ==== IR Set1 Report (Output) ====
        self.device.write(bytearray(b"\x13\x04"))
        time.sleep(0.1)

        # ==== IR Set2 Report (Output) ====
        self.device.write(bytearray(b"\x1a\x04"))
        time.sleep(0.1)

        # DATA: 52 16 CC OO OO OO SS DD DD DD DD DD DD DD DD DD DD DD DD DD DD DD DD
        # CC -> 0x04: Rumble Off but write to Registers
        # DATA:                    16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.device.write(bytearray(b"\x16\x04\xb0\x00\x30\x01\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # DATA BLOCK 1:            16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.device.write(bytearray(b"\x16\x04\xb0\x00\x00\x09\x00\x00\x00\x00\x00\x00\x90\x00\xC0\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # DATA BLOCK 2:            16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.device.write(bytearray(b"\x16\x04\xb0\x00\x1a\x02\x40\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # IR MODE:                 16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.device.write(bytearray(b"\x16\x04\xb0\x00\x33\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # DATA:                    16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.device.write(bytearray(b"\x16\x04\xb0\x00\x30\x01\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)

        # DATA:       30 BB BB II II II II II II II II II II EE EE EE EE EE EE EE EE EE
        # REPORT:     30
        # BUTTONS:    BB BB
        # IR:         II II II II II II II II II II
        # PERIPHERAL: EE EE EE EE EE EE EE EE EE
        # ==== DRM Set Report (Output) ====
        self.device.write(bytearray(b"\x12\x00") + bytearray(self.REPORT_MODE))
        time.sleep(1)

    def parser_ir(self, payload):
        # IR DOT 1 X1
        ir_x1_lower                       =  payload[0] & 0xff
        ir_x1_upper                       = (payload[2] & 0x30) << 4
        self.ir_status["pos_raw"][0][_X]  = ir_x1_lower | ir_x1_upper
        self.ir_status["pos_nor"][0][_X]  = self.ir_status["pos_raw"][0][_X] / 1023.5

        # INV X
        self.ir_status["pos_nor"][0][_X]  = 1 - self.ir_status["pos_nor"][0][_X]

        # IR DOT 1 Y1
        ir_y1_lower                       =  payload[1] & 0xff
        ir_y1_upper                       = (payload[2] & 0xc0) << 2
        self.ir_status["pos_raw"][0][_Y]  = ir_y1_lower | ir_y1_upper
        self.ir_status["pos_nor"][0][_Y]  = self.ir_status["pos_raw"][0][_Y] / 767.5

        # IR DOT 1 FOUND
        self.ir_status["dot_ok"][0]       = (ir_x1_lower & ir_y1_lower) < 0xff

        # IR DOT 2 X2
        ir_x2_lower                       =  payload[3] & 0xff
        ir_x2_upper                       = (payload[2] & 0x03) << 8
        self.ir_status["pos_raw"][1][_X]  = ir_x2_lower | ir_x2_upper
        self.ir_status["pos_nor"][1][_X]  = self.ir_status["pos_raw"][1][_X] / 1023.5

        # INV X
        self.ir_status["pos_nor"][1][_X]  = 1 - self.ir_status["pos_nor"][1][_X]

        # IR DOT 2 Y2
        ir_y2_lower                       =  payload[4] & 0xff
        ir_y2_upper                       = (payload[2] & 0x0c) << 6
        self.ir_status["pos_raw"][1][_Y]  = ir_y2_lower | ir_y2_upper
        self.ir_status["pos_nor"][1][_Y]  = self.ir_status["pos_raw"][1][_Y] / 767.5

        # IR DOT 2 FOUND
        self.ir_status["dot_ok"][1]       = (ir_x2_lower & ir_y2_lower) < 0xff

        # IR POS MID
        self.ir_status["pos_mid_raw"][_X] = 0
        self.ir_status["pos_mid_raw"][_Y] = 0
        self.ir_status["pos_mid_nor"][_X] = 0
        self.ir_status["pos_mid_nor"][_Y] = 0

        if self.ir_status["dot_ok"][0] & self.ir_status["dot_ok"][1]:
            self.ir_status["pos_mid_raw"][_X] = ( self.ir_status["pos_raw"][1][_X] + \
                    self.ir_status["pos_raw"][0][_X] ) // 2
            self.ir_status["pos_mid_raw"][_Y] = ( self.ir_status["pos_raw"][1][_Y] + \
                    self.ir_status["pos_raw"][0][_Y] ) // 2

            self.ir_status["pos_mid_nor"][_X] = ( self.ir_status["pos_nor"][1][_X] + \
                    self.ir_status["pos_nor"][0][_X] ) / 2
            self.ir_status["pos_mid_nor"][_Y] = ( self.ir_status["pos_nor"][1][_Y] + \
                    self.ir_status["pos_nor"][0][_Y] ) / 2

        elif self.ir_status["dot_ok"][0]:
            self.ir_status["pos_mid_raw"][_X] = self.ir_status["pos_raw"][0][_X]
            self.ir_status["pos_mid_raw"][_Y] = self.ir_status["pos_raw"][0][_Y]
            self.ir_status["pos_mid_nor"][_X] = self.ir_status["pos_nor"][0][_X]
            self.ir_status["pos_mid_nor"][_Y] = self.ir_status["pos_nor"][0][_Y]

        elif self.ir_status["dot_ok"][1]:
            self.ir_status["pos_mid_raw"][_X] = self.ir_status["pos_raw"][1][_X]
            self.ir_status["pos_mid_raw"][_Y] = self.ir_status["pos_raw"][1][_Y]
            self.ir_status["pos_mid_nor"][_X] = self.ir_status["pos_nor"][1][_X]
            self.ir_status["pos_mid_nor"][_Y] = self.ir_status["pos_nor"][1][_Y]

    def get_cursor_position(self):
        return [
            int(self.ir_status["pos_mid_nor"][_X] * 1920),
            int(self.ir_status["pos_mid_nor"][_Y] * 1080),
        ]

    def read(self):
        self.device.readinto(self.buf)
        report_id, button, ir_dots_far, ir_dots_unknown = \
                                struct.unpack(self.DATA_FORMAT, self.buf)

        self.parser_ir(ir_dots_far)
        self.buttons_status = button

        return (self.buttons_status, self.ir_status)


fd = os.open("/dev/hidraw1", os.O_RDWR)
with io.FileIO(fd, "rb+") as device_io:

    wiimote = WiiMoteDevice(device_io)
    while 1:
        button, ir = wiimote.read()

        cursor = wiimote.get_cursor_position()
        mouse.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_X, cursor[_X])
        mouse.write(evdev.ecodes.EV_ABS, evdev.ecodes.ABS_Y, cursor[_Y])
        mouse.syn()

        print("L({L}) R({R}) D({D}) U({U}) +({P}) ".format(**{
            "L":   button[0] & WIIMOTE_CORE_BUTTON_LEFT_MASK,
            "R":  (button[0] & WIIMOTE_CORE_BUTTON_RIGHT_MASK) >> 0x01,
            "D":  (button[0] & WIIMOTE_CORE_BUTTON_DOWN_MASK)  >> 0x02,
            "U":  (button[0] & WIIMOTE_CORE_BUTTON_UP_MASK)    >> 0x03,
            "P":  (button[0] & WIIMOTE_CORE_BUTTON_PLUS_MASK)  >> 0x04
        }), end="")
        print("2({T}) 1({O}) B({B}) A({A}) -({M}) ".format(**{
            "T":   button[1] & WIIMOTE_CORE_BUTTON_TWO_MASK,
            "O":  (button[1] & WIIMOTE_CORE_BUTTON_ONE_MASK)   >> 0x01,
            "B":  (button[1] & WIIMOTE_CORE_BUTTON_B_MASK)     >> 0x02,
            "A":  (button[1] & WIIMOTE_CORE_BUTTON_A_MASK)     >> 0x03,
            "M":  (button[1] & WIIMOTE_CORE_BUTTON_MINUS_MASK) >> 0x04
        }))
        print(cursor)
        pprint(ir)

