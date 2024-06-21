import time
import struct
import os

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

    def __init__(self, hidraw_io, width=1920, height=1080):
        self.is_pair = False

        self.io           = hidraw_io
        self.player       = 0
        self.prev_player  = 0
        self.width        = width
        self.height       = height

        ##                     ID     BB   IR_F   IR_B   OTHER
        self.buf = bytearray(0x01 + 0x02 + 0x05 + 0x05 + 0x09 )

        self.buttons_status = b"\x00\x00"
        self.ir_status = {
            "dot_ok":       [False, False],
            "pos_raw":     [[0xfff, 0xfff], [0xfff, 0xfff]],
            "pos_nor":     [[  1.0,   1.0], [  1.0,   1.0]],
            "pos_mid_raw":  [0xfff, 0xfff],
            "pos_mid_nor":  [  1.0,   1.0],
        }

        self.reset()

    def reset(self):
        try:
            self.update_index()
            self.enable_ir()
            self.is_pair = True
        except:
            self.is_pair = False

    def update_index(self, player=0):
        try:
            self.player = player
            if not self.player or self.player > 0xf:
                self.io.write(bytearray(b"\x11\xf0"))

            elif self.player != self.prev_player:
                index  = 0x00
                if player & 0x01:
                    index = index | 0x80
                if player & 0x02:
                    index = index | 0x40
                if player & 0x04:
                    index = index | 0x20
                if player & 0x08:
                    index = index | 0x10

                self.io.write(bytearray(b"\x11") + bytearray(bytes.fromhex("{:02x}".format(index))))
                self.prev_player = self.player

            self.is_pair = True
            return True
        except:
            self.is_pair = False
            return False

    def enable_ir(self):
        # ENABLE IR
        # REF: https://www.wiibrew.org/wiki/Wiimote
        # ==== IR Set1 Report (Output) ====
        self.io.write(bytearray(b"\x13\x04"))
        time.sleep(0.1)

        # ==== IR Set2 Report (Output) ====
        self.io.write(bytearray(b"\x1a\x04"))
        time.sleep(0.1)

        # DATA: 52 16 CC OO OO OO SS DD DD DD DD DD DD DD DD DD DD DD DD DD DD DD DD
        # CC -> 0x04: Rumble Off but write to Registers
        # DATA:                     16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.io.write(bytearray(b"\x16\x04\xb0\x00\x30\x01\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # DATA BLOCK 1:             16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.io.write(bytearray(b"\x16\x04\xb0\x00\x00\x09\x00\x00\x00\x00\x00\x00\x90\x00\xC0\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # DATA BLOCK 2:             16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.io.write(bytearray(b"\x16\x04\xb0\x00\x1a\x02\x40\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # IR MODE:                  16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.io.write(bytearray(b"\x16\x04\xb0\x00\x33\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # DATA:                     16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.io.write(bytearray(b"\x16\x04\xb0\x00\x30\x01\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)

        # DATA:       30 BB BB II II II II II II II II II II EE EE EE EE EE EE EE EE EE
        # REPORT:     30
        # BUTTONS:    BB BB
        # IR:         II II II II II II II II II II
        # PERIPHERAL: EE EE EE EE EE EE EE EE EE
        # ==== DRM Set Report (Output) ====
        self.io.write(bytearray(b"\x12\x00") + bytearray(self.REPORT_MODE))
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
            int(self.ir_status["pos_mid_nor"][_X] * self.width),
            int(self.ir_status["pos_mid_nor"][_Y] * self.height),
        ]

    def read(self):
        if not self.is_pair:
            self.reset()

        self.io.readinto(self.buf)
        report_id, button, ir_dots_far, ir_dots_unknown = \
                                struct.unpack(self.DATA_FORMAT, self.buf)

        # print(ir_dots_far)
        self.parser_ir(ir_dots_far)
        self.buttons_status = button

        # TODO: report id 0x36, status 0x20 working
        return [self.buttons_status, self.ir_status]
