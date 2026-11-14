"""
Una calibracion de principio a fin (CalibrationSession): un target por
paso, varias vueltas a los targets, y al final calcula el mapa y devuelve
CalibrationData. Errores: ERR_INCONSISTENT (dos disparos al mismo target no
coinciden) y ERR_GEOMETRY (el mapa sale mal; se repite).
"""

import math
import time

from dbar4gun.core.calibration.capture import CaptureBuffer, median
from dbar4gun.core.calibration.data import CalibrationData, MODE_2PT, MODE_3PT, MODE_4PT
from dbar4gun.core.calibration.maps import (
    geometry_ok, quick_recalibrate, solve_affine_3pt, solve_homography_4pt,
    solve_scale_offset_2pt,
)


ERR_GEOMETRY = "bad_geometry"
ERR_INCONSISTENT = "inconsistent"

# vueltas a los targets en la calibracion completa (un disparo por target en
# cada vuelta): se promedian, asi un disparo algo desviado (pulso, tiron) no
# desplaza toda la calibracion. Si dos disparos al mismo target se separan mas
# de MAX_SHOT_DIFF_SEP (en separaciones de barra, ~0.4 sep = ~150 px de TV en
# una TV de 45" a 2 m) uno de los dos fue a otro sitio y se repiten los de ese
# target.
CALIBRATION_SHOTS = 2
MAX_SHOT_DIFF_SEP = 0.4


class CalibrationSession(object):
    """
    Maquina de estados de una calibracion: un target por paso, captura en el
    flanco de subida de B.

    kind: "3pt" (TL, TR, BC), "2pt" (modo 1: centro, TL) o "quick".
    targets: puntos en pantalla (normalizados a la TV completa).
    shots: vueltas a los targets. Cada vuelta pasa por todos (TL, TR, BC, TL,
    TR, BC): cada disparo es un apuntado nuevo y la media de los de un target
    compensa el pulso (dos disparos seguidos se desvian igual).
    """

    def __init__(self, kind, targets, distance_compensation=True,
                 base=None, shots=1):
        self.kind = kind
        self.shots = max(1, int(shots))
        self.targets = list(targets)
        self.distance_compensation = distance_compensation
        self.base = base
        self.captures = []
        self.seps = []
        self.buffer = CaptureBuffer()
        self.prev_b = True   # no capturar si B ya venia pulsado
        self.result = None
        self._reset_shots()

    def _reset_shots(self):
        # orden de los disparos (indices de target) y disparos validos por target
        self.queue = list(range(len(self.targets))) * self.shots
        self.samples = [[] for _ in self.targets]

    @property
    def step(self):
        """Indice del target al que hay que disparar ahora."""
        return self.queue[0] if self.queue else len(self.targets)

    @property
    def done(self):
        return self.result is not None

    @property
    def target(self):
        return self.targets[min(self.step, len(self.targets) - 1)]

    @property
    def shots_taken(self):
        """Disparos validos de toda la sesion."""
        return sum(len(s) for s in self.samples)

    @property
    def total_shots(self):
        return len(self.targets) * self.shots

    def feed(self, cp, button_b, now=None):
        """
        Un frame. Devuelve None, ("shot", step) (otro disparo al mismo
        target), ("captured", step) (cambia de target), ("error", codigo) o
        ("done", CalibrationData).
        """
        event = None
        edge = button_b and not self.prev_b
        self.prev_b = button_b

        if edge:
            # la captura usa los frames anteriores al flanco (el de B tiembla)
            point, sep, err = self.buffer.capture()
            unit = getattr(self.buffer, "unit", 1.0)
            self.buffer.clear()
            if err:
                event = ("error", err)
            else:
                event = self._shot(point, sep, unit, now)
        else:
            self.buffer.push(cp)
        return event

    def _shot(self, point, sep, unit, now):
        i = self.queue[0]
        prev = self.samples[i]
        if prev:
            first = prev[0][0]
            diff = math.sqrt((point[0] - first[0]) ** 2 + (point[1] - first[1]) ** 2) / unit
            if diff > MAX_SHOT_DIFF_SEP:
                # uno de los dos fue a otro sitio: se repiten los de este target
                del self.queue[0]
                self.queue[0:0] = [i] * (len(prev) + 1)
                self.samples[i] = []
                return ("error", ERR_INCONSISTENT)
        prev.append((point, sep))
        del self.queue[0]
        if not self.queue:
            self.captures = []
            self.seps = []
            for ss in self.samples:
                n = float(len(ss))
                self.captures.append((sum(p[0][0] for p in ss) / n, sum(p[0][1] for p in ss) / n))
                self.seps.append(median([p[1] for p in ss]))
            return self._finish(now)
        if self.queue[0] == i:
            return ("shot", i)
        return ("captured", self.queue[0])

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
            self.captures = []
            self.seps = []
            self._reset_shots()
            return ("error", ERR_GEOMETRY)

        sep_ref = median(self.seps)
        if self.kind == "quick" and self.base.sep_ref:
            # la recalibracion rapida conserva la escala vertical de la
            # principal, asi que tambien su distancia de referencia
            sep_ref = self.base.sep_ref

        self.result = CalibrationData(
            mode=mode, affine=m, sep_ref=sep_ref,
            distance_compensation=self.distance_compensation,
            targets=self.targets if self.kind != "quick" else self.base.targets,
            calibrated=True,
            # fecha real (el `now` del pipeline es monotonic, desde el arranque)
            timestamp=time.time())
        return ("done", self.result)
