import time
import struct
import os

import cv2
import numpy as np

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

VIRTUALGUN_NUNCHUK_Z_MASK      = 0x01
VIRTUALGUN_NUNCHUK_C_MASK      = 0x02

_X = 0
_Y = 1

# REF: https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL
class WiiMoteDevice(object):

    REPORT_MODE = b"\x36"
    DATA_FORMAT = ">B2s5s5sBB3xB3x"

    def __init__(self, hidraw_io, width=1920, height=1080):
        self.is_pair = False

        self.calibration_on             = 0
        self.calibration_dots_screen    = np.float32([
            [width/2,  height/2], # center
            [       0,        0], # top left
            [   width,        0], # top right
            [       0,   height], # bottom left
            [   width,   height], # bottom right
        ])

        self.calibration_dots_gun = np.float32([
            [width/2, height/2], # center
            [      0,        0], # top left
            [  width,        0], # top right
            [      0,   height], # bottom left
            [  width,   height], # bottom right
        ])

        # set point on calibration
        self.calibration_dots_gun_buf = []

        self.calibration_matrix, _ = cv2.estimateAffine2D(self.calibration_dots_gun, self.calibration_dots_screen)

        self.io           = hidraw_io
        self.player       = 0
        self.player_prev  = 0
        self.width        = width
        self.height       = height


        ##                     ID     BB   IR_F   IR_B   OTHER
        self.buf = bytearray(0x01 + 0x02 + 0x05 + 0x05 + 0x09 )

        self.buttons_status  = b"\x00\x00"
        self.is_rumble       = False
        self.nunchuck_status = {
            "joy_x":   0xff,
            "joy_y":   0xff,
            "buttons": 0xff
        }

        self.ir_status = {
            "dot_ok":           [False, False],
            "pos_raw":          [[0xfff, 0xfff], [0xfff, 0xfff]],
            "pos_raw_prev":     [[0xfff, 0xfff], [0xfff, 0xfff]],
            "pos_nor":          [[  1.0,   1.0], [  1.0,   1.0]],
            "pos_nor_prev":     [[  1.0,   1.0], [  1.0,   1.0]],
            "pos_mid_raw":      [0xfff, 0xfff],
            "pos_mid_raw_prev": [0xfff, 0xfff],
            "pos_mid_nor":      [  1.0,   1.0],
            "pos_mid_nor_prev": [  1.0,   1.0],
        }

        self.reset()

    def reset(self):
        try:
            self.enable_ir()
            self.update_index(self.player)
        except:
            self.is_pair = False

    def check_is_alive(self):
        self.update_index(self.player)

    def update_index(self, player=0):
        if self.calibration_on > 0:
            return True
        try:
            if not self.is_pair:
                self.enable_ir()

            self.player = player
            if not self.player or self.player > 0xf:
                self.io.write(bytearray(b"\x11\xf0"))

            else:
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
                self.player_prev = self.player

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

            self.ir_status["pos_raw_prev"][0] = self.ir_status["pos_raw"][0][:]
            self.ir_status["pos_raw_prev"][1] = self.ir_status["pos_raw"][1][:]

            self.ir_status["pos_nor_prev"][0] = self.ir_status["pos_nor"][0][:]
            self.ir_status["pos_nor_prev"][1] = self.ir_status["pos_nor"][1][:]

        elif self.ir_status["dot_ok"][0]:

            self.ir_status["pos_mid_nor"][_X] = (
                    self.ir_status["pos_nor"][0][_X] + \
                    self.ir_status["pos_nor_prev"][1][_X] ) / 2
            self.ir_status["pos_mid_nor"][_Y] = self.ir_status["pos_nor"][0][_Y]

        elif self.ir_status["dot_ok"][1]:

            self.ir_status["pos_mid_nor"][_X] = (
                    self.ir_status["pos_nor"][1][_X] + \
                    self.ir_status["pos_nor_prev"][0][_X] ) / 2
            self.ir_status["pos_mid_nor"][_Y] = self.ir_status["pos_nor"][1][_Y]
        else:
            self.ir_status["pos_mid_raw"] = self.ir_status["pos_mid_raw_prev"][:]
            self.ir_status["pos_mid_nor"] = self.ir_status["pos_mid_nor_prev"][:]

            x = self.ir_status["pos_mid_nor"][_X]
            y = self.ir_status["pos_mid_nor"][_Y]

            # Calculate the distance to each of the edges
            distance_left = x
            distance_right = 1 - x
            distance_bottom = y
            distance_top = 1 - y

            # Put the distances in a dictionary
            distances = {
                "left":   distance_left,
                "right":  distance_right,
                "bottom": distance_bottom,
                "top":    distance_top
            }

            # Determine which edge is the closest
            nearest_edge = min(distances, key=distances.get)

            # Adjust the object's position to the closest edge
            if nearest_edge   == "left":
                self.ir_status["pos_mid_nor"][_X] = 0
            elif nearest_edge == "right":
                self.ir_status["pos_mid_nor"][_X] = 1
            elif nearest_edge == "bottom":
                self.ir_status["pos_mid_nor"][_Y] = 0
            elif nearest_edge == "top":
                self.ir_status["pos_mid_nor"][_Y] = 1

        self.ir_status["pos_mid_raw_prev"] = self.ir_status["pos_mid_raw"][:]
        self.ir_status["pos_mid_nor_prev"] = self.ir_status["pos_mid_nor"][:]

    def get_cursor_position(self, ir):
        cursor = self.calibration_cursor(
                [ir["pos_mid_nor"][_X] * self.width, ir["pos_mid_nor"][_Y] * self.height]
        )
        return [
            int(cursor[_X]),
            int(cursor[_Y]),
        ]

    def calibration_cursor(self, cursor):
        point_homogeneous = np.array([cursor[_X], cursor[_Y], 1.0])
        transformed_point = np.dot(self.calibration_matrix, point_homogeneous)
        return np.clip(transformed_point[:2], [0, 0], [self.width, self.height])

    def calibration_set(self, button_trigger):
        # center
        if self.calibration_on == 0:
            self.io.write(bytearray(b"\x11\xf0"))
            self.calibration_on = 1
            self.calibration_dots_gun_buf = []

        elif self.calibration_on == 1 and button_trigger:
            self.calibration_dots_gun_buf.append(self.get_cursor_position(self.ir_status))
            self.calibration_on = 2

        # top left
        elif self.calibration_on == 2 and button_trigger == False:
            self.io.write(bytearray(b"\x11\x10"))
            self.calibration_on = 3

        elif self.calibration_on == 3 and button_trigger:
            self.calibration_dots_gun_buf.append(self.get_cursor_position(self.ir_status))
            self.calibration_on = 4

        # top right
        elif self.calibration_on == 4 and button_trigger == False:
            self.io.write(bytearray(b"\x11\x20"))
            self.calibration_on = 5

        elif self.calibration_on == 5 and button_trigger:
            self.calibration_dots_gun_buf.append(self.get_cursor_position(self.ir_status))
            self.calibration_on = 6

        # bottom left
        elif self.calibration_on == 6 and button_trigger == False:
            self.io.write(bytearray(b"\x11\x40"))
            self.calibration_on = 7

        elif self.calibration_on == 7 and button_trigger:
            self.calibration_dots_gun_buf.append(self.get_cursor_position(self.ir_status))
            self.calibration_on = 8

        # bottom right
        elif self.calibration_on == 8 and button_trigger == False:
            self.io.write(bytearray(b"\x11\x80"))
            self.calibration_on = 9

        elif self.calibration_on == 9 and button_trigger:
            self.calibration_dots_gun_buf.append(self.get_cursor_position(self.ir_status))
            self.calibration_dots_gun = np.float32(self.calibration_dots_gun_buf)

            self.calibration_matrix, _ = cv2.estimateAffine2D(
                    self.calibration_dots_gun, self.calibration_dots_screen)

            self.calibration_on = 0


    def read(self):
        if not self.is_pair:
            self.reset()

        self.io.readinto(self.buf)
        report_id,         \
        button,            \
        ir_dots_far,       \
        ir_dots_unknown,   \
        nunchuck_joy_x,    \
        nunchuck_joy_y,    \
        nunchuck_buttons = struct.unpack(self.DATA_FORMAT, self.buf)

        if report_id != 0x20:
            self.parser_ir(ir_dots_far)
            self.buttons_status = button
            self.nunchuck_status["joy_x"]   = nunchuck_joy_x
            self.nunchuck_status["joy_y"]   = nunchuck_joy_y
            self.nunchuck_status["buttons"] = nunchuck_buttons

            # calibration
            try:
                button_a     = (not not (button[1] & WIIMOTE_CORE_BUTTON_A_MASK))
                button_b     = (not not (button[1] & WIIMOTE_CORE_BUTTON_B_MASK))
                button_plus  = (not not (button[0] & WIIMOTE_CORE_BUTTON_PLUS_MASK))
                button_minus = (not not (button[1] & WIIMOTE_CORE_BUTTON_MINUS_MASK))

                if ( button_a & button_plus ) or self.calibration_on > 0:
                    self.calibration_set(button_b)

                if button_a & button_minus:
                    self.calibration_on = 0
                    self.buttons_status  = b"\x00\x00"

                    # reset calibration
                    self.calibration_dots_gun = np.float32([
                        [self.width/2, self.height/2], # center
                        [           0,             0], # top left
                        [  self.width,             0], # top right
                        [           0,   self.height], # bottom left
                        [  self.width,   self.height], # bottom right
                    ])

                    self.calibration_matrix, _ = cv2.estimateAffine2D(self.calibration_dots_gun, self.calibration_dots_screen)

                if self.calibration_on > 0:
                    self.buttons_status  = b"\x00\x00"

            except Exception as e:
                print(e)

            # VERY SLOW
            """
            try:
                if button[1] & WIIMOTE_CORE_BUTTON_B_MASK:
                    self.is_rumble = True
                    self.io.write(bytearray(b"\x10\x01"))
                elif self.is_rumble:
                    self.is_rumble = False
                    self.io.write(bytearray(b"\x10\x00"))
            except Exception as e:
                print(e)
            """
        else:
            self.reset()

        return [self.buttons_status, self.ir_status, self.nunchuck_status]
