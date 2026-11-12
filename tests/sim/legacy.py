"""
Replica del pipeline de la v0.18.2 (parser antiguo + IRSetupStandard +
calibracion de 3 puntos), solo para medir la baseline con el simulador.
"""

from dbar4gun import calibration, irsetup
from dbar4gun.core.gun import BUTTON_A, BUTTON_B, BUTTON_PLUS

# targets que mostraba la calibracion de 3 puntos antigua
LEGACY_TARGETS_3PT = [(0.05, 0.05), (0.95, 0.05), (0.5, 0.95)]


def legacy_parser_ir(payload):
    """Parser de la v0.18.2 (ausente si los 8 bits bajos de x e y son 0xFF)."""
    dots = []
    for off in (0, 5):
        b = payload[off:off + 5]
        for xl, yl, xs, ys in ((b[0], b[1], (b[2] & 0x30) << 4, (b[2] & 0xC0) << 2),
                               (b[3], b[4], (b[2] & 0x03) << 8, (b[2] & 0x0C) << 6)):
            x = 1 - (xl | xs) / 1023.5
            y = (yl | ys) / 767.5
            ok = float((xl & yl) < 0xFF)
            dots.append([max(0.0, min(1.0, x)), max(0.0, min(1.0, y)), ok])
    return dots


class LegacyDriver(object):
    def __init__(self, monkeypatch=None):
        self.ir_setup = irsetup.IRSetupStandard()
        self.calibration = calibration.CalibrationTopLeftTopRightBottomCenterPoint()
        self.calibration_on = 0

    def feed(self, report):
        buttons = (report[1] << 8) | report[2]
        acc = list(report[3:6])
        dots = legacy_parser_ir(report[6:16])
        sorted_dots = self.ir_setup.sort_and_restore(dots, acc)

        a = bool(buttons & BUTTON_A)
        b = bool(buttons & BUTTON_B)
        plus = bool(buttons & BUTTON_PLUS)
        if (a and plus) or self.calibration_on:
            done, _ = self.calibration.step(b, sorted_dots[:], acc)
            self.calibration_on = 0 if done else 1

        return self.calibration.map_coordinates(sorted_dots, acc)

    def calibrate(self, scene, roll_deg=0.0, settle=5):
        self.feed(scene.report(0.5, 0.5, roll_deg, BUTTON_A | BUTTON_PLUS))
        for sx, sy in LEGACY_TARGETS_3PT:
            for _ in range(settle):
                self.feed(scene.report(sx, sy, roll_deg))
            self.feed(scene.report(sx, sy, roll_deg, BUTTON_B))
        self.feed(scene.report(0.5, 0.5, roll_deg))
        assert self.calibration_on == 0, "la calibracion no termino"
