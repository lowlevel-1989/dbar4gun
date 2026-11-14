"""
Installation: distancia, barra nivelada y barra centrada.
"""

import math

import pygame

from dbar4gun.gui.draw import CYAN, GREEN, GREY, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.calibration import (
    bar_position, bar_tilt_deg, distance_m, reference_distance_m,
)
from dbar4gun.gui.screens.base import GunScreen


class InstallScreen(GunScreen):
    """distancia, barra nivelada y barra centrada."""

    def __init__(self, app, virtualgun):
        super(InstallScreen, self).__init__(app, virtualgun)
        self.next_status = 0.0

    def update(self, now):
        if self.back_on_home(now):
            return
        if now >= self.next_status:
            self.next_status = now + 1.0
            self.app.refresh_status()

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        lines = []

        d = distance_m(p, app.hardware)
        ref = reference_distance_m(p, app.hardware)
        if d is None:
            lines.append((t("distance_na"), GREY))
        elif ref:
            close = abs(d - ref) <= 0.15 * ref
            lines.append((t("distance_ref", d=d, r=ref), GREEN if close else YELLOW))
        else:
            lines.append((t("distance", d=d), WHITE))

        tilt = bar_tilt_deg(p)
        if tilt is None:
            lines.append((t("level_na"), GREY))
        else:
            ok = abs(tilt) <= 2.0
            lines.append((t("level_ok") if ok else t("level", v=tilt), GREEN if ok else YELLOW))
        if p is not None and not math.isnan(p.roll):
            lines.append((t("roll", v=p.roll), GREY))

        status = self.gun.status if self.gun else {}
        pos = bar_position(status) if status.get("calibrated") else None
        if pos is None:
            lines.append((t("center_na"), GREY))
        else:
            off = (pos[0] - 0.5) * 100.0
            lines.append((t("center", x=off), GREEN if abs(off) <= 3 else YELLOW))
            # la barra segun la calibracion
            bx, by = int(pos[0] * w), int(max(0.0, min(1.0, pos[1])) * h)
            pygame.draw.line(surf, CYAN, (bx - w // 20, by), (bx + w // 20, by), 6)

        y = h // 5
        for text, color in lines:
            app.text(surf, text, (w // 10, y), app.font_big, color)
            y += app.font_big.get_height() + 12

        # nivel: linea de la barra girada segun la inclinacion medida
        if tilt is not None:
            cx, cy, r = w // 2, int(h * 0.72), w // 6
            a = math.radians(tilt)
            pygame.draw.line(surf, GREY, (cx - r, cy), (cx + r, cy), 2)
            pygame.draw.line(surf, GREEN if abs(tilt) <= 2 else YELLOW,
                             (cx - r * math.cos(a), cy + r * math.sin(a)),
                             (cx + r * math.cos(a), cy - r * math.sin(a)), 6)
        app.draw_camera(surf, app.inset_rect(), p)
        app.text(surf, t("hint_back"), (w // 2, h - app.font.get_height() * 2), app.font, GREY, center=True)
