"""
Tracker de los 2 dots de la barra (TL/TR).

Trabaja en espacio cuadrado: (x, y * 767/1023), para que las distancias y los
angulos no dependan del aspecto del sensor.

- C5: TL/TR se mantienen por continuidad (vecino mas cercano). Si se pierde un
  dot se reconstruye con el ultimo vector TL->TR, valido PAIR_TIMEOUT segundos
  desde el ultimo par completo.
- C17: roll desde el acelerometro (centro 0x80). Se usa cuando no hay un par
  reciente: para ordenar TL/TR (tambien mas alla de +-90 grados) y para
  orientar la reconstruccion.
- C18: sin dots, el estado queda `lost` (el pipeline lleva el cursor al borde).
- C8: los dots mas cercanos que MERGE_DIST se fusionan en su centroide
  (reflejos que parten un LED) y el par se elige con un coste de continuidad
  mas la separacion y el angulo esperados (fuentes IR ajenas a la barra).
"""

import math

SQUARE_Y = 767.0 / 1023.0

PAIR_TIMEOUT = 0.5

ACC_ZERO = 0x80
# signo del eje X del acelerometro frente al roll (lo comprueba el calibrator
# y se guarda con `dbar4gun hw`)
ACC_X_SIGN = -1.0
# |g| minimo en el plano X/Z (cuentas) para fiarse del roll
ACC_MIN_XZ = 8

# C8: distancia de fusion (espacio cuadrado normalizado, ~15 px del sensor)
MERGE_DIST = 0.015
# pesos del coste del par
W_SEP = 1.0
W_ANGLE = 1.0
W_CONTINUITY = 0.5
# por encima de este coste el mejor par no es la barra (p. ej. un LED + una
# lampara): se usa un solo dot y se reconstruye el otro
MAX_PAIR_COST = 0.3


def acc_roll(acc, acc_x_sign=None):
    """
    Roll en radianes desde el acelerometro (bytes 0..255), positivo = Wiimote
    girado en sentido horario visto desde el jugador. None si el Wiimote apunta
    casi en vertical (X y Z sin informacion).
    """
    if acc is None:
        return None
    ax = (acc[0] - ACC_ZERO) * (ACC_X_SIGN if acc_x_sign is None else acc_x_sign)
    az = acc[2] - ACC_ZERO
    if ax * ax + az * az < ACC_MIN_XZ * ACC_MIN_XZ:
        return None
    return math.atan2(ax, az)


def dot_angle_from_roll(roll):
    """
    Angulo esperado del vector TL->TR (espacio cuadrado normalizado) para un
    roll dado. Con el Wiimote recto es 0; al girarlo en sentido horario la
    barra se ve girada en sentido contrario.
    """
    return -roll


def merge_close(pts, dist=MERGE_DIST):
    """C8: fusiona en su centroide los dots a menos de `dist` entre si."""
    groups = []
    d2 = dist * dist
    for p in pts:
        for g in groups:
            if _dist2(p, g[0]) <= d2:
                g[1].append(p)
                n = len(g[1])
                g[0] = (sum(q[0] for q in g[1]) / n, sum(q[1] for q in g[1]) / n)
                break
        else:
            groups.append([p, [p]])
    return [g[0] for g in groups]


def _angle_diff_mod_pi(a, b):
    """Diferencia de angulos de rectas (sin sentido), en [0, pi/2]."""
    d = (a - b) % math.pi
    return min(d, math.pi - d)


def _dist2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


class TrackState(object):
    __slots__ = ("tl", "tr", "tl_rec", "tr_rec", "n_dots", "roll", "lost", "t")

    def __init__(self, tl=None, tr=None, tl_rec=False, tr_rec=False,
                 n_dots=0, roll=None, lost=True, t=0.0):
        self.tl = tl
        self.tr = tr
        self.tl_rec = tl_rec
        self.tr_rec = tr_rec
        self.n_dots = n_dots
        self.roll = roll
        self.lost = lost
        self.t = t

    @property
    def valid(self):
        return self.tl is not None and self.tr is not None

    @property
    def full(self):
        return self.valid and not (self.tl_rec or self.tr_rec)

    @property
    def separation(self):
        if not self.valid:
            return 0.0
        return math.sqrt(_dist2(self.tl, self.tr))

    @property
    def angle(self):
        if not self.valid:
            return 0.0
        return math.atan2(self.tr[1] - self.tl[1], self.tr[0] - self.tl[0])


