"""
Mapas de camera point a pantalla y como se calculan.

- AffineMap: screen = A * c + b (modos 1 y 2).
- HomographyMap: homografia con division perspectiva (modo 3, 4 puntos).
- solve_*: calculan el mapa a partir de los disparos a los targets.
- quick_recalibrate: corrige un mapa con 2 disparos.
- geometry_ok: rechaza mapas degenerados o con un eje invertido.
"""


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
    """screen = H * (c, 1), con division perspectiva."""

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
    """homografia exacta de 4 camera points a 4 puntos de pantalla."""
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
    corrige `base` con 2 capturas en las esquinas del lado de la barra.
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
