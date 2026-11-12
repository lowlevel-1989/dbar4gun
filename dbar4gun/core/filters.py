"""
C13: One Euro filter (Casiez et al., 2012) para el cursor.

Paso bajo con frecuencia de corte adaptativa: quieto filtra mucho (fc_min,
quita el jitter) y al moverse rapido sube la frecuencia de corte (beta,
quita el retraso). En 2D se usa la velocidad 2D para que los dos ejes tengan
el mismo retraso.

Unidades: posicion normalizada a la pantalla (0..1) y segundos.
"""

import math

# ajustados con el simulador (TV 45", 3 m, ruido 0.5 px): mismo retraso que la
# media movil de 3 frames de la v0.18 y un tercio del jitter
DEFAULT_FC_MIN = 1.0      # Hz
DEFAULT_BETA = 10.0       # Hz por (unidad de pantalla / s)
DEFAULT_D_CUTOFF = 1.0    # Hz
DEFAULT_LEVEL = 3


def params_for_level(level):
    """--smoothing-level: 0 = sin filter, 3 = por defecto, mas = mas suave."""
    if level <= 0:
        return None
    return {"fc_min": DEFAULT_FC_MIN * DEFAULT_LEVEL / float(level),
            "beta": DEFAULT_BETA, "d_cutoff": DEFAULT_D_CUTOFF}

# dt si los timestamps no avanzan (reports a ~100 Hz)
DEFAULT_DT = 0.01


def _alpha(cutoff, dt):
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuro2D(object):
    def __init__(self, fc_min=DEFAULT_FC_MIN, beta=DEFAULT_BETA, d_cutoff=DEFAULT_D_CUTOFF):
        self.fc_min = fc_min
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self):
        self.x = None
        self.dx = (0.0, 0.0)
        self.t = None

    def params(self):
        return {"fc_min": self.fc_min, "beta": self.beta, "d_cutoff": self.d_cutoff}

    def set_params(self, fc_min=None, beta=None, d_cutoff=None):
        if fc_min is not None:
            self.fc_min = max(0.01, float(fc_min))
        if beta is not None:
            self.beta = max(0.0, float(beta))
        if d_cutoff is not None:
            self.d_cutoff = max(0.01, float(d_cutoff))

    def __call__(self, p, t):
        if self.x is None:
            self.x = (p[0], p[1])
            self.t = t
            return self.x

        dt = t - self.t if self.t is not None else 0.0
        if dt <= 0:
            dt = DEFAULT_DT
        self.t = t

        vx = (p[0] - self.x[0]) / dt
        vy = (p[1] - self.x[1]) / dt
        ad = _alpha(self.d_cutoff, dt)
        self.dx = (self.dx[0] + ad * (vx - self.dx[0]),
                   self.dx[1] + ad * (vy - self.dx[1]))
        speed = math.sqrt(self.dx[0] ** 2 + self.dx[1] ** 2)

        a = _alpha(self.fc_min + self.beta * speed, dt)
        self.x = (self.x[0] + a * (p[0] - self.x[0]),
                  self.x[1] + a * (p[1] - self.x[1]))
        return self.x


def simulate(samples, fc_min, beta, d_cutoff=DEFAULT_D_CUTOFF, dt=DEFAULT_DT):
    """Aplica el filter a una lista de puntos equiespaciados (auto-tune de la GUI)."""
    f = OneEuro2D(fc_min, beta, d_cutoff)
    return [f(p, i * dt) for i, p in enumerate(samples)]
