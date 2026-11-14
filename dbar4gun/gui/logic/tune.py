"""
Auto-tune del filtro One Euro.

Con el Wiimote quieto se elige fc_min (cuanto tiembla el cursor) y moviendolo
se elige beta (cuanto se retrasa).
"""

import math

from dbar4gun.gui.logic.gallery import GAME_H, GAME_W


FC_CANDIDATES = (4.0, 3.0, 2.0, 1.5, 1.0, 0.7, 0.5, 0.35, 0.25)
BETA_CANDIDATES = (1.0, 2.0, 5.0, 10.0, 20.0, 40.0)
JITTER_TARGET_GAME = 0.5
LAG_TARGET_GAME = 6.0


def _game_dist(a, b, area):
    return math.sqrt(((a[0] - b[0]) / area[2] * GAME_W) ** 2 + ((a[1] - b[1]) / area[3] * GAME_H) ** 2)


def jitter_game(samples, area, warmup=0.3):
    """Desviacion maxima (px de juego) respecto a la media, sin el arranque."""
    s = samples[int(len(samples) * warmup):]
    if not s:
        return None
    m = (sum(p[0] for p in s) / len(s), sum(p[1] for p in s) / len(s))
    return max(_game_dist(p, m, area) for p in s)


def choose_fc_min(still, area, dt=0.01, beta=0.0, target=JITTER_TARGET_GAME):
    """
    La fc_min mas alta (menos retraso) cuyo jitter con el Wiimote quieto queda
    por debajo del objetivo. Devuelve (fc_min, jitter).
    """
    from dbar4gun.core.filters import simulate
    best = None
    for fc in FC_CANDIDATES:
        j = jitter_game(simulate(still, fc, beta, dt=dt), area)
        best = (fc, j)
        if j is not None and j <= target:
            return best
    return best


def choose_beta(moving, fc_min, area, dt=0.01, target=LAG_TARGET_GAME):
    """
    La beta mas baja (menos jitter) cuyo retraso medio en movimiento queda por
    debajo del objetivo. El retraso se mide frente a la senal sin filtrar.
    Devuelve (beta, retraso).
    """
    from dbar4gun.core.filters import simulate
    best = None
    skip = len(moving) // 5
    for beta in BETA_CANDIDATES:
        f = simulate(moving, fc_min, beta, dt=dt)
        lag = [_game_dist(a, b, area) for a, b in zip(f[skip:], moving[skip:])]
        best = (beta, sum(lag) / len(lag) if lag else None)
        if lag and best[1] <= target:
            return best
    return best


def motion_amount(samples, area):
    """Recorrido (px de juego) de una prueba en movimiento, para validarla."""
    return sum(_game_dist(a, b, area) for a, b in zip(samples, samples[1:]))
