"""
Camera point: de TL/TR (espacio cuadrado) a un punto 2D independiente del
roll y, opcionalmente, de la distancia.

- midpoint en espacio cuadrado, respecto al centro del sensor, y tilt
  correction (girar por -angulo de TL->TR). Tambien con dots reconstruidos.
- dividir el offset entre la separacion de los dots. Se usa la separacion
  angular (radianes, con la focal de la camara) y no la distancia en la imagen:
  la separacion en la imagen crece al apuntar lejos de la barra (1/cos^2) y eso
  deformaba las esquinas. La separacion angular solo depende de la distancia.
"""

import math

from dbar4gun.core.tracker import SQUARE_Y

CENTER = (0.5, 0.5 * SQUARE_Y)

# focal en unidades normalizadas (1 = 1023 px): 512 / tan(33 / 2 grados) / 1023
# (el FOV real lo mide el calibrator y se guarda con `dbar4gun hw`)
FOV_H_DEG = 33.0
FOCAL = (512.0 / math.tan(math.radians(FOV_H_DEG / 2.0))) / 1023.0

# distancia entre los LEDs de la barra (m), solo para estimar la distancia
BAR_WIDTH_M = 0.20


def angular_separation(tl, tr, focal=FOCAL):
    """Angulo (rad) entre las direcciones de los 2 dots vistos desde la camara."""
    x1, y1 = tl[0] - CENTER[0], tl[1] - CENTER[1]
    x2, y2 = tr[0] - CENTER[0], tr[1] - CENTER[1]
    f = focal
    dot = x1 * x2 + y1 * y2 + f * f
    cx = y1 * f - f * y2
    cy = f * x2 - x1 * f
    cz = x1 * y2 - y1 * x2
    return math.atan2(math.sqrt(cx * cx + cy * cy + cz * cz), dot)


def distance_from_separation(theta, bar_width=BAR_WIDTH_M):
    """Distancia aproximada (m) a la barra."""
    if theta <= 1e-9:
        return 0.0
    return bar_width / (2.0 * math.tan(theta * 0.5))


class CameraPoint(object):
    """
    x, y:  camera point.
    sep:   separacion angular de los dots (rad).
    angle: angulo de TL->TR (rad).
    unit:  longitud de una separacion de barra en unidades de (x, y); sirve
           para medir la dispersion igual con y sin compensacion.
    """

    __slots__ = ("x", "y", "sep", "angle", "unit")

    def __init__(self, x, y, sep, angle, unit):
        self.x = x
        self.y = y
        self.sep = sep
        self.angle = angle
        self.unit = unit


def camera_point(state, tilt_correction=True, distance_compensation=True):
    """CameraPoint desde un TrackState valido, o None."""
    if not state.valid:
        return None

    tl, tr = state.tl, state.tr
    mx = (tl[0] + tr[0]) * 0.5 - CENTER[0]
    my = (tl[1] + tr[1]) * 0.5 - CENTER[1]

    dx = tr[0] - tl[0]
    dy = tr[1] - tl[1]
    sep_img = math.sqrt(dx * dx + dy * dy)
    angle = math.atan2(dy, dx)
    theta = angular_separation(tl, tr)
    if sep_img <= 1e-6 or theta <= 1e-9:
        return None

    if tilt_correction:
        c, s = math.cos(-angle), math.sin(-angle)
        mx, my = c * mx - s * my, s * mx + c * my

    unit = sep_img
    if distance_compensation:
        mx /= theta
        my /= theta
        unit = sep_img / theta

    return CameraPoint(mx, my, theta, angle, unit)
