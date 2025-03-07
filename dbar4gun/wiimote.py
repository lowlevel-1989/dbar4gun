import io
import time
import typing
import struct

WIIMOTE_CORE_BUTTON_TWO_MASK   = 1 << 0x0
WIIMOTE_CORE_BUTTON_ONE_MASK   = 1 << 0x1
WIIMOTE_CORE_BUTTON_B_MASK     = 1 << 0x2
WIIMOTE_CORE_BUTTON_A_MASK     = 1 << 0x3
WIIMOTE_CORE_BUTTON_MINUS_MASK = 1 << 0x4

WIIMOTE_CORE_BUTTON_UNK_03     = 1 << 0x5
WIIMOTE_CORE_BUTTON_UNK_04     = 1 << 0x6

WIIMOTE_CORE_BUTTON_HOME_MASK  = 1 << 0x7

WIIMOTE_CORE_BUTTON_LEFT_MASK  = 1 << 0x8
WIIMOTE_CORE_BUTTON_RIGHT_MASK = 1 << 0x9
WIIMOTE_CORE_BUTTON_DOWN_MASK  = 1 << 0xa
WIIMOTE_CORE_BUTTON_UP_MASK    = 1 << 0xb
WIIMOTE_CORE_BUTTON_PLUS_MASK  = 1 << 0xc

WIIMOTE_CORE_BUTTON_UNK_00     = 1 << 0xd
WIIMOTE_CORE_BUTTON_UNK_01     = 1 << 0xe
WIIMOTE_CORE_BUTTON_UNK_02     = 1 << 0xf

WIIMOTE_NUNCHUCK_BUTTON_Z_MASK = 1 << 0
WIIMOTE_NUNCHUCK_BUTTON_C_MASK = 1 << 1

WIIMOTE_LED_1 = 0x10
WIIMOTE_LED_2 = 0x20
WIIMOTE_LED_3 = 0x40
WIIMOTE_LED_4 = 0x80

WIIMOTE_REPORT_STATUS_ID   = 0x20
WIIMOTE_REPORT_RESULT_ID   = 0x22
WIIMOTE_REPORT_MODE_X37_ID = 0x37

_X = 0
_Y = 1
_K = 2

_TL = 0
_TR = 1
_BL = 2
_BR = 3

# unsupport python < version 3.12
# type Vector2D             = tuple[float, float]
# type Vector3D             = tuple[float, float, float]
# type CoreIRDot            = Vector3D
# type CoreIRCollection     = tuple[CoreIRDot, CoreIRDot, CoreIRDot, CoreIRDot]
# type CoreIRSortCollection = CoreIRCollection
# type CoreAccelerometer    = tuple[int, int, int]
# type CoreButtons          = int
# type NunchuckButtons      = int
# type NunchuckJoy          = Vector2D
# type Cursor               = Vector2D
# type IsDone               = bool
# type LEDs                 = int

class IRSetupProtocol(typing.Protocol):

    # unsupport python < version 3.12
    # def sort_and_restore(self, dots : CoreIRCollection, acc : CoreAccelerometer) -> CoreIRSortCollection:
    def sort_and_restore(self, ir_dots, acc : tuple[int, int, int]):
        ...

class CalibrationProtocol(typing.Protocol):

    # unsupport python < version 3.12
    # def step(self,
    #    button_trigger : bool,
    #    dots : CoreIRCollection, acc : CoreAccelerometer) -> tuple[IsDone, LEDs]:
    def step(self,
        button_trigger : bool,
        dots, acc : tuple[int, int, int]) -> tuple[bool, int]:
        ...

    def reset(self) -> None:
        ...

    # unsupport python < version 3.12
    # def map_coordinates(self, dots : CoreIRCollection, acc : CoreAccelerometer) -> Cursor:
    def map_coordinates(self, dots, acc : tuple[int, int, int]) -> tuple[float, float]:
        ...

    def set_tilt_correction(self, enable: bool) -> None:
        ...

    # unsupport python < version 3.12
    # def get_cursor_raw(self, dots : CoreIRCollection) -> Cursor:
    def get_cursor_raw(self, dots) -> tuple[float, float]:
        ...

    def get_cursor(self, dots) -> tuple[float, float]:
        ...

