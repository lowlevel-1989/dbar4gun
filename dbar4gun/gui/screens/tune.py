"""
Auto-tune del One Euro: 3 s quieto (fc_min) y 3 s moviendo (beta).
"""

import pygame

from dbar4gun.gui.draw import GREY, MAGENTA, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.tune import choose_beta, choose_fc_min, motion_amount
from dbar4gun.gui.logic.wiimotes import BTN_A
from dbar4gun.gui.screens.base import GunScreen


class TuneScreen(GunScreen):
    """auto-tune del One Euro (3 s quieto -> fc_min, 3 s moviendo -> beta)."""

    DURATION = 3.0
    MIN_MOTION_GAME = 300.0

    def __init__(self, app, virtualgun):
        super(TuneScreen, self).__init__(app, virtualgun)
        self.state = "still_intro"
        self.samples = []
        self.t0 = 0.0
        self.fc = self.jitter = self.beta = self.lag = None
        p = self.packet
        self.area = p.area if p else (0.0, 0.0, 1.0, 1.0)

    def dt(self):
        p = self.packet
        return 1.0 / p.hz if p is not None and p.hz > 10 else 0.01

    def update(self, now):
        g = self.gun
        if g is None:
            self.back_on_home(now)
            return
        if self.back_on_home(now):
            return
        st = self.state
        if st in ("still_intro", "move_intro", "move_again") and g.was_pressed(BTN_A):
            self.samples = []
            self.t0 = now
            self.state = "still" if st == "still_intro" else "move"
        elif st in ("still", "move"):
            self.samples += [p.screen for p in g.frame_packets if p.has(0x20)]
            if now - self.t0 >= self.DURATION and len(self.samples) > 30:
                if st == "still":
                    self.fc, self.jitter = choose_fc_min(self.samples, self.area, self.dt())
                    self.state = "move_intro"
                elif motion_amount(self.samples, self.area) < self.MIN_MOTION_GAME:
                    self.state = "move_again"
                else:
                    self.beta, self.lag = choose_beta(self.samples, self.fc, self.area, self.dt())
                    self.state = "result"
        elif st == "result" and g.was_pressed(BTN_A):
            reply = self.app.control.send("filter {} {:.3f} {:.2f}".format(self.vg, self.fc, self.beta))
            self.state = "applied" if reply.get("ok") else "result"

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        st = self.state
        text = {
            "still_intro": t("tune.still"),
            "move_intro": t("tune.move"),
            "move_again": t("tune.move_again"),
            "applied": t("tune.applied"),
        }.get(st)
        if st in ("still", "move"):
            text = t("tune.recording", s=max(0.0, self.DURATION - (app.now - self.t0)))
        if st in ("result", "applied") or (st.startswith("move") and self.fc):
            app.text(surf, t("tune.result", fc=self.fc or 0, j=self.jitter or 0, b=self.beta or 0,
                             l=self.lag or 0), (w // 2, h // 2), app.font, WHITE, center=True)
        if st == "result":
            text = t("tune.apply")
        if text:
            app.text(surf, text, (w // 2, h // 3), app.font_big, YELLOW, center=True)
        app.draw_target(surf, (w // 2, h // 2 - h // 6), GREY)
        p = self.packet
        if p is not None:
            pygame.draw.circle(surf, MAGENTA, (int(p.cursor[0] * w), int(p.cursor[1] * h)), 10, 3)
        app.draw_camera(surf, app.inset_rect(), p)
