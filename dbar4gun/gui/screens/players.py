"""
Players: mapa de jugadores y prueba de botones (teclas y combos).
"""

from dbar4gun.gui.draw import CYAN, GREY, GUN_COLORS, WHITE
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.wiimotes import (
    BTN_A, BTN_B, BTN_DOWN, BTN_HOME, BTN_LEFT, BTN_MINUS, BTN_ONE, BTN_PLUS, BTN_RIGHT,
    BTN_TWO, BTN_UP,
)
from dbar4gun.gui.screens.base import GunScreen


class PlayersScreen(GunScreen):
    """mapa de jugadores y prueba de botones (teclas y combos emitidos)."""

    HOLD = 1.0

    def __init__(self, app, virtualgun):
        super(PlayersScreen, self).__init__(app, virtualgun)
        self.home_since = None

    def update(self, now):
        g = self.gun
        held = g is not None and g.packet is not None and g.packet.buttons & BTN_HOME
        if held:
            if self.home_since is None:
                self.home_since = now
            elif now - self.home_since >= self.HOLD:
                self.app.go_menu()
        else:
            self.home_since = None

    def draw(self, surf):
        from dbar4gun.wiimote import player_leds
        from dbar4gun.virtualgun import describe_outputs

        app = self.app
        w, h = surf.get_size()
        app.text(surf, t("players.title"), (w // 2, h // 12), app.font_big, WHITE, center=True)
        y = h // 6
        names = {BTN_A: "A", BTN_B: "B", BTN_ONE: "1", BTN_TWO: "2", BTN_PLUS: "+",
                 BTN_MINUS: "-", BTN_HOME: "Home", BTN_UP: "Up", BTN_DOWN: "Down",
                 BTN_LEFT: "Left", BTN_RIGHT: "Right"}
        for g in app.hub.active(app.now):
            p = g.packet
            mask = player_leds(p.index)
            leds = "".join("#" if mask & bit else "." for bit in (0x10, 0x20, 0x40, 0x80))
            col = GUN_COLORS[(g.virtualgun - 1) % 4]
            # RetroArch cuenta el mouse index desde 0; el driver, desde 1
            app.text(surf, t("players.row", leds=leds, vg=g.virtualgun, idx=max(0, p.index - 1)), (w // 10, y),
                     app.font, col)
            y += app.font.get_height() + 4
            pressed = [n for b, n in names.items() if p.buttons & b]
            app.text(surf, t("players.buttons", b=" ".join(pressed) or "-"), (w // 8, y), app.font_small, WHITE)
            y += app.font_small.get_height() + 2
            outs = describe_outputs(p.buttons, g.virtualgun - 1)
            app.text(surf, t("players.outputs", o=" ".join(outs) or "-"), (w // 8, y), app.font_small, CYAN)
            y += app.font_small.get_height() + 14
        app.text(surf, t("players.hint"), (w // 2, h - app.font.get_height() * 2), app.font, GREY, center=True)
