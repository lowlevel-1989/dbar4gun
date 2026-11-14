"""
Calibrate: wizard de calibracion (disparar a los targets y verificar).
"""

import pygame

from dbar4gun.core.calibration.session import CALIBRATION_SHOTS
from dbar4gun.gui.draw import CYAN, GREEN, GREY, MAGENTA, RED, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.calibration import (
    adaptive_targets, geometry_check, stability, verify_error_px, VERIFY_MAX_PX,
)
from dbar4gun.gui.logic.wiimotes import BTN_A, BTN_B, BTN_HOME, BTN_ONE
from dbar4gun.gui.screens.base import GunScreen
from dbar4gun.protocol import FLAG_CALIBRATED


class WizardScreen(GunScreen):
    """wizard de calibracion."""

    def __init__(self, app, virtualgun):
        super(WizardScreen, self).__init__(app, virtualgun)
        self.state = "intro"
        self.message = None
        self.seen_calibrating = False
        self.error_px = None
        self.ratio = None

    def start(self):
        p = self.packet
        g = self.gun
        reach = g.reach if g else None
        status = self.app.refresh_status().get(self.vg, {})
        if status.get("mode_option") == 0:
            self.message = (t("wiz.failed", e="calibration disabled (--calibration 0)"), RED)
            return
        points = {1: 2, 3: 4}.get(status.get("mode_option"), 3)
        if points == 2:
            # modo 1: centro y arriba a la izquierda (escala y offset por eje)
            x0, y0, aw, ah = p.area if p else (0, 0, 1, 1)
            targets = [(x0 + 0.5 * aw, y0 + 0.5 * ah), (x0 + 0.1 * aw, y0 + 0.1 * ah)]
        else:
            targets = adaptive_targets(p.area if p else (0, 0, 1, 1), p.useful_zone if p else 0.85,
                                       reach, points)
        flat = ",".join("{:.4f},{:.4f}".format(x, y) for x, y in targets)
        reply = self.app.control.send("calibrate {} full targets={}".format(self.vg, flat))
        if not reply.get("ok") or self.vg not in reply.get("started", []):
            self.message = (t("wiz.failed", e=reply.get("error", "?")), RED)
            return
        self.state = "capture"
        self.message = None
        self.seen_calibrating = False

    def update(self, now):
        g = self.gun
        if g is None:
            self.back_on_home(now)
            return
        p = g.packet

        if self.state == "intro":
            if self.back_on_home(now):
                return
            if g.was_pressed(BTN_A):
                self.start()

        elif self.state == "capture":
            if g.was_pressed(BTN_HOME):
                self.app.control.send("cancel")
                self.app.go_menu()
                return
            if p is None:
                return
            if p.calibrating:
                self.seen_calibrating = True
                if p.error:
                    self.message = (t("wiz.err." + p.error), RED)
                elif g.was_pressed(BTN_B):
                    self.message = None
            elif self.seen_calibrating:
                if p.has(FLAG_CALIBRATED):
                    self.check_geometry()
                else:
                    # cancelada (A+minus en el Wiimote)
                    self.state = "intro"

        elif self.state == "geometry":
            if g.was_pressed(BTN_A):
                self.state = "intro"
                self.start()
            elif g.was_pressed(BTN_HOME):
                self.state = "verify"

        elif self.state == "verify":
            if g.was_pressed(BTN_HOME):
                self.state = "done"
            elif g.was_pressed(BTN_ONE):
                # repetir la calibracion (el 1, no el gatillo: no se pulsa sin querer)
                self.start()
            elif g.was_pressed(BTN_B):
                samples = g.samples_before_last_b()
                self.error_px = verify_error_px(samples, self.center(), self.app.size)
                if self.error_px is not None and self.error_px <= VERIFY_MAX_PX:
                    self.state = "done"
                else:
                    self.state = "verify_bad"

        elif self.state == "verify_bad":
            if g.was_pressed(BTN_A):
                self.start()
            elif g.was_pressed(BTN_B):
                self.state = "verify"
            elif g.was_pressed(BTN_HOME):
                self.state = "done"

        elif self.state == "done":
            # cada jugador entra en Calibrar desde el menu con su Wiimote
            if g.was_pressed(BTN_ONE):
                self.start()
            elif g.was_pressed(BTN_HOME) or g.was_pressed(BTN_A):
                self.app.go_menu()
                return

    def check_geometry(self):
        status = self.app.refresh_status().get(self.vg, {})
        if status.get("calibration_mode") == 3:
            # con 4 puntos el mapa corrige la perspectiva y su proporcion cambia
            # por la pantalla: medida en un punto da avisos falsos. El driver
            # ya rechaza las calibraciones imposibles y la comprobacion del
            # centro mide el error real
            self.ratio = None
            self.state = "verify"
            return
        ok, ratio = geometry_check(status.get("scale_ratio"), status.get("screen_aspect", 16.0 / 9.0))
        self.ratio = (ratio, status.get("screen_aspect", 16.0 / 9.0))
        self.state = "verify" if ok else "geometry"

    def center(self):
        p = self.packet
        x0, y0, w, h = p.area if p else (0, 0, 1, 1)
        return (x0 + 0.5 * w, y0 + 0.5 * h)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        app.draw_screen_overlay(surf, p)
        cx = w // 2
        y = h // 3

        if self.state == "intro":
            app.text(surf, t("wiz.intro", vg=self.vg), (cx, y), app.font_big, WHITE, center=True)
            app.text(surf, t("wiz.intro2"), (cx, y + app.font_big.get_height() + 10), app.font, GREY, center=True)
        elif self.state == "capture" and p is not None and p.calibrating:
            tx, ty = int(p.target[0] * w), int(p.target[1] * h)
            app.draw_target(surf, (tx, ty), YELLOW)
            stab = stability(p.spread)
            color = {"good": GREEN, "ok": YELLOW, "bad": RED}.get(stab, GREY)
            radius = int(max(12, min(h // 4, p.spread * h * 0.6))) if p.spread >= 0 else 12
            pygame.draw.circle(surf, color, (tx, ty), radius, 4)
            app.text(surf, t("wiz.point", i=p.step + 1, n=p.total), (cx, h // 2), app.font_big, WHITE, center=True)
            # vueltas a los targets (el daemon manda los disparos validos de la sesion)
            if CALIBRATION_SHOTS > 1:
                n = p.total * CALIBRATION_SHOTS
                app.text(surf, t("wiz.shot", i=min(p.captured + 1, n), n=n,
                                 r=min(p.captured // max(1, p.total) + 1, CALIBRATION_SHOTS),
                                 m=CALIBRATION_SHOTS),
                         (cx, h // 2 + app.font_big.get_height() + 6), app.font, GREY, center=True)
        elif self.state == "geometry":
            r, e = self.ratio
            app.text(surf, t("wiz.geometry_bad", r=r or 0, e=e), (cx, y), app.font, RED, center=True)
        elif self.state in ("verify", "verify_bad"):
            c = self.center()
            app.draw_target(surf, (int(c[0] * w), int(c[1] * h)), CYAN)
            if p is not None:
                pygame.draw.circle(surf, MAGENTA, (int(p.screen[0] * w), int(p.screen[1] * h)), 10, 3)
            if self.state == "verify":
                app.text(surf, t("wiz.verify"), (cx, h // 6), app.font_big, WHITE, center=True)
                app.text(surf, t("wiz.verify_hint"), (cx, h // 6 + app.font_big.get_height() + 6),
                         app.font, GREY, center=True)
            else:
                app.text(surf, t("wiz.verify_bad", e=self.error_px or 0, m=VERIFY_MAX_PX),
                         (cx, h // 6), app.font, RED, center=True)
        elif self.state == "done":
            y0 = h // 3
            if self.error_px is not None:
                app.text(surf, t("wiz.verify_ok", e=self.error_px), (cx, y0 - app.font_big.get_height() - 10),
                         app.font, GREEN, center=True)
            app.text(surf, t("wiz.done", vg=self.vg), (cx, y0), app.font_big, GREEN, center=True)
            app.text(surf, t("wiz.next"), (cx, y0 + app.font_big.get_height() + 10), app.font, GREY, center=True)

        if self.message:
            app.text(surf, self.message[0], (cx, int(h * 0.8)), app.font, self.message[1], center=True)
        target = None
        if self.state == "capture" and p is not None and p.calibrating:
            target = (int(p.target[0] * w), int(p.target[1] * h))
        app.draw_camera(surf, app.inset_rect(avoid=target), p)
