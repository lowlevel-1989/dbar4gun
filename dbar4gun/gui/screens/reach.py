"""
Reach test: rastro verde/amarillo/rojo y distancia recomendada.

Pensada para la barra encima de la TV. Con la barra debajo sale cerca del
100% y no afecta a la calibracion (ver ReachTest en logic/calibration.py).
"""

import pygame

from dbar4gun.gui.draw import BLACK, GREEN, RED, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.calibration import distance_m, ReachTest, recommend_distance
from dbar4gun.gui.logic.wiimotes import BTN_A
from dbar4gun.gui.screens.base import GunScreen


class ReachScreen(GunScreen):
    """rastro verde/amarillo/rojo y distancia recomendada."""

    def __init__(self, app, virtualgun):
        super(ReachScreen, self).__init__(app, virtualgun)
        self.test = ReachTest()
        self.done = False
        self.result = None
        # al terminar el barrido la barra suele estar fuera de vista
        self.distance = None
        # el rastro se pinta en su propia superficie, solo los puntos nuevos
        # (redibujar miles de circulos por frame costaba ~10 ms en una Pi 5)
        self.trail_surf = None
        self.trail_drawn = 0

    def update(self, now):
        if self.back_on_home(now):
            return
        g = self.gun
        if g is None:
            return
        if not self.done:
            for p in g.frame_packets:
                self.test.add(p)
                d = distance_m(p, self.app.hardware)
                if d:
                    self.distance = d
            if g.was_pressed(BTN_A):
                self.finish()
        elif g.was_pressed(BTN_A):
            self.app.go_menu()

    def finish(self):
        self.done = True
        reach = self.test.reach()
        p = self.packet
        g = self.gun
        if g is not None:
            g.reach = reach
        uz = p.useful_zone if p else 0.85
        factor, dist = recommend_distance(self.distance, reach, uz)
        self.result = (reach, uz, factor, dist)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        app.draw_screen_overlay(surf, p)
        colors = {2: GREEN, 1: YELLOW, 0: RED}
        trail = self.test.trail
        if self.trail_surf is None or self.trail_surf.get_size() != (w, h) or \
                self.trail_drawn > len(trail):
            self.trail_surf = pygame.Surface((w, h))
            self.trail_surf.set_colorkey(BLACK)
            self.trail_drawn = 0
        for x, y, n in trail[self.trail_drawn:]:
            pygame.draw.circle(self.trail_surf, colors[n], (int(x * w), int(y * h)), 5)
        self.trail_drawn = len(trail)
        surf.blit(self.trail_surf, (0, 0))
        if not self.done:
            app.text(surf, t("reach.help"), (w // 2, h // 12), app.font_big, WHITE, center=True)
        else:
            reach, uz, factor, dist = self.result
            y = h // 12
            if reach is None:
                app.text(surf, t("reach.none"), (w // 2, y), app.font_big, RED, center=True)
            else:
                app.text(surf, t("reach.result", r=reach * 100, u=uz * 100), (w // 2, y),
                         app.font_big, WHITE, center=True)
                y += app.font_big.get_height() + 10
                if factor <= 1.0:
                    msg, color = t("reach.ok"), GREEN
                elif dist:
                    msg, color = t("reach.move", d=dist, f=factor), YELLOW
                else:
                    msg, color = t("reach.move_nod", f=factor), YELLOW
                app.text(surf, msg, (w // 2, y), app.font_big, color, center=True)
        app.draw_camera(surf, app.inset_rect(), p)
