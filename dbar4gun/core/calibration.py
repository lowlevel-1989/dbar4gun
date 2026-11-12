"""
Calibracion: de camera point a pantalla (coordenadas normalizadas de la TV
completa, y hacia abajo).

- C1/C2/C3/C10: afin exacta de 3 puntos, screen = A*c + b, con targets
  configurables, sin offsets fijos; el clamp solo se aplica al cursor final.
- modo 1: escala y offset por eje con 2 puntos.
- C4: captura = mediana por eje del ring buffer (8 frames anteriores al flanco
  de B); si la dispersion supera el umbral, error UNSTABLE.
- C19: recalibracion rapida de 2 puntos (esquinas del lado de la barra).
- C16: modo 3, homografia con 4 puntos (esquinas).
"""

import math
import time

MODE_DISABLED = 0
MODE_2PT = 1
MODE_3PT = 2
MODE_4PT = 3

# codigos de error de captura
ERR_NO_IR = "no_ir"
ERR_UNSTABLE = "unstable"
ERR_GEOMETRY = "bad_geometry"

RING_SIZE = 8
MIN_SAMPLES = 4
# dispersion maxima (distancia a la mediana) en separaciones de barra
# (0.15 sep = ~58 px de TV con una TV de 45" y una barra de 20 cm). El jitter
# normal de la mano a 3 m ya ronda 20-50 px y la mediana lo filtra; solo se
# rechaza un pulso claramente movido (ajustar con hardware).
MAX_SPREAD_SEP = 0.15


class AffineMap(object):
    """screen = A * c + b"""

    __slots__ = ("a", "b", "c", "d", "tx", "ty")

    def __init__(self, a=1.0, b=0.0, c=0.0, d=1.0, tx=0.0, ty=0.0):
        self.a, self.b, self.c, self.d = a, b, c, d
        self.tx, self.ty = tx, ty

    def apply(self, x, y):
        return (self.a * x + self.b * y + self.tx,
                self.c * x + self.d * y + self.ty)

    def det(self):
        return self.a * self.d - self.b * self.c

    def scaled(self, k):
        """Mapa equivalente para un camera point multiplicado por 1/k."""
        return AffineMap(self.a * k, self.b * k, self.c * k, self.d * k, self.tx, self.ty)

    def to_list(self):
        return [self.a, self.b, self.c, self.d, self.tx, self.ty]

    @classmethod
    def from_list(cls, v):
        return cls(*[float(x) for x in v])

    def __repr__(self):
        return "AffineMap({})".format(", ".join("{:.4f}".format(v) for v in self.to_list()))


