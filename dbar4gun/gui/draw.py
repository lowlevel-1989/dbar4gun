"""
Colores y dibujo compartido por todas las pantallas.

App hereda de Drawing, asi que desde una pantalla se usan como
self.app.text(...), self.app.draw_camera(...), etc.
"""

import math

import pygame

from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.calibration import distance_m
from dbar4gun.protocol import DOT_RECONSTRUCTED, DOT_VALID, RAW_ABSENT


BLACK = (0, 0, 0)
WHITE = (240, 240, 240)
GREY = (110, 110, 110)
DARK = (40, 40, 48)
GREEN = (80, 220, 120)
YELLOW = (240, 210, 70)
RED = (235, 80, 70)
CYAN = (90, 200, 220)
MAGENTA = (210, 110, 220)

GUN_COLORS = [(228, 116, 89), (96, 205, 131), (96, 198, 205), (197, 96, 205)]


class Drawing(object):
    def text(self, surf, text, pos, font, color, center=False):
        img = font.render(text, True, color)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        surf.blit(img, r)

    def wrap(self, text, font, max_w):
        """Parte un texto en lineas que caben en max_w px (las palabras largas, por /)."""
        out = []
        line = ""
        for word in text.split(" "):
            cand = word if not line else line + " " + word
            if font.size(cand)[0] <= max_w:
                line = cand
                continue
            if line:
                out.append(line)
            line = word
            # una palabra que no cabe (una ruta): se corta por caracteres
            while font.size(line)[0] > max_w and len(line) > 1:
                cut = len(line)
                while cut > 1 and font.size(line[:cut])[0] > max_w:
                    cut -= 1
                out.append(line[:cut])
                line = line[cut:]
        if line:
            out.append(line)
        return out or [""]

    def inset_rect(self, avoid=None):
        """
        Recuadro de la camara, abajo a la derecha. `avoid`: punto (px) que no
        debe tapar (un target de la calibracion en esa esquina): entonces va
        abajo a la izquierda.
        """
        w, h = self.size
        ih = h // 4
        iw = ih * 4 // 3
        rect = pygame.Rect(w - iw - 16, h - ih - 16, iw, ih)
        if avoid is not None:
            r = max(14, h // 40) * 2          # la mira del target, con su cruz
            if rect.inflate(2 * r, 2 * r).collidepoint(avoid):
                rect.x = 16
        return rect

    def draw_target(self, surf, pos, color):
        x, y = pos
        r = max(14, self.size[1] // 40)
        pygame.draw.circle(surf, color, pos, r, 3)
        pygame.draw.line(surf, color, (x - 2 * r, y), (x + 2 * r, y), 2)
        pygame.draw.line(surf, color, (x, y - 2 * r), (x, y + 2 * r), 2)

    def draw_screen_overlay(self, surf, p):
        """area del perfil y useful zone."""
        if p is None:
            return
        w, h = surf.get_size()
        x0, y0, aw, ah = p.area
        rect = pygame.Rect(int(x0 * w), int(y0 * h), int(aw * w), int(ah * h))
        pygame.draw.rect(surf, DARK, rect, 2)
        yy = int((y0 + p.useful_zone * ah) * h)
        for x in range(rect.left, rect.right, 24):
            pygame.draw.line(surf, GREY, (x, yy), (x + 12, yy), 1)

    def draw_camera(self, surf, rect, p, big=False):
        """vista de la camara 4:3 (dots en bruto, TL/TR, reconstruidos, extra)."""
        pygame.draw.rect(surf, DARK, rect)
        pygame.draw.rect(surf, GREY, rect, 1)
        if p is None:
            return
        rad = max(4, rect.height // 40)

        def to_px(u, v):
            return (int(rect.left + u / 1023.0 * rect.width), int(rect.top + v / 767.0 * rect.height))

        tracked = []
        for k, d in enumerate(p.dots):
            if d[2] & DOT_VALID:
                u = (1.0 - d[0]) * 1023.0
                v = 767.0 - d[1] * 767.0
                # el TL del espacio normalizado es el LED derecho (x invertida):
                # se etiqueta por el lado fisico, como lo ve el jugador
                tracked.append((to_px(u, v), bool(d[2] & DOT_RECONSTRUCTED), "R" if k == 0 else "L"))

        raw_seen = []
        for r in p.raw:
            if r[1] == RAW_ABSENT:
                continue
            pos = to_px(r[0], 767 - r[1])
            raw_seen.append((pos, r[2]))

        tracked_pos = [t_[0] for t_ in tracked if not t_[1]]
        for pos, size in raw_seen:
            extra = all(abs(pos[0] - q[0]) > 2 or abs(pos[1] - q[1]) > 2 for q in tracked_pos)
            pygame.draw.circle(surf, RED if extra else WHITE, pos, rad if not extra else rad + 2,
                               0 if not extra else 2)
            if big and size != 0xFF:
                # tamano del dot (IR extendido): un LED debil se ve mas pequeno
                self.text(surf, str(size), (pos[0], pos[1] + rad + 14), self.font_small, GREY,
                          center=True)

        if len(tracked) == 2:
            a, b = tracked[0][0], tracked[1][0]
            dashed = tracked[0][1] or tracked[1][1]
            self.line(surf, CYAN, a, b, dashed)
        font = self.font if big else self.font_small
        for pos, rec, label in tracked:
            if rec:
                pygame.draw.circle(surf, YELLOW, pos, rad + 3, 2)
            self.text(surf, label, (pos[0], pos[1] - rad - font.get_height() // 2 - 4), font, CYAN,
                      center=True)

    def line(self, surf, color, a, b, dashed=False):
        if not dashed:
            pygame.draw.line(surf, color, a, b, 2)
            return
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) // 10))
        for i in range(0, n, 2):
            p0 = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            p1 = (a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n)
            pygame.draw.line(surf, color, p0, p1, 2)

    def gun_lines(self, p, vg):
        if p is None:
            return [(t("player", vg=vg), GREY)]
        lines = [(t("player", vg=vg), GUN_COLORS[(vg - 1) % 4])]
        lines.append((t("battery", v=p.battery) if p.battery is not None else t("battery_na"),
                      RED if p.battery is not None and p.battery < 20 else WHITE))
        lines.append((t("hz", v=p.hz), WHITE if p.hz >= 80 or p.hz == 0 else YELLOW))
        n = p.n_dots
        lines.append((t("dots", n=n), GREEN if n == 2 else YELLOW if n == 1 else RED))
        if n > 2:
            lines.append((t("extra_ir", n=n - 2), RED))
        d = distance_m(p, self.hardware)
        lines.append((t("distance", d=d) if d else t("distance_na"), WHITE))
        if not math.isnan(p.roll):
            lines.append((t("roll", v=p.roll), GREY))
        return lines

    def draw_gun_summary(self, surf, guns):
        w, h = surf.get_size()
        x = w // 20
        y = h - h // 5
        for g in guns:
            p = g.packet
            col = GUN_COLORS[(g.virtualgun - 1) % 4]
            parts = [t("player", vg=g.virtualgun),
                     t("battery", v=p.battery) if p.battery is not None else t("battery_na"),
                     t("dots", n=p.n_dots)]
            self.text(surf, "   ".join(parts), (x, y), self.font, col)
            y += self.font.get_height() + 4
            # cursor de cada Wiimote
            pygame.draw.circle(surf, col, (int(p.screen[0] * w), int(p.screen[1] * h)), 10, 3)
