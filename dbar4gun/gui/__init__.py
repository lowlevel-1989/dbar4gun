import sys
import pygame
import socket

class GUI(object):
    def __init__(self,
                 width  : int =  1280,
                 height : int =   720,
                 port   : int = 35460):

        self.port   = port
        self.width  = width
        self.height = height
        self.center = [width//2, height//2]

        pygame.init()
        pygame.display.init()

        pygame.mouse.set_visible(False)

        self.display = pygame.display.set_mode((width, height,))

        axis = self.center
        background = pygame.Surface((width, height,))

        # draw x-axis
        pygame.draw.line(background, [0xff, 0, 0], [0, axis[1]], [width, axis[1]], 1)

        # draw y-axis
        pygame.draw.line(background, [0, 0xff, 0], [axis[0], 0], [axis[0], height], 1)

        self.background = background

    def open(self) -> None:
        self.open_sock()

    def close(self) -> None:
        self.close_sock()

    def loop(self) -> None:
        is_exit = False
        while not is_exit:
            self.display.blit(self.background, (0, 0,))

            self.read_sock()

            # draw here

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    is_exit = True

    def open_sock(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.setblocking(False)

    def read_sock(self) -> None:
        try:
            data, _ = self.sock.recvfrom(1024) # buffer size is 1024 bytes
            print("received message: %s" % data)
        except BlockingIOError:
            pass

    def close_sock(self) -> None:
        self.sock.close()
