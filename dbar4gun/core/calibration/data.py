"""
Lo que se guarda de la calibracion de cada Wiimote (CalibrationData) y el
mapa nominal que se usa antes de calibrar.

Modos: MODE_DISABLED (0), MODE_2PT (1), MODE_3PT (2) y MODE_4PT (3).
"""

from dbar4gun.core.calibration.maps import AffineMap, HomographyMap


MODE_DISABLED = 0
MODE_2PT = 1
MODE_3PT = 2
MODE_4PT = 3


# Mapa nominal (sin calibrar): TV de 45" con barra de 20 cm a 3 cm del borde,
# jugador centrado. Medidas en separaciones de barra.
NOMINAL_TV_W_SEP = 4.98
NOMINAL_TV_H_SEP = 2.80
NOMINAL_BAR_GAP_SEP = 0.15
# separacion angular nominal a 3 m (rad)
NOMINAL_SEP = 0.0667


def nominal_map():
    """
    Aproximacion de primer orden con compensacion de distancia: el camera point
    vale FOCAL * (punto apuntado - barra) en separaciones de barra.
    """
    from dbar4gun.core.pointer import FOCAL

    kx = 1.0 / (FOCAL * NOMINAL_TV_W_SEP)
    ky = 1.0 / (FOCAL * NOMINAL_TV_H_SEP)
    off = (NOMINAL_TV_H_SEP * 0.5 + NOMINAL_BAR_GAP_SEP) / NOMINAL_TV_H_SEP
    return AffineMap(kx, 0.0, 0.0, ky, 0.5, 0.5 - off)


def _level(v):
    """smoothing_level guardado: entero >= 0 o None."""
    if v is None:
        return None
    return max(0, int(v))


class CalibrationData(object):
    """Lo que se guarda por Wiimote."""

    VERSION = 1

    def __init__(self, mode=MODE_3PT, affine=None, sep_ref=0.0,
                 distance_compensation=True, targets=None,
                 calibrated=False, timestamp=0.0, smoothing_level=None):
        self.mode = mode
        self.affine = affine or nominal_map()
        self.sep_ref = sep_ref
        self.distance_compensation = distance_compensation
        self.targets = targets or []
        self.calibrated = calibrated
        self.timestamp = timestamp
        # smoothing de este Wiimote (None = el --smoothing-level del servicio)
        self.smoothing_level = smoothing_level

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
            "calibrated": self.calibrated,
            "timestamp": self.timestamp,
            "smoothing_level": self.smoothing_level,
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
            calibrated=bool(d.get("calibrated", True)),
            timestamp=float(d.get("timestamp", 0.0)),
            smoothing_level=_level(d.get("smoothing_level")),
        )
