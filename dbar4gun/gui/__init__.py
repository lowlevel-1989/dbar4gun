import sys
import pygame
import struct
import socket

STRUCT_DATA       = "!BH12e12e2e"
STRUCT_DATA_SIZE  = struct.calcsize(STRUCT_DATA)

COLOR = [
    [0xe4, 0x74, 0x59],
    [0x60, 0xcd, 0x83],
    [0x60, 0xc6, 0xcd],
    [0xc5, 0x60, 0xcd],
]

class GUI(object):
    def __init__(self,
                 width  : int =  1280,
                 height : int =   720,
                 port   : int = 35460):

        self.port   = port
        self.width  = width
        self.height = height

        self.base_width  = 160
        self.base_height =  90

        self.center = [self.base_width//2, self.base_height//2]

        self.is_exit = False

        pygame.init()
        pygame.display.init()

        pygame.mouse.set_visible(False)

        self.display = pygame.display.set_mode((width, height,))

        axis = self.center
        background = pygame.Surface((self.base_width, self.base_height,))

        # draw x-axis
        pygame.draw.line(background, [0xff, 0, 0], [0, axis[1]], [self.base_width, axis[1]], 1)

        # draw y-axis
        pygame.draw.line(background, [0, 0xff, 0], [axis[0], 0], [axis[0], self.base_height], 1)

        self.background     = background
        self.surface_back   = pygame.Surface((self.base_width, self.base_height,))
        self.surface_front  = pygame.Surface((self.base_width, self.base_height,))

        self.ir_raw = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        self.ir     = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        self.cursor = [1.0, 1.0]

    def open(self) -> None:
        self.open_sock()

    def close(self) -> None:
        self.close_sock()

    def loop(self) -> None:
        self.is_exit = False
        while not self.is_exit:
            self.read_sock()

            self.surface_back.blit(self.background,  (0, 0,))

            for i in range(4):
                dot_raw     = self.ir_raw[i]

                if dot_raw[2]:
                    point = [
                        int(dot_raw[0] * self.base_width),
                        int(dot_raw[1] * self.base_height),
                    ]
                    pygame.draw.circle(
                            self.surface_back,
                            [0xe3, 0xc8, 0xe4], point, 3)

            self.surface_front.blit(self.surface_back, (0, 0,))

            for i in range(4):
                dot_sorted  = self.ir[i]

                point = [
                    int(dot_sorted[0] * self.base_width),
                    int(dot_sorted[1] * self.base_height),
                ]
                pygame.draw.circle(
                        self.surface_front,
                        COLOR[i],
                        point,  3, width=0 if dot_sorted[2] else 1)

            cursor = [
                int(self.cursor[0] * self.base_width),
                int(self.cursor[1] * self.base_height),
            ]
            pygame.draw.circle(
                    self.surface_front,
                    [0xe3, 0xc8, 0xe4],
                    cursor, 3, width=1)

            scaled_surface = pygame.transform.scale(self.surface_front, (self.width, self.height))
            self.display.blit(scaled_surface, (0, 0))

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT or \
                        (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    self.is_exit = True

    def open_sock(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.setblocking(False)

    def read_sock(self) -> None:
        try:
            data, _ = self.sock.recvfrom(STRUCT_DATA_SIZE)
            index, button, \
            ir_raw_0_x, ir_raw_0_y, ir_raw_0_z, \
            ir_raw_1_x, ir_raw_1_y, ir_raw_1_z, \
            ir_raw_2_x, ir_raw_2_y, ir_raw_2_z, \
            ir_raw_3_x, ir_raw_3_y, ir_raw_3_z, \
            ir_0_x,     ir_0_y,     ir_0_z,     \
            ir_1_x,     ir_1_y,     ir_1_z,     \
            ir_2_x,     ir_2_y,     ir_2_z,     \
            ir_3_x,     ir_3_y,     ir_3_z,     \
            cursor_x, cursor_y = struct.unpack(STRUCT_DATA, data)

            if button & (1 << 0x7):
                self.is_exit = True

            self.ir_raw = [
                [ir_raw_0_x, ir_raw_0_y, ir_raw_0_z],
                [ir_raw_1_x, ir_raw_1_y, ir_raw_1_z],
                [ir_raw_2_x, ir_raw_2_y, ir_raw_2_z],
                [ir_raw_3_x, ir_raw_3_y, ir_raw_3_z],
            ]

            self.ir = [
                [ir_0_x, ir_0_y, ir_0_z],
                [ir_1_x, ir_1_y, ir_1_z],
                [ir_2_x, ir_2_y, ir_2_z],
                [ir_3_x, ir_3_y, ir_3_z],
            ]

            self.cursor = [cursor_x, cursor_y,]

        except BlockingIOError:
            pass

    def close_sock(self) -> None:
        self.sock.close()