# REF: https://wiibrew.org/wiki/Wiimote
# REF: https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL
class WiiMoteDevice(object):

    # DATA:           37 BB BB AA AA AA II II II II II II II II II II EE EE EE EE EE EE
    # REPORT:         37
    # BUTTONS:        BB BB
    # ACCELEROMETER:  AA AA AA
    # IR:             II II II II II II II II II II
    # PERIPHERAL:     EE EE EE EE EE EE
    REPORT_MODE     = b"\x37"
    DATA_FORMAT_X37 = ">BH3B10sBB3xB"

    # DATA:           22 BB BB RR EE
    # REPORT:         22
    # BUTTONS:        BB BB
    # CB REPORT:      RR
    # ERROR:          EE                0 is ok
    DATA_FORMAT_X22 = ">BHBB"

    def __init__(self,
                 hidraw_io : type[io.FileIO],
                 Calibration : CalibrationProtocol,
                 IRSetup : IRSetupProtocol):

        self.is_pair = False

        self.calibration_on = 0
        self.calibration    = Calibration()
        self.ir_setup       = IRSetup()

        self.io      = hidraw_io
        self.player  = 0

        self.buf = bytearray(struct.calcsize(self.DATA_FORMAT_X37))

        self.core_button = 0x0000

        # all normalized
        self.core_ir_dot             = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        self.core_ir_dot_sorted      = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        self.core_accelerometer      = [1.0, 1.0, 1.0]

        self.enable_nunchuck =     False
        self.nunchuck_button =      0x00
        self.nunchuck_joy    = [0.5, 0.5]

        self.is_alive_time_last = time.time()

        # logica para desconectar wiimote (hack dolphinbar multigun)
        self.acc_sum_last      = 0.0
        self.acc_sum_time_last = time.time()

        # controla si enviar un cursor real o uno falso
        self.state_fake_cursor = 0
        self.is_fake_cursor    = False

        self.reset()

    def to_bytes(self, val : int) -> bytearray:
        return bytearray(bytes.fromhex("{:02x}".format(val)))

    def set_tilt_correction(self, enable: bool) -> None:
        self.calibration.set_tilt_correction(enable)

    def enable_ir(self) -> None:

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

        # DATA:           37 BB BB AA AA AA II II II II II II II II II II EE EE EE EE EE EE
        # REPORT:         37
        # BUTTONS:        BB BB
        # ACCELEROMETER:  AA AA AA
        # IR:             II II II II II II II II II II
        # PERIPHERAL:     EE EE EE EE EE EE
        # ==== DRM Set Report (Output) ====
        self.io.write(bytearray(b"\x12\x00") + bytearray(self.REPORT_MODE))
        time.sleep(1)

    def parser_ir(self, payload : bytes) -> None:

        """
        Bit
Byte	7	6	5	4	3	2	1	0
0	X1<7:0>
1	Y1<7:0>
2	Y1<9:8>	X1<9:8>	Y2<9:8>	X2<9:8>
3	X2<7:0>
4	Y2<7:0>
        """

        #----------------------- IR PART A -----------------------------

        # IR DOT 1 X1
        ir_x1_lower                       =  payload[0] & 0xff
        ir_x1_upper                       = (payload[2] & 0x30) << 4

        dot_x1 = ( ir_x1_lower | ir_x1_upper ) / 1023.5

        # INV X
        dot_x1 = 1 - dot_x1


        # IR DOT 1 Y1
        ir_y1_lower                       =  payload[1] & 0xff
        ir_y1_upper                       = (payload[2] & 0xc0) << 2

        dot_y1 = ( ir_y1_lower | ir_y1_upper ) / 767.5

        # IR DOT 1 FOUND
        dot_ok_1 = float((ir_x1_lower & ir_y1_lower) < 0xff)

        # IR DOT 2 X2
        ir_x2_lower                       =  payload[3] & 0xff
        ir_x2_upper                       = (payload[2] & 0x03) << 8

        dot_x2 = ( ir_x2_lower | ir_x2_upper ) / 1023.5

        # INV X
        dot_x2 = 1 - dot_x2

        # IR DOT 2 Y2
        ir_y2_lower                       =  payload[4] & 0xff
        ir_y2_upper                       = (payload[2] & 0x0c) << 6

        dot_y2 = ( ir_y2_lower | ir_y2_upper ) / 767.5

        # IR DOT 2 FOUND
        dot_ok_2 = float((ir_x2_lower & ir_y2_lower) < 0xff)

        #----------------------- IR PART B -----------------------------

        # IR DOT 3 X3
        ir_x3_lower                       =  payload[5] & 0xff
        ir_x3_upper                       = (payload[7] & 0x30) << 4

        dot_x3 = ( ir_x3_lower | ir_x3_upper ) / 1023.5

        # INV X
        dot_x3 = 1 - dot_x3

        # IR DOT 3 Y3
        ir_y3_lower                       =  payload[6] & 0xff
        ir_y3_upper                       = (payload[7] & 0xc0) << 2

        dot_y3 = ( ir_y3_lower | ir_y3_upper ) / 767.5

        # IR DOT 1 FOUND
        dot_ok_3 = float((ir_x3_lower & ir_y3_lower) < 0xff)

        # IR DOT 4 X4
        ir_x4_lower                       =  payload[8] & 0xff
        ir_x4_upper                       = (payload[7] & 0x03) << 8

        dot_x4 = ( ir_x4_lower | ir_x4_upper ) / 1023.5

        # INV X
        dot_x4 = 1 - dot_x4

        # IR DOT 4 Y4
        ir_y4_lower                       =  payload[9] & 0xff
        ir_y4_upper                       = (payload[7] & 0x0c) << 6

        dot_y4 = ( ir_y4_lower | ir_y4_upper ) / 767.5

        # IR DOT 4 FOUND
        dot_ok_4 = float((ir_x4_lower & ir_y4_lower) < 0xff)

        # prevent overflow
        dot_x1 = max(0.0, min(1.0, dot_x1))
        dot_y1 = max(0.0, min(1.0, dot_y1))

        dot_x2 = max(0.0, min(1.0, dot_x2))
        dot_y2 = max(0.0, min(1.0, dot_y2))

        dot_x3 = max(0.0, min(1.0, dot_x3))
        dot_y3 = max(0.0, min(1.0, dot_y3))

        dot_x4 = max(0.0, min(1.0, dot_x4))
        dot_y4 = max(0.0, min(1.0, dot_y4))

        self.core_ir_dot[0] = [dot_x1, dot_y1, dot_ok_1]
        self.core_ir_dot[1] = [dot_x2, dot_y2, dot_ok_2]
        self.core_ir_dot[2] = [dot_x3, dot_y3, dot_ok_3]
        self.core_ir_dot[3] = [dot_x4, dot_y4, dot_ok_4]

    def calibration_step(self, button_trigger : bool) -> None:

        is_done, leds = self.calibration.step(
                button_trigger,
                self.core_ir_dot_sorted.copy(),
                self.core_accelerometer)

        if is_done:
            self.calibration_on = 0
            return

        self.calibration_on = 1

        if leds:
            self.io.write(bytearray(b"\x11") + self.to_bytes(leds))

    # unsupport python < version 3.12
    # def get_cursor_raw(self) -> Cursor:
    def get_cursor_raw(self) -> tuple[float, float]:
        return self.calibration.get_cursor_raw(self.core_ir_dot_sorted)

    # unsupport python < version 3.12
    # def get_cursor(self) -> Cursor:
    def get_cursor(self) -> tuple[float, float]:
        if self.is_fake_cursor:
            return (0.0, 0.0)

        return self.calibration.map_coordinates(
                self.core_ir_dot_sorted, self.core_accelerometer)

    def fake_cursor_check(self) -> None:
        button = self.core_button

        button_b     = (bool(button & WIIMOTE_CORE_BUTTON_B_MASK))
        button_plus  = (bool(button & WIIMOTE_CORE_BUTTON_PLUS_MASK))

        if (button_b & button_plus) and self.state_fake_cursor == 0:
            self.is_fake_cursor = not self.is_fake_cursor
            self.state_fake_cursor = 1

        if (not button_plus) and self.state_fake_cursor == 1:
            self.state_fake_cursor = 0

    def calibration_check(self) -> None:

        button = self.core_button

        button_a     = (bool(button & WIIMOTE_CORE_BUTTON_A_MASK))
        button_b     = (bool(button & WIIMOTE_CORE_BUTTON_B_MASK))
        button_plus  = (bool(button & WIIMOTE_CORE_BUTTON_PLUS_MASK))
        button_minus = (bool(button & WIIMOTE_CORE_BUTTON_MINUS_MASK))

        only_buttons_mask = WIIMOTE_CORE_BUTTON_MINUS_MASK | WIIMOTE_CORE_BUTTON_PLUS_MASK | WIIMOTE_CORE_BUTTON_HOME_MASK

        if ( button_a & button_plus ) or self.calibration_on > 0:
            self.core_button = self.core_button & only_buttons_mask
            self.calibration_step(button_b)

        if button_a & button_minus:
            self.core_button = self.core_button & only_buttons_mask
            self.calibration_on = 0

            # reset calibration
            self.calibration.reset()

    # unsupport python < version 3.12
    # def read(self) -> tuple[
    #        CoreButtons, CoreIRCollection, CoreIRSortCollection, CoreAccelerometer,
    #        NunchuckButtons, NunchuckJoy]:
    def read(self):

        if not self.is_pair:
            self.reset()

        self.io.readinto(self.buf)
        report_id = self.buf[0]

        if report_id == WIIMOTE_REPORT_RESULT_ID:
            # DATA:      22 BB BB RR EE
            report_id, \
            buttons,   \
            result,    \
            err        = struct.unpack(self.DATA_FORMAT_X22, self.buf[:5])

            self.core_button = buttons

        elif report_id == WIIMOTE_REPORT_MODE_X37_ID:
            # DATA:            37 BB BB AA AA AA II II II II II II II II II II EE EE EE EE EE EE
            report_id,       \
            buttons,         \
            acc_x,           \
            acc_y,           \
            acc_z,           \
            ir_payload,      \
            nunchuck_joy_x,  \
            nunchuck_joy_y,  \
            nunchuck_buttons = struct.unpack(self.DATA_FORMAT_X37, self.buf)

            self.core_button        = buttons
            self.core_accelerometer = [acc_x / 0xff, acc_y / 0xff, acc_z / 0xff]

            self.nunchuck_button = 0x00
            self.nunchuck_joy    = [0.5, 0.5]

            if self.enable_nunchuck:
                self.nunchuck_button    = (nunchuck_buttons & 0x3) ^ 0x3
                self.nunchuck_joy       = [
                    nunchuck_joy_x / 0xff,
                    nunchuck_joy_y / 0xff,
                ]

            self.parser_ir(ir_payload)
            self.core_ir_dot_sorted = self.ir_setup.sort_and_restore(self.core_ir_dot, [acc_x, acc_y, acc_z])
            self.fake_cursor_check()
            self.calibration_check()

        elif report_id == WIIMOTE_REPORT_STATUS_ID:
            self.enable_nunchuck = (self.buf[0x03] & 0xf & 0x02) >> 1
            self.reset()

        # hack reconnect dolphinbar wiimote
        acc_sum = sum(self.core_accelerometer)
        now = time.time()
        if acc_sum == self.acc_sum_last:
            if now - self.acc_sum_time_last >= 10 and self.is_pair:
                self.is_pair = False
                self.io.write(bytearray(b"\x11\xf0"))
                time.sleep(0.5)
                self.reset()
                self.acc_sum_time_last = now
        else:
            self.acc_sum_last      = acc_sum
            self.acc_sum_time_last = now

        return [
            self.core_button,
            self.core_ir_dot.copy(),
            self.core_ir_dot_sorted.copy(),
            self.core_accelerometer,
            self.nunchuck_button,
            self.nunchuck_joy
        ]

    def reset(self) -> None:
        try:
            self.enable_ir()
            self.update_index(self.player)
        except:
            self.is_pair = False

    # fix slow dolphinbar
    def check_is_alive(self) -> None:
        now = time.time()
        if now - self.is_alive_time_last >= 3:
            self.is_alive_time_last = now
            self.update_index(self.player)

    def update_index(self, player : int =0) -> bool:
        if self.calibration_on > 0:
            return True
        try:
            if not self.is_pair:
                self.enable_ir()

            self.player = player % 4 + 1
            if not player or player > 0xf:
                self.io.write(bytearray(b"\x11\xf0"))

            else:
                if self.player == 0x01:
                    index = WIIMOTE_LED_4
                if self.player == 0x02:
                    index = WIIMOTE_LED_3
                if self.player == 0x03:
                    index = WIIMOTE_LED_2
                if self.player == 0x04:
                    index = WIIMOTE_LED_1

                self.io.write(bytearray(b"\x11") + self.to_bytes(index))

            self.is_pair = True
            return True
        except:
            self.is_pair = False
            return False
