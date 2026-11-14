"""
Colocar la barra y calibrar: instalacion, alcance y wizard.

- distancia a la barra, inclinacion y posicion en la TV.
- reach test y distancia recomendada.
- targets del wizard, comprobacion de geometria y verificacion.
"""

import math

from dbar4gun.core.calibration.capture import MAX_SPREAD_SEP
from dbar4gun.core.hardware import HardwareConfig
from dbar4gun.core.pointer import FOCAL


# ----------------------------------------------------------------------
# instalacion
def distance_m(packet, hw=None):
    """Distancia a la barra; con `hw` usa el FOV y el ancho medidos."""
    if packet is None or packet.separation <= 0:
        return None
    return (hw or HardwareConfig()).distance(packet.separation, FOCAL)


def reference_distance_m(packet, hw=None):
    if packet is None or packet.sep_ref <= 0:
        return None
    return (hw or HardwareConfig()).distance(packet.sep_ref, FOCAL)


def bar_tilt_deg(packet):
    """
    Inclinacion de la barra respecto al suelo (grados, positivo = lado derecho
    mas alto): el angulo de los dots corregido con el roll del acelerometro.
    Con la barra nivelada, angulo = -roll; el TL del espacio normalizado es el
    LED derecho (x invertida), asi que una barra inclinada da angulo = -tilt.
    """
    if packet is None or math.isnan(packet.roll) or packet.n_dots < 2:
        return None
    t = -(packet.angle + packet.roll)
    return (t + 180.0) % 360.0 - 180.0


def bar_position(status):
    """
    Posicion de la barra en la TV segun la calibracion (status del socket de control): el
    camera point (0, 0) es apuntar justo a la barra. (x, y) normalizados.
    """
    pos = (status or {}).get("bar_position")
    return tuple(pos) if pos else None


# ----------------------------------------------------------------------
# alcance
class ReachTest(object):
    """
    Rastro de la reach test: (x, y, dots) en pantalla.

    La reach test mide hasta donde de la pantalla se puede bajar viendo la
    barra (con la barra encima de la TV, lo dificil es la parte de abajo). Su
    unico uso en la calibracion: el wizard no pone el target de abajo mas abajo
    de lo alcanzado (adaptive_targets).

    Con la barra debajo de la TV, bajar siempre es facil y sale cerca del 100%.
    No afecta a la calibracion: con 100% el target de abajo queda en la useful
    zone, igual que sin hacer la reach test. Lo que no mide es si se alcanza la
    parte de arriba; eso se comprueba con la shooting gallery.
    """

    def __init__(self):
        self.trail = []

    def add(self, packet):
        x, y = packet.screen
        self.trail.append((x, y, min(packet.n_dots, 2)))

    def reach(self):
        """
        Fraccion del alto de la pantalla que se alcanza con los 2 dots, medida
        desde arriba (la barra). None si no hay datos.
        """
        ys = [y for x, y, n in self.trail if n >= 2 and -0.2 <= y <= 1.2]
        if not ys:
            return None
        return max(0.0, min(1.0, max(ys)))


def recommend_distance(distance, reach, useful_zone):
    """
    factor = useful_zone / reach; D_nueva = D * factor. Devuelve
    (factor, distancia nueva o None).
    """
    if not reach or reach <= 0:
        return None, None
    factor = useful_zone / reach
    return factor, (distance * factor if distance else None)


# ----------------------------------------------------------------------
# wizard
TOP_TARGET = 0.10
REACH_MARGIN = 0.05


def adaptive_targets(area, useful_zone, reach=None, points=3):
    """
    Targets de 3 puntos en pantalla completa: los de arriba al 10% del alto y
    el de abajo en min(useful zone, alcance - margen).
    area: (x0, y0, w, h).
    """
    x0, y0, w, h = area
    far = useful_zone
    if reach is not None:
        far = min(far, reach - REACH_MARGIN)
    far = max(far, 0.5)
    left = x0 + 0.1 * w
    right = x0 + 0.9 * w
    center = x0 + 0.5 * w
    near_y = y0 + TOP_TARGET * h
    far_y = y0 + far * h
    if points == 4:
        # esquinas TL, TR, BR, BL
        return [(left, near_y), (right, near_y), (right, far_y), (left, far_y)]
    return [(left, near_y), (right, near_y), (center, far_y)]


def geometry_check(ratio, screen_aspect, tol=0.10):
    """
    e/a (escala vertical / horizontal del mapa, `scale_ratio` del status)
    debe parecerse al aspecto de la TV: 1 unidad de camera point es igual en
    x e y, y la pantalla mide aspecto veces mas en x. Devuelve (ok, ratio).
    """
    if not ratio or ratio <= 0:
        return False, None
    return abs(ratio / screen_aspect - 1.0) <= tol, ratio


def median(values):
    v = sorted(values)
    n = len(v)
    if not n:
        return None
    m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) * 0.5


def verify_error_px(samples, target, size):
    """Error (px de TV) de la mediana de las muestras respecto al target."""
    if not samples:
        return None
    mx = median([s[0] for s in samples])
    my = median([s[1] for s in samples])
    dx = (mx - target[0]) * size[0]
    dy = (my - target[1]) * size[1]
    return math.sqrt(dx * dx + dy * dy)


VERIFY_MAX_PX = 20.0


def stability(spread):
    """'good' / 'ok' / 'bad' / None segun la dispersion (separaciones de barra)."""
    if spread is None or spread < 0:
        return None
    if spread <= MAX_SPREAD_SEP * 0.5:
        return "good"
    if spread <= MAX_SPREAD_SEP:
        return "ok"
    return "bad"

