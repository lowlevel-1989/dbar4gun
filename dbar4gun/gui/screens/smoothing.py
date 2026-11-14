"""
Smoothing de un Wiimote: cada jugador elige el suyo.

Por defecto cada Wiimote usa el del servicio (--smoothing-level). El cambio se
aplica al momento, para notarlo apuntando, y se guarda con la calibracion.
"""

import pygame

from dbar4gun.core.filters import MAX_LEVEL
from dbar4gun.gui.draw import CYAN, DARK, GREY, GUN_COLORS, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.wiimotes import BTN_A, BTN_DOWN, BTN_LEFT, BTN_RIGHT, BTN_UP
from dbar4gun.gui.screens.base import GunScreen
from dbar4gun.gui.screens.gallery import draw_round_target


class SmoothingScreen(GunScreen):
    """arriba/abajo cambian el smoothing; A vuelve al del servicio."""

    def __init__(self, app, virtualgun):
        super(SmoothingScreen, self).__init__(app, virtualgun)
        self.reload()
        self.error = False

    def reload(self):
        st = self.app.refresh_status().get(self.vg, {})
        self.level = st.get("smoothing_level", 0)
        self.own = st.get("smoothing_own", False)
        self.default = st.get("smoothing_default", 0)
        self.calibrated = st.get("calibrated", False)

    def send(self, value):
        reply = self.app.control.send("smoothing {} {}".format(self.vg, value))
        self.error = not reply.get("ok")
        self.reload()

    def update(self, now):
        g = self.gun
        if g is None or self.back_on_home(now):
            return
        if g.was_pressed(BTN_UP) or g.was_pressed(BTN_RIGHT):
            if self.level < MAX_LEVEL:
                self.send(self.level + 1)
        elif g.was_pressed(BTN_DOWN) or g.was_pressed(BTN_LEFT):
            if self.level > 0:
                self.send(self.level - 1)
        elif g.was_pressed(BTN_A) and self.own:
            self.send("default")

    def draw_who(self, surf, y):
        """A que Wiimote se aplica: su VirtualGun, en su color, y sus LEDs."""
        app = self.app
        w = surf.get_width()
        color = GUN_COLORS[(self.vg - 1) % 4]
        label = t("player", vg=self.vg)
        led = app.font_big.get_height() // 2
        gap = led // 2
        leds_w = 4 * led + 3 * gap
        total = app.font_big.size(label)[0] + 2 * led + leds_w
        x = (w - total) // 2
        app.text(surf, label, (x, y), app.font_big, color)
        x += app.font_big.size(label)[0] + 2 * led
        p = self.packet
        mask = 0
        if p is not None:
            from dbar4gun.wiimote import player_leds
            mask = player_leds(p.index)
        cy = y + app.font_big.get_height() // 2 - led // 2
        for i, bit in enumerate((0x10, 0x20, 0x40, 0x80)):
            r = pygame.Rect(x + i * (led + gap), cy, led, led)
            pygame.draw.rect(surf, color if mask & bit else DARK, r)
            pygame.draw.rect(surf, GREY, r, 1)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        y = h // 14
        self.draw_who(surf, y)
        y += app.font_big.get_height() + 14
        app.text(surf, t("smooth.only"), (w // 2, y), app.font, WHITE, center=True)
        y += app.font.get_height() + 14
        app.text(surf, t("smooth.title", lvl=self.level), (w // 2, y), app.font_big, YELLOW, center=True)
        y += app.font_big.get_height() + 4
        note = t("smooth.own", d=self.default) if self.own else t("smooth.default")
        app.text(surf, note, (w // 2, y), app.font, WHITE, center=True)
        y += app.font.get_height() + 16

        # una casilla por nivel: la elegida rellena, la del servicio marcada
        box = max(18, w // 40)
        gap = box // 2
        x = (w - (MAX_LEVEL + 1) * box - MAX_LEVEL * gap) // 2
        for lvl in range(MAX_LEVEL + 1):
            r = pygame.Rect(x + lvl * (box + gap), y, box, box)
            if lvl == self.level:
                pygame.draw.rect(surf, YELLOW, r)
            pygame.draw.rect(surf, CYAN if lvl == self.default else GREY, r, 2)
            app.text(surf, str(lvl), (r.centerx, r.bottom + 4 + app.font_small.get_height() // 2),
                     app.font_small, CYAN if lvl == self.default else GREY, center=True)
        y += box + app.font_small.get_height() + 16

        for key in ("smooth.help", "smooth.try"):
            for part in app.wrap(t(key), app.font, w - w // 5):
                app.text(surf, part, (w // 2, y), app.font, GREY, center=True)
                y += app.font.get_height() + 2
        if not self.calibrated:
            app.text(surf, t("smooth.unsaved"), (w // 2, y + 8), app.font, YELLOW, center=True)
        if self.error:
            app.text(surf, t("smooth.error"), (w // 2, y + 8 + app.font.get_height()), app.font, YELLOW,
                     center=True)

        # un target para apuntar y notar el cambio
        draw_round_target(surf, (w // 2, h * 2 // 3), h // 24)
        p = self.packet
        if p is not None:
            pygame.draw.circle(surf, GUN_COLORS[(self.vg - 1) % 4],
                               (int(p.cursor[0] * w), int(p.cursor[1] * h)), 10, 3)
        app.text(surf, t("smooth.hint"), (w // 2, h - app.font.get_height() * 2), app.font, GREY,
                 center=True)
