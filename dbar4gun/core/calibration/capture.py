"""
Captura de un disparo: guarda los ultimos camera points (CaptureBuffer) y
al pulsar B da la mediana. Si no hay IR o el pulso se movio demasiado, da un
error (ERR_NO_IR, ERR_UNSTABLE).
"""

import math


# codigos de error de captura
ERR_NO_IR = "no_ir"
ERR_UNSTABLE = "unstable"

RING_SIZE = 8
MIN_SAMPLES = 4
# dispersion maxima (distancia a la mediana) en separaciones de barra
# (0.15 sep = ~58 px de TV con una TV de 45" y una barra de 20 cm). El jitter
# normal de la mano a 3 m ya ronda 20-50 px y la mediana lo filtra; solo se
# rechaza un pulso claramente movido (ajustar con hardware).
MAX_SPREAD_SEP = 0.15


def median(values):
    v = sorted(values)
    n = len(v)
    m = n // 2
    if n % 2:
        return v[m]
    return (v[m - 1] + v[m]) * 0.5


class CaptureBuffer(object):
    """ring buffer de camera points validos."""

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
        mx = median([i[0] for i in self.items])
        my = median([i[1] for i in self.items])
        unit = max(median([i[3] for i in self.items]), 1e-9)
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
        mx = median([i[0] for i in self.items])
        my = median([i[1] for i in self.items])
        sep = median([i[2] for i in self.items])
        self.unit = max(median([i[3] for i in self.items]), 1e-9)
        return (mx, my), sep, None