class Tracker(object):
    def __init__(self, pair_timeout=PAIR_TIMEOUT, acc_x_sign=ACC_X_SIGN):
        self.pair_timeout = pair_timeout
        # medido con el calibrator (hardware.json)
        self.acc_x_sign = acc_x_sign
        self.reset()

    def reset(self):
        # ultima posicion (completa o reconstruida)
        self.tl = None
        self.tr = None
        self.pos_t = -1e9
        # ultimo par completo
        self.vec = None
        self.vec_t = -1e9
        self.sep = None
        self.state = TrackState()

    # ------------------------------------------------------------------
    def update(self, dots, acc, t):
        """
        dots: lista de (x, y, found) normalizados (parser).
        acc:  (ax, ay, az) bytes del acelerometro o None.
        t:    tiempo en segundos (monotonic).
        """
        pts = merge_close([(d[0], d[1] * SQUARE_Y) for d in dots if d[2]])
        roll = acc_roll(acc, self.acc_x_sign)
        continuity = self.tl is not None and (t - self.pos_t) <= self.pair_timeout

        pair = self._pick_pair(pts, continuity, roll, t) if len(pts) >= 2 else None
        if len(pts) >= 2 and pair is None:
            # ningun par encaja con la barra: un LED + fuentes ajenas
            pts = [self._best_single(pts)]

        if pair is not None:
            tl, tr = pair
            self.vec = (tr[0] - tl[0], tr[1] - tl[1])
            self.vec_t = t
            self.sep = math.sqrt(self.vec[0] ** 2 + self.vec[1] ** 2)
            state = TrackState(tl, tr, False, False, len(pts), roll, False, t)

        elif len(pts) == 1:
            state = self._single(pts[0], continuity, roll, t)

        else:
            state = TrackState(None, None, False, False, 0, roll, True, t)

        if state.valid:
            self.tl, self.tr = state.tl, state.tr
            self.pos_t = t

        self.state = state
        return state

    # ------------------------------------------------------------------
    def _order(self, a, b, continuity, roll):
        """Devuelve (tl, tr)."""
        if continuity:
            keep = _dist2(a, self.tl) + _dist2(b, self.tr)
            swap = _dist2(b, self.tl) + _dist2(a, self.tr)
            return (a, b) if keep <= swap else (b, a)

        phi = 0.0 if roll is None else dot_angle_from_roll(roll)
        c, s = math.cos(phi), math.sin(phi)
        pa = a[0] * c + a[1] * s
        pb = b[0] * c + b[1] * s
        return (a, b) if pa <= pb else (b, a)

    def _expected_angle(self, roll, t):
        if self.vec is not None and (t - self.vec_t) <= self.pair_timeout:
            return math.atan2(self.vec[1], self.vec[0])
        if roll is not None:
            return dot_angle_from_roll(roll)
        return None

    def pair_cost(self, a, b, continuity, expected_angle):
        """
        C8: (coste total, coste de forma) del par. La forma (separacion y
        angulo esperados) decide si el par puede ser la barra; la continuidad
        solo ayuda a elegir entre pares plausibles.
        """
        d = math.sqrt(_dist2(a, b))
        if d <= 1e-6:
            return float("inf"), float("inf")
        shape = 0.0
        ref = self.sep or d
        if self.sep:
            shape += W_SEP * abs(d - self.sep) / self.sep
        if expected_angle is not None:
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            shape += W_ANGLE * _angle_diff_mod_pi(ang, expected_angle) / (math.pi / 2)
        total = shape
        if continuity:
            keep = math.sqrt(_dist2(a, self.tl)) + math.sqrt(_dist2(b, self.tr))
            swap = math.sqrt(_dist2(b, self.tl)) + math.sqrt(_dist2(a, self.tr))
            total += W_CONTINUITY * min(keep, swap) / ref
        return total, shape

    def _pick_pair(self, pts, continuity, roll, t=0.0):
        """(tl, tr) del mejor par, o None si ninguno parece la barra."""
        expected = self._expected_angle(roll, t)
        # solo se rechazan pares con una referencia reciente: si no, la
        # separacion guardada puede ser de otra distancia y el tracker se
        # quedaria atascado
        strict = self.sep is not None and (t - self.vec_t) <= self.pair_timeout
        best = None
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                total, shape = self.pair_cost(pts[i], pts[j], continuity, expected)
                if strict and shape > MAX_PAIR_COST:
                    continue
                if best is None or total < best[0]:
                    best = (total, pts[i], pts[j])
        # ningun par plausible
        if best is None:
            return None
        return self._order(best[1], best[2], continuity, roll)

    def _best_single(self, pts):
        """El dot mas cercano a la ultima posicion de TL o TR."""
        if self.tl is None:
            return pts[0]
        return min(pts, key=lambda p: min(_dist2(p, self.tl), _dist2(p, self.tr)))

    def _single(self, p, continuity, roll, t):
        vec = None
        if self.vec is not None and (t - self.vec_t) <= self.pair_timeout:
            vec = self.vec
        elif self.sep and roll is not None:
            phi = dot_angle_from_roll(roll)
            vec = (self.sep * math.cos(phi), self.sep * math.sin(phi))

        if vec is None or self.tl is None:
            return TrackState(None, None, False, False, 1, roll, False, t)

        if not continuity and roll is None:
            return TrackState(None, None, False, False, 1, roll, False, t)

        # el dot visible es el TL o el TR anterior mas cercano
        if _dist2(p, self.tl) <= _dist2(p, self.tr):
            tl = p
            tr = (p[0] + vec[0], p[1] + vec[1])
            return TrackState(tl, tr, False, True, 1, roll, False, t)

        tr = p
        tl = (p[0] - vec[0], p[1] - vec[1])
        return TrackState(tl, tr, True, False, 1, roll, False, t)
