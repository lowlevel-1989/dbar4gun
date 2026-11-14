"""
Escena simulada: TV, barra y jugador. Genera los reports que veria el
Wiimote apuntando a un punto de la TV.
"""

import math
import random

from tests.sim.camera import CameraPose, SENSOR_H
from tests.sim.payload import ir_basic_payload, report_0x37, acc_bytes


class TV(object):
    """TV 16:9 centrada en el origen, en el plano z = 0."""

    def __init__(self, diagonal_in=45.0, aspect=(16, 9)):
        aw, ah = aspect
        diag = math.sqrt(aw * aw + ah * ah)
        self.diagonal_in = diagonal_in
        self.width = diagonal_in * 0.0254 * aw / diag
        self.height = diagonal_in * 0.0254 * ah / diag

    def point(self, sx, sy):
        """(sx, sy) normalizados, y hacia abajo -> punto 3D."""
        return ((sx - 0.5) * self.width, (0.5 - sy) * self.height, 0.0)


class Scene(object):
    """
    TV + barra de 2 dots (separacion `bar_sep` m, `bar_gap` m por encima o
    por debajo del borde) + jugador en (x, y, D).
    """

    def __init__(self, tv=None, bar_sep=0.20, bar_gap=0.03, bar_on_top=True,
                 player=(0.0, 0.0, 3.0), noise_px=0.0, seed=1234,
                 dot_order="left_first", bar_offset=(0.0, 0.0), bar_tilt_deg=0.0,
                 extra_ir=(), split_px=0.0):
        self.tv = tv or TV()
        self.bar_sep = bar_sep
        self.bar_on_top = bar_on_top
        y = self.tv.height / 2.0 + bar_gap
        if not bar_on_top:
            y = -y
        # bar_offset: barra desplazada (m) respecto al centro de la TV
        bx, by = bar_offset
        # bar_tilt_deg: barra inclinada (positivo = lado derecho mas alto)
        ca = math.cos(math.radians(bar_tilt_deg)) * bar_sep / 2.0
        sa = math.sin(math.radians(bar_tilt_deg)) * bar_sep / 2.0
        self.leds = [(bx - ca, y + by - sa, 0.0), (bx + ca, y + by + sa, 0.0)]
        # fuentes IR ajenas a la barra (puntos 3D, p. ej. una lampara) y
        # reflejo que parte cada LED en 2 dots separados split_px
        self.extra_ir = list(extra_ir)
        self.split_px = split_px
        self.player = player
        self.noise_px = noise_px
        self.rng = random.Random(seed)
        self.dot_order = dot_order

    def pose(self, sx, sy, roll_deg=0.0):
        return CameraPose(self.player, self.tv.point(sx, sy), roll_deg)

    def raw_dots(self, sx, sy, roll_deg=0.0, drop=()):
        """
        Dots en coordenadas raw del Wiimote (raw_x = u, raw_y = 767 - v) o None.
        `drop`: indices de LED (0 izquierda, 1 derecha) que se dan por perdidos.
        """
        pose = self.pose(sx, sy, roll_deg)
        dots = []
        for i, led in enumerate(self.leds):
            p = pose.project(led)
            if p is None or i in drop:
                dots.append(None)
                continue
            u, v = p
            if self.noise_px:
                u += self.rng.gauss(0.0, self.noise_px)
                v += self.rng.gauss(0.0, self.noise_px)
            raw_x = max(0, min(1023, int(round(u))))
            raw_y = max(0, min(SENSOR_H - 1, int(round(SENSOR_H - 1 - v))))
            dots.append((raw_x, raw_y))

        if self.split_px:
            split = []
            for d in dots:
                split.append(d)
                if d is not None:
                    split.append((min(1023, d[0] + int(self.split_px)), max(0, d[1] - int(self.split_px // 2))))
            dots = split
        for point in self.extra_ir:
            p = pose.project(point)
            if p is not None:
                dots.append((int(round(p[0])), int(round(SENSOR_H - 1 - p[1]))))
        # la camara solo reporta 4 dots
        dots = dots[:4]

        if self.dot_order == "right_first":
            dots.reverse()
        elif self.dot_order == "random":
            self.rng.shuffle(dots)
        return dots

    def report(self, sx, sy, roll_deg=0.0, buttons=0, drop=()):
        pose = self.pose(sx, sy, roll_deg)
        dots = self.raw_dots(sx, sy, roll_deg, drop)
        return report_0x37(buttons, acc_bytes(pose.gravity()), ir_basic_payload(dots))


def trajectory(a, b, frames=25):
    """Puntos (sx, sy) interpolados linealmente de a a b, ambos incluidos."""
    out = []
    for i in range(frames):
        t = i / float(frames - 1)
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out
