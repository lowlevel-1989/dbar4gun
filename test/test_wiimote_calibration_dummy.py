import io
import os
import sys
import time
import signal
import argparse

import pygame

import dbar4gun

from dbar4gun import wiimote as wmote
from dbar4gun.calibration import CalibrationDummy


def SignalHandler(SignalNumber, Frame):
    if fd:
        try:
            hidraw_io.close()
            os.close(fd)
        except:
            pass
    sys.kill()

def test_argument():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=str, default="/dev/hidraw0", help="/dev/hidraw0")
    parser.add_argument("--width",  type=int, default=1024, help="screen")
    parser.add_argument("--height", type=int, default=768,  help="screen")

    return parser.parse_args()

def test_wiimote():
    config = test_argument()

    fd        = os.open(config.device, os.O_RDWR)
    hidraw_io = io.FileIO(fd, "rb+", closefd=False)

    try:

        pygame.init()
        pygame.display.set_caption("{title} {version}".format(**{
            "title":   dbar4gun.__title__,
            "version": dbar4gun.__version__}))

        off = [300, 100]
        surface = pygame.display.set_mode((config.width+(off[0] * 2), config.height+(off[1] * 2)))

        axis = [(config.width+(off[0] * 2))//2, (config.height+(off[1] * 2))//2]

        # draw x-axis
        pygame.draw.line(surface, [0xff, 0, 0], [0, axis[1]], [config.width+(off[0]*2), axis[1]], 1)

        # draw y-axis
        pygame.draw.line(surface, [0, 0xff, 0], [axis[0], 0], [axis[0], config.height+(off[1]*2)], 1)

        pygame.draw.rect(surface, [0x80, 0x80, 0x80], pygame.Rect(off, [config.width, config.height]), width=1)

        pygame.display.flip()

        wiimote = wmote.WiiMoteDevice(hidraw_io, CalibrationDummy)

        p_center_prev = [0.5, 0.5]
        is_exit = False
        while not is_exit:
            wiimote.check_is_alive()
            button, ir_dots, acc, nunchuck_button, nunchuck_joy = wiimote.read()

            surface.fill([0, 0, 0])

            # draw x-axis
            pygame.draw.line(surface, [0xff, 0, 0], [0, axis[1]], [config.width+(off[0]*2), axis[1]], 1)

            # draw y-axis
            pygame.draw.line(surface, [0, 0xff, 0], [axis[0], 0], [axis[0], config.height+(off[1]*2)], 1)

            pygame.draw.rect(surface, [0x80, 0x80, 0x80], pygame.Rect(off, [config.width, config.height]), width=1)


            ratio = 12
            color = [
                [0xe4, 0x74, 0x59],
                [0x60, 0xcd, 0x83],
                [0x60, 0xc6, 0xcd],
                [0xc5, 0x60, 0xcd],
            ]
            i = 0
            for dot in ir_dots:
                point = [int(dot[0] * config.width) + off[0], int(dot[1] * config.height) + off[1]]
                pygame.draw.circle(surface, color[i], point, ratio, width=0 if dot[2] else 6)
                i += 1

            calibration = CalibrationDummy()
            cursor = calibration.map_coordinates(ir_dots, acc)

            cursor[0] = int(cursor[0] * config.width)  + off[0]
            cursor[1] = int(cursor[1] * config.height) + off[1]

            pygame.draw.circle(surface, [0xe3, 0xc8, 0xe4], cursor, ratio, width=2)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    is_exit = True

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
