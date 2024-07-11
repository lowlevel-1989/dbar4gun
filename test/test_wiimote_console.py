import io
import os
import sys
import time
import signal
import argparse

from dbar4gun import wiimote as wmote
from dbar4gun.calibration import CalibrationDummy


fd        = None
hidraw_io = None

def SignalHandler(SignalNumber, Frame):
    if fd:
        try:
            hidraw_io.close()
            os.close(fd)
        except:
            pass
    sys.exit()

def test_argument():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=str, default="/dev/hidraw0", help="/dev/hidraw0")
    parser.add_argument("--width",  type=int, default=1920, help="screen")
    parser.add_argument("--height", type=int, default=1080, help="screen")

    return parser.parse_args()

def normalize_to_screen(point, width, height):
    screen_x = int(point[0] * (width - 1))
    screen_y = int(point[1] * (height - 1))
    return [screen_x, screen_y]

def draw_screen(point_a, point_b, point_c, point_d, width, height):
    # Create an empty screen where each horizontal unit is doubled
    screen = [[' ' for _ in range(width * 2)] for _ in range(height)]

    # Draw the point, doubling the horizontal position
    screen[point_d[1]][point_d[0] * 2] = 'd'
    if point_d[0] * 2 + 1 < width * 2:  # Ensure we don't go out of bounds
        screen[point_d[1]][point_d[0] * 2 + 1] = ' '

    # Draw the point, doubling the horizontal position
    screen[point_c[1]][point_c[0] * 2] = 'c'
    if point_c[0] * 2 + 1 < width * 2:  # Ensure we don't go out of bounds
        screen[point_c[1]][point_c[0] * 2 + 1] = ' '

    # Draw the point, doubling the horizontal position
    screen[point_b[1]][point_b[0] * 2] = 'b'
    if point_b[0] * 2 + 1 < width * 2:  # Ensure we don't go out of bounds
        screen[point_b[1]][point_b[0] * 2 + 1] = ' '

    # Draw the point, doubling the horizontal position
    screen[point_a[1]][point_a[0] * 2] = 'a'
    if point_a[0] * 2 + 1 < width * 2:  # Ensure we don't go out of bounds
        screen[point_a[1]][point_a[0] * 2 + 1] = ' '

    # Draw the borders
    for y in range(height):
        for x in range(width * 2):
            if y == 0 or y == height - 1:
                screen[y][x] = '·'
            elif x == 0 or x == width * 2 - 1:
                screen[y][x] = '·'

    # Convert the screen matrix to a single string for printing
    screen_str = '\n'.join([''.join(row) for row in screen])
    return screen_str

def test_wiimote():
    config = test_argument()

    fd        = os.open(config.device, os.O_RDWR)
    hidraw_io = io.FileIO(fd, "rb+", closefd=False)

    try:
        wiimote = wmote.WiiMoteDevice(hidraw_io, CalibrationDummy)

        while 1:
            wiimote.check_is_alive()
            button, ir_dots, acc, nunchuck_button, nunchuck_joy = wiimote.read()

            point_a = normalize_to_screen(ir_dots[0], 25, 10)
            point_b = normalize_to_screen(ir_dots[1], 25, 10)
            point_c = normalize_to_screen(ir_dots[2], 25, 10)
            point_d = normalize_to_screen(ir_dots[3], 25, 10)
            screen_str       = draw_screen(point_a, point_b, point_c, point_d, 25, 10)

            template = """\033[2J\033[H
       U({U})       -({M}) #({H}) +({P})  A({A})  1({O})  C({C})
  L({L})      R({R})                  B({B})  2({T})  Z({Z})
       D({D})

    TL [{DOT_TL_X:02.02f}, {DOT_TL_Y:02.02f}, {DOT_TL_K:02.02f}]  TR [{DOT_TR_X:02.02f}, {DOT_TR_Y:02.02f}, {DOT_TR_K:02.02f}]
    BL [{DOT_BL_X:02.02f}, {DOT_BL_Y:02.02f}, {DOT_BL_K:02.02f}]  BR [{DOT_BR_X:02.02f}, {DOT_BR_Y:02.02f}, {DOT_BR_K:02.02f}]

{SCREEN}
            """
            print(template.format(**{
                "T":  (button & wmote.WIIMOTE_CORE_BUTTON_TWO_MASK)    >> 0x00,
                "O":  (button & wmote.WIIMOTE_CORE_BUTTON_ONE_MASK)    >> 0x01,
                "B":  (button & wmote.WIIMOTE_CORE_BUTTON_B_MASK)      >> 0x02,
                "A":  (button & wmote.WIIMOTE_CORE_BUTTON_A_MASK)      >> 0x03,
                "M":  (button & wmote.WIIMOTE_CORE_BUTTON_MINUS_MASK)  >> 0x04,
                "H":  (button & wmote.WIIMOTE_CORE_BUTTON_HOME_MASK)   >> 0x07,
                "L":  (button & wmote.WIIMOTE_CORE_BUTTON_LEFT_MASK)   >> 0x08,
                "R":  (button & wmote.WIIMOTE_CORE_BUTTON_RIGHT_MASK)  >> 0x09,
                "D":  (button & wmote.WIIMOTE_CORE_BUTTON_DOWN_MASK)   >> 0x0a,
                "U":  (button & wmote.WIIMOTE_CORE_BUTTON_UP_MASK)     >> 0x0b,
                "P":  (button & wmote.WIIMOTE_CORE_BUTTON_PLUS_MASK)   >> 0x0c,

                "Z":  (nunchuck_button & wmote.WIIMOTE_NUNCHUCK_BUTTON_Z_MASK) >> 0x00,
                "C":  (nunchuck_button & wmote.WIIMOTE_NUNCHUCK_BUTTON_C_MASK) >> 0x01,

                "DOT_TL_X": ir_dots[0][0], "DOT_TL_Y": ir_dots[0][1], "DOT_TL_K": ir_dots[0][2],
                "DOT_TR_X": ir_dots[1][0], "DOT_TR_Y": ir_dots[1][1], "DOT_TR_K": ir_dots[1][2],
                "DOT_BL_X": ir_dots[2][0], "DOT_BL_Y": ir_dots[2][1], "DOT_BL_K": ir_dots[2][2],
                "DOT_BR_X": ir_dots[3][0], "DOT_BR_Y": ir_dots[3][1], "DOT_BR_K": ir_dots[3][2],

                "SCREEN": screen_str,
            }))

    except Exception as e:
        print(e)

    try:
        hidraw_io.close()
        os.close(fd)
    except:
        pass

if __name__ == '__main__':
    signal.signal(signal.SIGINT,  SignalHandler)
    signal.signal(signal.SIGTERM, SignalHandler)

    test_wiimote()
