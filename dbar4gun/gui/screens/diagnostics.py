"""
IR diagnostics: dots en bruto, TL/TR, fuentes IR extra, bateria y Hz.
"""


import pygame

from dbar4gun.gui.draw import GREY, RED
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.wiimotes import BTN_HOME, BTN_ONE
from dbar4gun.gui.screens.base import GunScreen


class DiagnosticsScreen(GunScreen):
    """dots en bruto, TL/TR, fuentes IR extra, bateria y Hz."""

    def __init__(self, app, virtualgun):
        super(DiagnosticsScreen, self).__init__(app, virtualgun)
        self.extended = False
        self.message = None

    def update(self, now):
        g = self.gun
        if g is not None and g.was_pressed(BTN_ONE):
            # tamano de los dots: modo IR extendido por el socket de control (experimental)
            mode = "basic" if self.extended else "extended"
            reply = self.app.control.send("irmode {}".format(mode))
            if reply.get("ok"):
                self.extended = not self.extended
                self.message = None
            else:
                self.message = reply.get("error", "?")
        if g is not None and g.was_pressed(BTN_HOME) and self.extended:
            self.app.control.send("irmode basic")
        self.back_on_home(now)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        rect = pygame.Rect(w // 20, h // 8, int(h * 0.7 * 4 / 3), int(h * 0.7))
        app.draw_camera(surf, rect, p, big=True)
        x = rect.right + w // 30
        y = rect.top
        for line, color in app.gun_lines(p, self.vg):
            app.text(surf, line, (x, y), app.font, color)
            y += app.font.get_height() + 6
        app.text(surf, t("diag.size_hint"), (x, y + 10), app.font_small, GREY)
        if self.message:
            app.text(surf, self.message, (x, y + 40), app.font_small, RED)
        app.text(surf, t("hint_back"), (w // 2, h - app.font.get_height() * 2), app.font, GREY, center=True)
