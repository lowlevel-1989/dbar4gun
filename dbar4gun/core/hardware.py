"""
Parametros del hardware medidos con el calibrator (hardware.json).

- fov_h_deg:   FOV horizontal de la camara del Wiimote. Solo se usa para las
               distancias (distance_m, reach test): el pipeline usa
               siempre la focal nominal, asi una medida nueva no invalida las
               calibraciones guardadas (en el simulador, un FOV real de 38-42
               grados con la focal de 33 da la misma precision).
- acc_x_sign:  signo del eje X del acelerometro frente al roll (C17).
- bar_width_m: distancia entre los centros de los 2 grupos de LEDs de la barra.
- ir_sensitivity: nivel de la camara IR (C15). None = el del servicio
  (--ir-sensitivity); si se fija aqui, manda sobre la opcion del servicio.
"""

import math

from dbar4gun.core import tracker as _tracker

DEFAULT_FOV_H_DEG = 33.0
DEFAULT_ACC_X_SIGN = _tracker.ACC_X_SIGN
DEFAULT_BAR_WIDTH_M = 0.20

FOV_RANGE = (20.0, 60.0)
BAR_WIDTH_RANGE = (0.05, 0.60)

# alias del comando `hw` -> campo
KEYS = {
    "fov": "fov_h_deg",
    "fov_h_deg": "fov_h_deg",
    "acc_x_sign": "acc_x_sign",
    "acc": "acc_x_sign",
    "bar_width": "bar_width_m",
    "bar_width_m": "bar_width_m",
    "ir": "ir_sensitivity",
    "ir_sensitivity": "ir_sensitivity",
}

SENSOR_HALF_W = 512.0

# niveles de IR_SENSITIVITY (wiimote.py): 1..5 de wiibrew (mas alto = umbral de
# brillo mas bajo = mas sensible) y los bloques marcan (por defecto) y cliff
IR_LEVELS = ("1", "2", "3", "4", "5", "marcan", "cliff")
# marcan (umbral 0xc0 / 0x40) queda entre los niveles 2 y 4 de wiibrew
IR_LADDER = ("1", "2", "marcan", "4", "5")


def next_ir_sensitivity(current, direction):
    """
    Siguiente nivel hacia "higher" (mas sensible) o "lower", o None si ya
    esta en el extremo. 3 y cliff ocupan el mismo puesto que marcan.
    """
    i = IR_LADDER.index(current) if current in IR_LADDER else IR_LADDER.index("marcan")
    j = i + (1 if direction == "higher" else -1)
    if not 0 <= j < len(IR_LADDER):
        return None
    return IR_LADDER[j]


def focal_norm(fov_h_deg):
    """Focal en unidades normalizadas (1 = 1023 px), como pointer.FOCAL."""
    return (SENSOR_HALF_W / math.tan(math.radians(fov_h_deg / 2.0))) / 1023.0


def focal_px(fov_h_deg):
    return SENSOR_HALF_W / math.tan(math.radians(fov_h_deg / 2.0))


def fov_from_focal_px(f):
    return math.degrees(2.0 * math.atan(SENSOR_HALF_W / f))


class HardwareConfig(object):
    __slots__ = ("fov_h_deg", "acc_x_sign", "bar_width_m", "ir_sensitivity")

    def __init__(self, fov_h_deg=DEFAULT_FOV_H_DEG, acc_x_sign=DEFAULT_ACC_X_SIGN,
                 bar_width_m=DEFAULT_BAR_WIDTH_M, ir_sensitivity=None):
        self.fov_h_deg = DEFAULT_FOV_H_DEG
        self.acc_x_sign = DEFAULT_ACC_X_SIGN
        self.bar_width_m = DEFAULT_BAR_WIDTH_M
        self.ir_sensitivity = None
        self.set("fov_h_deg", fov_h_deg)
        self.set("acc_x_sign", acc_x_sign)
        self.set("bar_width_m", bar_width_m)
        if ir_sensitivity is not None:
            self.set("ir_sensitivity", ir_sensitivity)

    def set(self, key, value):
        """Valida y fija un campo (acepta los alias de KEYS). ValueError si no vale."""
        field = KEYS.get(key)
        if field is None:
            raise ValueError("unknown hardware key '{}' (fov, acc_x_sign, bar_width, ir_sensitivity)".format(key))
        if field == "ir_sensitivity":
            # "default" (o null en el json) vuelve a la opcion del servicio
            if value is None or str(value) == "default":
                self.ir_sensitivity = None
            elif str(value) in IR_LEVELS:
                self.ir_sensitivity = str(value)
            else:
                raise ValueError("ir_sensitivity: default, " + ", ".join(IR_LEVELS))
            return field
        v = float(value)
        if field == "fov_h_deg":
            if not FOV_RANGE[0] <= v <= FOV_RANGE[1]:
                raise ValueError("fov: {}..{} degrees".format(*FOV_RANGE))
            self.fov_h_deg = v
        elif field == "acc_x_sign":
            if v not in (-1.0, 1.0):
                raise ValueError("acc_x_sign: 1 or -1")
            self.acc_x_sign = v
        else:
            if not BAR_WIDTH_RANGE[0] <= v <= BAR_WIDTH_RANGE[1]:
                raise ValueError("bar_width: {}..{} m".format(*BAR_WIDTH_RANGE))
            self.bar_width_m = v
        return field

    def to_dict(self):
        return {"fov_h_deg": self.fov_h_deg, "acc_x_sign": self.acc_x_sign,
                "bar_width_m": self.bar_width_m, "ir_sensitivity": self.ir_sensitivity}

    @classmethod
    def from_dict(cls, d):
        """Ignora claves desconocidas y valores invalidos (se queda el defecto)."""
        hw = cls()
        for k, v in (d or {}).items():
            try:
                hw.set(k, v)
            except (ValueError, TypeError):
                pass
        return hw

    def copy(self):
        return HardwareConfig(self.fov_h_deg, self.acc_x_sign, self.bar_width_m,
                              self.ir_sensitivity)

    def true_separation(self, theta, nominal_focal):
        """
        Separacion angular con el FOV medido a partir de la calculada con la
        focal nominal (aproximacion de dots cerca del centro).
        """
        if theta <= 0:
            return 0.0
        k = nominal_focal / focal_norm(self.fov_h_deg)
        return 2.0 * math.atan(math.tan(theta * 0.5) * k)

    def distance(self, theta, nominal_focal):
        """Distancia (m) a la barra desde la separacion angular nominal."""
        t = self.true_separation(theta, nominal_focal)
        if t <= 1e-9:
            return 0.0
        return self.bar_width_m / (2.0 * math.tan(t * 0.5))
