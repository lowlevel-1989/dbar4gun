"""
Profiles: previsualizar el area, editar un area custom y la useful zone.
"""

import pygame

from dbar4gun.gui.draw import CYAN, GREEN, GREY, RED, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.wiimotes import BTN_A, BTN_B, BTN_DOWN, BTN_LEFT, BTN_RIGHT, BTN_UP
from dbar4gun.gui.screens.base import GunScreen


class ProfilesScreen(GunScreen):
    """previsualizar el area, editar un area custom y la useful zone."""

    PRESETS = ["full", "4:3", "custom"]
    FIELDS = ["preset", "x0", "y0", "w", "h", "useful_zone"]
    STEP = 0.005

    def __init__(self, app, virtualgun):
        super(ProfilesScreen, self).__init__(app, virtualgun)
        p = self.packet
        x0, y0, aw, ah = p.area if p else (0.0, 0.0, 1.0, 1.0)
        self.values = {"x0": x0, "y0": y0, "w": aw, "h": ah,
                       "useful_zone": p.useful_zone if p else 0.85}
        self.preset = "full" if (x0, y0, aw, ah) == (0.0, 0.0, 1.0, 1.0) else "custom"
        self.sel = 0
        self.message = None

    def profile(self):
        if self.preset != "custom":
            return self.preset
        v = self.values
        return "custom:{:.4f},{:.4f},{:.4f},{:.4f}".format(v["x0"], v["y0"], v["w"], v["h"])

    def preview_area(self):
        from dbar4gun.core.area import AreaProfile
        try:
            a = AreaProfile.parse(self.profile(), float(self.app.size[0]) / self.app.size[1])
            return (a.x0, a.y0, a.w, a.h)
        except ValueError:
            return None

    def change(self, d):
        f = self.FIELDS[self.sel]
        if f == "preset":
            i = self.PRESETS.index(self.preset)
            self.preset = self.PRESETS[(i + d) % len(self.PRESETS)]
            if self.preset != "custom":
                a = self.preview_area()
                if a:
                    self.values.update(x0=a[0], y0=a[1], w=a[2], h=a[3])
            return
        lo, hi = (0.3, 1.0) if f == "useful_zone" else (0.0, 1.0)
        self.values[f] = max(lo, min(hi, self.values[f] + d * self.STEP))
        if f != "useful_zone":
            self.preset = "custom"

    def update(self, now):
        g = self.gun
        if g is None or self.back_on_home(now):
            return
        if g.was_pressed(BTN_DOWN):
            self.sel = (self.sel + 1) % len(self.FIELDS)
        if g.was_pressed(BTN_UP):
            self.sel = (self.sel - 1) % len(self.FIELDS)
        if self.FIELDS[self.sel] == "preset":
            # el preset cambia con cada pulsacion
            if g.was_pressed(BTN_RIGHT):
                self.change(1)
            if g.was_pressed(BTN_LEFT):
                self.change(-1)
        elif g.packet is not None:
            # los valores cambian mientras se mantiene pulsado (cada frame)
            if g.packet.buttons & BTN_RIGHT:
                self.change(1)
            if g.packet.buttons & BTN_LEFT:
                self.change(-1)
        if g.was_pressed(BTN_A):
            r1 = self.app.control.send("area {}".format(self.profile()))
            r2 = self.app.control.send("usefulzone {:.3f}".format(self.values["useful_zone"]))
            ok = r1.get("ok") and r2.get("ok")
            self.message = (t("profiles.applied"), GREEN) if ok else \
                ((r1.get("error") or r2.get("error") or "?"), RED)
        if g.was_pressed(BTN_B):
            r = self.app.control.send("save")
            self.message = (t("profiles.saved", p=r.get("path", "")), GREEN) if r.get("ok") else \
                (r.get("error", "?"), RED)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        area = self.preview_area()
        if area:
            x0, y0, aw, ah = area
            rect = pygame.Rect(int(x0 * w), int(y0 * h), int(aw * w), int(ah * h))
            pygame.draw.rect(surf, CYAN, rect, 3)
            uy = int((y0 + self.values["useful_zone"] * ah) * h)
            pygame.draw.line(surf, YELLOW, (rect.left, uy), (rect.right, uy), 2)
        y = h // 6
        for i, f in enumerate(self.FIELDS):
            color = YELLOW if i == self.sel else WHITE
            if f == "preset":
                text = t("profiles.preset", v=self.profile())
            else:
                text = t("profiles.field", k=f, v=self.values[f])
            app.text(surf, ("> " if i == self.sel else "  ") + text, (w // 6, y), app.font, color)
            y += app.font.get_height() + 6
        if self.message:
            app.text(surf, self.message[0], (w // 6, y + 10), app.font, self.message[1])
        app.text(surf, t("profiles.hint"), (w // 2, h - app.font.get_height() * 2), app.font_small, GREY,
                 center=True)
