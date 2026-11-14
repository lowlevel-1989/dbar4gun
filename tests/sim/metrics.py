"""
Medidas de precision del simulador: error en px de la TV sobre una
cuadricula de puntos del area 4:3.
"""

import math

TV_W_PX = 1920
TV_H_PX = 1080

# area 4:3 dentro de 16:9
AREA_43_X0 = 0.125
AREA_43_W = 0.75

# juego 320x240 estirado sobre el area 4:3 de una TV 1080p: 1 px de juego = 4.5 px de TV
GAME_PX = TV_H_PX / 240.0


def grid_43(n=7, margin=0.05):
    """Grid n x n dentro del area 4:3, del `margin` al 1 - `margin` del area."""
    pts = []
    for j in range(n):
        for i in range(n):
            ax = margin + (1 - 2 * margin) * i / float(n - 1)
            ay = margin + (1 - 2 * margin) * j / float(n - 1)
            pts.append((AREA_43_X0 + AREA_43_W * ax, ay))
    return pts


def error_tv_px(cursor, target):
    dx = (cursor[0] - target[0]) * TV_W_PX
    dy = (cursor[1] - target[1]) * TV_H_PX
    return math.sqrt(dx * dx + dy * dy)


class Summary(object):
    def __init__(self, errors_tv):
        self.errors_tv = list(errors_tv)
        self.mean_tv = sum(self.errors_tv) / len(self.errors_tv)
        self.max_tv = max(self.errors_tv)
        self.mean_game = self.mean_tv / GAME_PX
        self.max_game = self.max_tv / GAME_PX

    def __repr__(self):
        return ("mean {:.1f} px TV ({:.1f} px juego), max {:.1f} px TV ({:.1f} px juego)"
                .format(self.mean_tv, self.mean_game, self.max_tv, self.max_game))


def measure_grid(scene, cursor_fn, roll_deg=0.0, frames=5, points=None):
    """
    Apunta a cada punto de la grid durante `frames` reports y mide el cursor final.
    `cursor_fn(report) -> (x, y)` normalizado a la pantalla completa.
    """
    errors = []
    for sx, sy in (points or grid_43()):
        cursor = None
        for _ in range(frames):
            cursor = cursor_fn(scene.report(sx, sy, roll_deg))
        errors.append(error_tv_px(cursor, (sx, sy)))
    return Summary(errors)