class HomographyMap(object):
    """C16: screen = H * (c, 1), con division perspectiva."""

    __slots__ = ("h",)

    def __init__(self, h):
        h = [float(v) for v in h]
        if abs(h[8]) > 1e-12:
            h = [v / h[8] for v in h]
        self.h = h

    def apply(self, x, y):
        h = self.h
        w = h[6] * x + h[7] * y + h[8]
        if abs(w) < 1e-12:
            w = 1e-12
        return ((h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w)

    # compatibilidad con los chequeos de AffineMap (escalas en el centro)
    @property
    def a(self):
        return self.h[0]

    @property
    def d(self):
        return self.h[4]

    @property
    def tx(self):
        return self.h[2]

    @property
    def ty(self):
        return self.h[5]

    def det(self):
        h = self.h
        return (h[0] * (h[4] * h[8] - h[5] * h[7]) - h[1] * (h[3] * h[8] - h[5] * h[6])
                + h[2] * (h[3] * h[7] - h[4] * h[6]))

    def scaled(self, k):
        """Mapa equivalente para un camera point multiplicado por 1/k."""
        h = self.h
        return HomographyMap([h[0] * k, h[1] * k, h[2], h[3] * k, h[4] * k, h[5], h[6] * k, h[7] * k, h[8]])

    def to_list(self):
        return list(self.h)

    def __repr__(self):
        return "HomographyMap({})".format(", ".join("{:.4f}".format(v) for v in self.h))


def _solve_linear(m, v):
    """Gauss con pivoteo parcial (n pequeno, python puro). None si es singular."""
    n = len(v)
    a = [list(row) + [v[i]] for i, row in enumerate(m)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        for r in range(col + 1, n):
            f = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= f * a[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (a[r][n] - sum(a[r][c] * x[c] for c in range(r + 1, n))) / a[r][r]
    return x


def solve_homography_4pt(cams, screens):
    """C16: homografia exacta de 4 camera points a 4 puntos de pantalla."""
    m, v = [], []
    for (x, y), (u, w) in zip(cams, screens):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        v.append(u)
        m.append([0, 0, 0, x, y, 1, -w * x, -w * y])
        v.append(w)
    h = _solve_linear(m, v)
    if h is None:
        return None
    return HomographyMap(h + [1.0])


def solve_affine_3pt(cams, screens):
    """
    Afin exacta que lleva 3 camera points a 3 puntos de pantalla.
    Devuelve None si los puntos son (casi) colineales.
    """
    (x0, y0), (x1, y1), (x2, y2) = cams
    det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(det) < 1e-9:
        return None

    def solve(v0, v1, v2):
        # v = p*x + q*y + r
        p = ((v1 - v0) * (y2 - y0) - (v2 - v0) * (y1 - y0)) / det
        q = ((x1 - x0) * (v2 - v0) - (x2 - x0) * (v1 - v0)) / det
        r = v0 - p * x0 - q * y0
        return p, q, r

    a, b, tx = solve(screens[0][0], screens[1][0], screens[2][0])
    c, d, ty = solve(screens[0][1], screens[1][1], screens[2][1])
    return AffineMap(a, b, c, d, tx, ty)


def solve_scale_offset_2pt(cams, screens):
    """Escala y offset por eje (modo 1). None si los puntos coinciden en un eje."""
    (x0, y0), (x1, y1) = cams
    if abs(x1 - x0) < 1e-9 or abs(y1 - y0) < 1e-9:
        return None
    kx = (screens[1][0] - screens[0][0]) / (x1 - x0)
    ky = (screens[1][1] - screens[0][1]) / (y1 - y0)
    return AffineMap(kx, 0.0, 0.0, ky,
                     screens[0][0] - kx * x0, screens[0][1] - ky * y0)


def quick_recalibrate(base, cams, screens):
    """
    C19: corrige `base` con 2 capturas en las esquinas del lado de la barra.
    Ajusta escala y offset en x y el offset en y; conserva la escala vertical
    y la rotacion de la calibracion principal.
    """
    (p0x, p0y), (p1x, p1y) = [base.apply(c[0], c[1]) for c in cams]
    if abs(p1x - p0x) < 1e-9:
        return None
    kx = (screens[1][0] - screens[0][0]) / (p1x - p0x)
    ox = screens[0][0] - kx * p0x
    oy = ((screens[0][1] - p0y) + (screens[1][1] - p1y)) * 0.5
    if isinstance(base, HomographyMap):
        # correccion afin aplicada a la salida: C * H
        h = base.h
        return HomographyMap([kx * h[0] + ox * h[6], kx * h[1] + ox * h[7], kx * h[2] + ox * h[8],
                              h[3] + oy * h[6], h[4] + oy * h[7], h[5] + oy * h[8],
                              h[6], h[7], h[8]])
    return AffineMap(base.a * kx, base.b * kx, base.c, base.d,
                     base.tx * kx + ox, base.ty + oy)


def geometry_ok(m):
    """Rechaza mapas degenerados o con un eje invertido."""
    if m is None:
        return False
    if abs(m.det()) < 1e-9:
        return False
    # apuntar mas a la derecha debe mover el cursor a la derecha (y abajo -> abajo)
    return m.a > 0 and m.d > 0


# ----------------------------------------------------------------------
# Mapa nominal (sin calibrar): TV de 45" con barra de 20 cm a 3 cm del borde,
# jugador centrado. Medidas en separaciones de barra.
NOMINAL_TV_W_SEP = 4.98
NOMINAL_TV_H_SEP = 2.80
NOMINAL_BAR_GAP_SEP = 0.15
# separacion angular nominal a 3 m (rad)
NOMINAL_SEP = 0.0667


def nominal_map(bar_on_top=True):
    """
    Aproximacion de primer orden con compensacion de distancia: el camera point
    vale FOCAL * (punto apuntado - barra) en separaciones de barra.
    """
    from dbar4gun.core.pointer import FOCAL

    kx = 1.0 / (FOCAL * NOMINAL_TV_W_SEP)
    ky = 1.0 / (FOCAL * NOMINAL_TV_H_SEP)
    off = (NOMINAL_TV_H_SEP * 0.5 + NOMINAL_BAR_GAP_SEP) / NOMINAL_TV_H_SEP
    ty = 0.5 - off if bar_on_top else 0.5 + off
    return AffineMap(kx, 0.0, 0.0, ky, 0.5, ty)


class CalibrationData(object):
    """Lo que se guarda por Wiimote (C11)."""

    VERSION = 1

    def __init__(self, mode=MODE_3PT, affine=None, sep_ref=0.0,
                 distance_compensation=True, targets=None, bar_on_top=True,
                 calibrated=False, timestamp=0.0, filter=None):
        self.mode = mode
        self.affine = affine or nominal_map(bar_on_top)
        self.sep_ref = sep_ref
        self.distance_compensation = distance_compensation
        self.targets = targets or []
        self.bar_on_top = bar_on_top
        self.calibrated = calibrated
        self.timestamp = timestamp
        # C13: parametros del One Euro de este Wiimote (None = los del servicio)
        self.filter = dict(filter) if filter else None

    def map_for(self, distance_compensation):
        """
        Afin para el modo de compensacion pedido. Si la calibracion se hizo con
        el otro modo, se convierte con sep_ref (aproximado).
        """
        if distance_compensation == self.distance_compensation:
            return self.affine
        sep = self.sep_ref or NOMINAL_SEP
        if self.distance_compensation:
            # guardada en separaciones, se usa sin compensar: c_sep = c / sep
            return self.affine.scaled(1.0 / sep)
        return self.affine.scaled(sep)

    def to_dict(self):
        return {
            "version": self.VERSION,
            "mode": self.mode,
            "affine": self.affine.to_list() if isinstance(self.affine, AffineMap) else None,
            "homography": self.affine.to_list() if isinstance(self.affine, HomographyMap) else None,
            "sep_ref": self.sep_ref,
            "distance_compensation": self.distance_compensation,
            "targets": [list(t) for t in self.targets],
            "bar_on_top": self.bar_on_top,
            "calibrated": self.calibrated,
            "timestamp": self.timestamp,
            "filter": self.filter,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            mode=int(d.get("mode", MODE_3PT)),
            affine=(HomographyMap(d["homography"]) if d.get("homography")
                    else AffineMap.from_list(d["affine"])),
            sep_ref=float(d.get("sep_ref", 0.0)),
            distance_compensation=bool(d.get("distance_compensation", True)),
            targets=[tuple(t) for t in d.get("targets", [])],
            bar_on_top=bool(d.get("bar_on_top", True)),
            calibrated=bool(d.get("calibrated", True)),
            timestamp=float(d.get("timestamp", 0.0)),
            filter=d.get("filter"),
        )


# ----------------------------------------------------------------------
def _median(values):
    v = sorted(values)
    n = len(v)
    m = n // 2
    if n % 2:
        return v[m]
    return (v[m - 1] + v[m]) * 0.5


class CaptureBuffer(object):
    """C4: ring buffer de camera points validos."""

    def __init__(self, size=RING_SIZE):
        self.size = size
        self.items = []

    def clear(self):
        self.items = []

    def push(self, cp):
        if cp is None:
            # sin IR se descarta lo acumulado: la captura debe ser continua
            self.items = []
            return
        self.items.append((cp.x, cp.y, cp.sep, cp.unit))
        if len(self.items) > self.size:
            del self.items[0]

    def spread(self):
        """Dispersion actual (distancia maxima a la mediana) en separaciones de barra."""
        if not self.items:
            return None
        mx = _median([i[0] for i in self.items])
        my = _median([i[1] for i in self.items])
        unit = max(_median([i[3] for i in self.items]), 1e-9)
        spread = 0.0
        for x, y, _, _ in self.items:
            spread = max(spread, math.sqrt((x - mx) ** 2 + (y - my) ** 2) / unit)
        return spread

    def capture(self, max_spread=MAX_SPREAD_SEP):
        """Devuelve ((x, y), sep, None) o (None, None, error)."""
        if len(self.items) < MIN_SAMPLES:
            return None, None, ERR_NO_IR
        if self.spread() > max_spread:
            return None, None, ERR_UNSTABLE
        mx = _median([i[0] for i in self.items])
        my = _median([i[1] for i in self.items])
        sep = _median([i[2] for i in self.items])
        return (mx, my), sep, None


class CalibrationSession(object):
    """
    Maquina de estados de una calibracion: un target por paso, captura en el
    flanco de subida de B.

    kind: "3pt" (TL, TR, BC), "2pt" (modo 1: centro, TL) o "quick" (C19).
    targets: puntos en pantalla (normalizados a la TV completa).
    """

    def __init__(self, kind, targets, distance_compensation=True,
                 base=None, bar_on_top=True):
        self.kind = kind
        self.targets = list(targets)
        self.distance_compensation = distance_compensation
        self.base = base
        self.bar_on_top = bar_on_top
        self.step = 0
        self.captures = []
        self.seps = []
        self.buffer = CaptureBuffer()
        self.prev_b = True   # no capturar si B ya venia pulsado
        self.result = None

    @property
    def done(self):
        return self.result is not None

    @property
    def target(self):
        return self.targets[min(self.step, len(self.targets) - 1)]

    def feed(self, cp, button_b, now=None):
        """
        Un frame. Devuelve None, ("captured", step), ("error", codigo) o
        ("done", CalibrationData).
        """
        event = None
        edge = button_b and not self.prev_b
        self.prev_b = button_b

        if edge:
            # la captura usa los frames anteriores al flanco (el de B tiembla)
            point, sep, err = self.buffer.capture()
            self.buffer.clear()
            if err:
                event = ("error", err)
            else:
                self.captures.append(point)
                self.seps.append(sep)
                self.step += 1
                event = ("captured", self.step)
                if self.step >= len(self.targets):
                    event = self._finish(now)
        else:
            self.buffer.push(cp)
        return event

    def _finish(self, now):
        if self.kind == "3pt":
            m = solve_affine_3pt(self.captures, self.targets)
            mode = MODE_3PT
        elif self.kind == "4pt":
            m = solve_homography_4pt(self.captures, self.targets)
            mode = MODE_4PT
        elif self.kind == "2pt":
            m = solve_scale_offset_2pt(self.captures, self.targets)
            mode = MODE_2PT
        else:
            m = quick_recalibrate(self.base.map_for(self.distance_compensation),
                                  self.captures, self.targets)
            mode = self.base.mode

        if not geometry_ok(m):
            # se repite la calibracion desde el principio
            self.step = 0
            self.captures = []
            self.seps = []
            return ("error", ERR_GEOMETRY)

        sep_ref = _median(self.seps)
        if self.kind == "quick" and self.base.sep_ref:
            # la recalibracion rapida conserva la escala vertical de la
            # principal, asi que tambien su distancia de referencia
            sep_ref = self.base.sep_ref

        self.result = CalibrationData(
            mode=mode, affine=m, sep_ref=sep_ref,
            distance_compensation=self.distance_compensation,
            targets=self.targets if self.kind != "quick" else self.base.targets,
            bar_on_top=self.bar_on_top, calibrated=True,
            # fecha real (el `now` del pipeline es monotonic, desde el arranque)
            timestamp=time.time())
        return ("done", self.result)
