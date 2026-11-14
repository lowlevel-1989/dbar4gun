"""
Ventana del calibrator y bucle principal.

App abre la ventana de pygame, lee en cada frame los paquetes de los
Wiimotes (logic/wiimotes.py), actualiza la pantalla activa (screens/) y la
dibuja. Las funciones de dibujo compartidas las hereda de draw.Drawing.
"""

import time

import pygame

from dbar4gun.control import send_command, SOCKET_PATH
from dbar4gun.core.hardware import HardwareConfig
from dbar4gun.gui.draw import BLACK, Drawing
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.wiimotes import Hub, PacketSource
from dbar4gun.gui.screens.menu import MenuScreen


# el calibrator dibuja a como mucho 720 lineas con el aspecto de la pantalla, y
# la GPU lo escala a pantalla completa (pygame SCALED): en una Pi 5 dibujar a 4K
# cuesta 16-28 ms por frame (no llega a 60 fps), a 720p 2-4 ms, y lo que se sube
# a la pantalla en cada frame es la imagen pequena. Mismo aspecto que la TV: los
# targets salen donde el driver los espera (un 640x480 con bandas en una TV 16:9
# los desplazaria)
MAX_NATIVE_HEIGHT = 720


def native_size(info):
    """
    (ancho, alto) en que dibuja el calibrator: el de la pantalla, o reducido a
    MAX_NATIVE_HEIGHT con su aspecto (una TV 4K: 1280x720, escalado por la GPU).
    (0, 0) si SDL no la sabe: entonces elige SDL.
    """
    w, h = getattr(info, "current_w", 0) or 0, getattr(info, "current_h", 0) or 0
    if w <= 0 or h <= 0:
        return 0, 0
    if h <= MAX_NATIVE_HEIGHT:
        return w, h
    return int(round(w * MAX_NATIVE_HEIGHT / float(h))), MAX_NATIVE_HEIGHT


class Control(object):
    """Cliente del socket de control (inyectable en los tests)."""

    def __init__(self, path=SOCKET_PATH):
        self.path = path

    def send(self, line):
        try:
            return send_command(line, self.path, timeout=1.5)
        except (OSError, ValueError) as e:
            return {"ok": False, "error": str(e)}


class App(Drawing):
    def __init__(self, width=0, height=0, port=35460, fullscreen=True, socket_path=SOCKET_PATH,
                 source=None, control=None, display=True):
        # solo pantalla y fuentes: pygame.init() abriria los joysticks, y por
        # Bluetooth el Wiimote es uno (hid-wiimote); al cerrarlos, el kernel
        # apaga la camara IR del Wiimote
        pygame.display.init()
        pygame.font.init()
        if display and not width and not height:
            width, height = native_size(pygame.display.Info())
        flags = pygame.FULLSCREEN if fullscreen else 0
        if display:
            self.surface = None
            if fullscreen and width and height:
                # sin cambiar el modo de video: la GPU escala la imagen pequena
                try:
                    self.surface = pygame.display.set_mode((width, height), flags | pygame.SCALED)
                except (pygame.error, AttributeError):
                    self.surface = None
            if self.surface is None:
                self.surface = pygame.display.set_mode((width, height), flags)
            pygame.display.set_caption(t("title"))
            pygame.mouse.set_visible(False)
        else:
            self.surface = pygame.Surface((width or 1280, height or 720))
        self.size = self.surface.get_size()
        h = self.size[1]
        self.font_small = pygame.font.Font(None, max(18, h // 36))
        self.font = pygame.font.Font(None, max(24, h // 24))
        self.font_big = pygame.font.Font(None, max(32, h // 14))

        self.source = source if source is not None else PacketSource(port)
        self.control = control if control is not None else Control(socket_path)
        self.hub = Hub()
        # FOV, signo del acelerometro y ancho de barra del daemon
        self.hardware = HardwareConfig()
        self.status_reply = {}
        self.screen = MenuScreen(self)
        self.running = True
        self.now = time.monotonic()
        self.clock = pygame.time.Clock()

    def go(self, screen):
        self.screen = screen
        # los flancos de este frame no deben pasar a la pantalla nueva
        for g in self.hub.guns.values():
            g.pressed = 0

    def refresh_status(self):
        reply = self.control.send("status")
        if reply.get("ok"):
            self.status_reply = reply
            if reply.get("hardware"):
                self.hardware = HardwareConfig.from_dict(reply["hardware"])
        out = {}
        for gun in reply.get("wiimotes", []) if reply.get("ok") else []:
            vg = gun.get("virtualgun")
            out[vg] = gun
            if vg in self.hub.guns:
                self.hub.guns[vg].status = gun
        return out

    # ------------------------------------------------------------------
    def step(self, now=None):
        """Un frame: vaciar el socket, actualizar y dibujar."""
        self.now = time.monotonic() if now is None else now
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
        self.hub.update(self.source.drain(), self.now)
        self.screen.update(self.now)
        self.surface.fill(BLACK)
        self.screen.draw(self.surface)

    def loop(self):
        while self.running:
            self.step()
            pygame.display.flip()
            self.clock.tick(60)

    def close(self):
        try:
            self.source.close()
        except Exception:
            pass
        pygame.quit()

    def go_menu(self):
        self.go(MenuScreen(self))
