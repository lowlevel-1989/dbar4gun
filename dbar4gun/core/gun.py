"""
Pipeline completo de un Wiimote, sin I/O:

    dots + acelerometro + botones -> tracker -> camera point -> calibracion
    -> perfil de area -> cursor (normalizado a la salida del gun)

Tambien lleva la logica de botones de calibracion (A+plus, A+minus, B+plus) y
deja las acciones de I/O (LEDs, rumble, guardar) en una cola que vacia
wiimote.py.
"""

import math

from dbar4gun.core.area import AreaProfile, clamp01
from dbar4gun.core.calibration.data import (
    CalibrationData, MODE_DISABLED, MODE_2PT, MODE_3PT, MODE_4PT,
)
from dbar4gun.core.calibration.session import CalibrationSession, CALIBRATION_SHOTS
from dbar4gun.core.filters import OneEuro2D, params_for_level, DEFAULT_LEVEL
from dbar4gun.core.hardware import HardwareConfig
from dbar4gun.core.pointer import camera_point, FOCAL
from dbar4gun.core.tracker import Tracker

BUTTON_B = 1 << 0x2
BUTTON_A = 1 << 0x3
BUTTON_MINUS = 1 << 0x4
BUTTON_HOME = 1 << 0x7
BUTTON_PLUS = 1 << 0xc

LED_1 = 0x10
LED_2 = 0x20
LED_3 = 0x40
LED_4 = 0x80

# durante la calibracion solo pasan estos botones al juego (como antes)
CALIBRATION_BUTTONS_MASK = BUTTON_MINUS | BUTTON_PLUS | BUTTON_HOME

# sin dots se mantiene el cursor este tiempo antes de llevarlo al borde
# (un parpadeo del IR no debe disparar fuera de pantalla)
LOST_HOLD = 0.05
# velocidad minima (salida/s) para usar la direccion del movimiento
LOST_MIN_SPEED = 0.5

DEFAULT_USEFUL_ZONE = 0.85


class GunOptions(object):
    def __init__(self, calibration_mode=MODE_3PT, tilt_correction=True,
                 distance_compensation=True, area="full", useful_zone=DEFAULT_USEFUL_ZONE,
                 targets=None, screen_aspect=16.0 / 9.0,
                 smoothing_level=DEFAULT_LEVEL, hardware=None):
        self.calibration_mode = calibration_mode
        self.tilt_correction = tilt_correction
        self.distance_compensation = distance_compensation
        self.screen_aspect = screen_aspect
        self.area = area if isinstance(area, AreaProfile) else AreaProfile.parse(area, screen_aspect)
        self.useful_zone = useful_zone
        # targets de la calibracion de 3 puntos en espacio de salida (TL, TR, BC)
        self.targets = targets
        # One Euro (None = sin filter)
        self.filter = params_for_level(smoothing_level)
        # FOV, signo del acelerometro y ancho de barra (hardware.json)
        self.hardware = hardware or HardwareConfig()


def parse_targets(text):
    """'x1,y1,x2,y2,x3,y3' -> [(x1, y1), (x2, y2), (x3, y3)]"""
    v = [float(t) for t in text.split(",")]
    if len(v) != 6 or not all(0.0 <= t <= 1.0 for t in v):
        raise ValueError("calibration targets: expected 6 values between 0 and 1")
    return [(v[0], v[1]), (v[2], v[3]), (v[4], v[5])]


class GunPipeline(object):
    def __init__(self, options=None, calibration=None):
        self.options = options or GunOptions()
        self.tracker = Tracker(acc_x_sign=self.options.hardware.acc_x_sign)
        self.calibration = calibration or CalibrationData(
            mode=self.options.calibration_mode,
            distance_compensation=self.options.distance_compensation)
        self.session = None
        self.actions = []

        self.fake_cursor = False
        self.state_fake_cursor = 0
        self.prev_a_plus = False
        self.prev_a_minus = False

        self.cursor = (0.5, 0.5)
        # cursor en pantalla completa (sin area ni clamp), para el calibrator
        self.screen = (0.5, 0.5)
        self.last_error = None
        self.velocity = (0.0, 0.0)
        self.last_valid_t = None
        self.last_t = None
        self.track = None
        self.cp = None
        self.filter = None

        self._update_map()

    # ------------------------------------------------------------------
    # configuracion
    def _update_map(self):
        self.map = self.calibration.map_for(self.options.distance_compensation)
        params = self.filter_params()
        if params is None:
            self.filter = None
        else:
            self.filter = OneEuro2D(params["fc_min"], params["beta"], params["d_cutoff"])

    def set_hardware(self, hardware):
        """Aplica los valores medidos con el calibrator."""
        self.options.hardware = hardware
        self.tracker.acc_x_sign = hardware.acc_x_sign

    def distance(self, theta):
        return self.options.hardware.distance(theta, FOCAL)

    def filter_params(self):
        """Parametros del One Euro: los del Wiimote (calibracion) o los del servicio."""
        if self.options.filter is None:
            return None
        params = dict(self.options.filter)
        if self.calibration.filter:
            params.update(self.calibration.filter)
        return params

    def set_filter(self, fc_min, beta, d_cutoff=None):
        """parametros por Wiimote; se guardan con la calibracion."""
        params = {"fc_min": float(fc_min), "beta": float(beta)}
        if d_cutoff is not None:
            params["d_cutoff"] = float(d_cutoff)
        cal = self.calibration
        cal.filter = dict(cal.filter or {}, **params)
        self._update_map()
        if cal.calibrated:
            self.actions.append(("save", cal, False))

    def set_calibration(self, data):
        # el filter ajustado del Wiimote se conserva al recalibrar
        if data.filter is None and getattr(self, "calibration", None) is not None:
            data.filter = self.calibration.filter
        self.calibration = data
        self._update_map()

    def set_area(self, area):
        if not isinstance(area, AreaProfile):
            area = AreaProfile.parse(area, self.options.screen_aspect)
        self.options.area = area

    @property
    def calibrating(self):
        return self.session is not None

    def calibration_targets(self, kind):
        """Targets (espacio de salida) de cada tipo de calibracion."""
        uz = self.options.useful_zone
        if kind == "2pt":
            return [(0.5, 0.5), (0.1, 0.1)]
        if kind == "quick":
            return [(0.1, 0.1), (0.9, 0.1)]
        if kind == "4pt":
            # esquinas TL, TR, BR, BL
            return [(0.1, 0.1), (0.9, 0.1), (0.9, uz), (0.1, uz)]
        return self.options.targets or [(0.1, 0.1), (0.9, 0.1), (0.5, uz)]

    def _target_leds(self, kind, step):
        if kind == "2pt":
            return (LED_2 | LED_3, LED_1)[step]
        if kind == "quick":
            return (LED_1, LED_4)[step]
        if kind == "4pt":
            return (LED_1, LED_4, LED_3 | LED_4, LED_1 | LED_2)[step]
        return (LED_1, LED_4, LED_2 | LED_3)[step]

    # ------------------------------------------------------------------
    # calibracion
    def default_kind(self):
        mode = self.options.calibration_mode
        if mode == MODE_DISABLED:
            return None
        if mode == MODE_2PT:
            return "2pt"
        full = "4pt" if mode == MODE_4PT else "3pt"
        # con calibracion guardada, A+plus hace la recalibracion rapida
        if self.calibration.calibrated and self.calibration.mode in (MODE_3PT, MODE_4PT):
            return "quick"
        return full

    def start_calibration(self, kind=None, screen_targets=None):
        """
        kind: None (lo que haria A+plus), "full", "3pt", "2pt" o "quick".
        screen_targets: targets en pantalla completa (el calibrator los
        adapta al alcance); si no, los de la configuracion.
        """
        if kind == "full":
            kind = {MODE_2PT: "2pt", MODE_4PT: "4pt"}.get(self.options.calibration_mode, "3pt")
        if kind is None:
            kind = self.default_kind()
        if kind is None:
            return False
        if kind == "quick" and not self.calibration.calibrated:
            kind = "4pt" if self.options.calibration_mode == MODE_4PT else "3pt"

        if screen_targets:
            targets = [tuple(t) for t in screen_targets]
            expected = {"2pt": 2, "quick": 2, "4pt": 4}.get(kind, 3)
            if len(targets) != expected:
                raise ValueError("calibration: {} needs {} targets".format(kind, expected))
            area = self.options.area
            targets_out = [(clamp01(o[0]), clamp01(o[1]))
                           for o in (area.to_output(x, y) for x, y in targets)]
        else:
            targets_out = self.calibration_targets(kind)
            targets = [self.options.area.to_screen(x, y) for x, y in targets_out]
        self.last_error = None
        # la recalibracion rapida (en partida) sigue con un disparo por target
        self.session = CalibrationSession(
            kind, targets, self.options.distance_compensation,
            base=self.calibration,
            shots=1 if kind == "quick" else CALIBRATION_SHOTS)
        self.session.targets_out = targets_out
        self.actions.append(("leds", self._target_leds(kind, 0)))
        return True

    def cancel_calibration(self):
        if self.session is not None:
            self.session = None
            self.actions.append(("restore_leds",))

    def reset_calibration(self):
        """A+minus: vuelve al mapa nominal (no borra lo guardado)."""
        self.cancel_calibration()
        self.set_calibration(CalibrationData(
            mode=self.options.calibration_mode,
            distance_compensation=self.options.distance_compensation))

    def _calibration_frame(self, cp, button_b, now):
        session = self.session
        event = session.feed(cp, button_b, now)
        if event is None:
            return
        kind, value = event
        if kind == "shot":
            # otro disparo al mismo target: el LED no cambia
            self.last_error = None
            self.actions.append(("rumble", "ok"))
        elif kind == "captured":
            self.last_error = None
            self.actions.append(("rumble", "ok"))
            self.actions.append(("leds", self._target_leds(session.kind, value)))
        elif kind == "error":
            self.last_error = value
            self.actions.append(("rumble", "error"))
            self.actions.append(("calibration_error", value))
            self.actions.append(("leds", self._target_leds(session.kind, session.step)))
        elif kind == "done":
            self.last_error = None
            self.session = None
            self.set_calibration(value)
            self.actions.append(("rumble", "done"))
            self.actions.append(("restore_leds",))
            self.actions.append(("save", value, True))

    # ------------------------------------------------------------------
    def _buttons(self, buttons):
        a = bool(buttons & BUTTON_A)
        b = bool(buttons & BUTTON_B)
        plus = bool(buttons & BUTTON_PLUS)
        minus = bool(buttons & BUTTON_MINUS)

        # B+plus: cursor falso (0, 0), igual que antes
        if b and plus and self.state_fake_cursor == 0:
            self.fake_cursor = not self.fake_cursor
            self.state_fake_cursor = 1
        if not plus and self.state_fake_cursor == 1:
            self.state_fake_cursor = 0

        a_plus = a and plus
        a_minus = a and minus
        if a_plus and not self.prev_a_plus and self.session is None:
            self.start_calibration()
        if a_minus and not self.prev_a_minus:
            self.reset_calibration()
        self.prev_a_plus = a_plus
        self.prev_a_minus = a_minus
        return b

    def process(self, dots, acc, buttons, now):
        """
        Un report 0x37. Devuelve (cursor, buttons) con el cursor normalizado a
        la salida del gun (perfil de area aplicado, con clamp).
        """
        button_b = self._buttons(buttons)

        self.track = self.tracker.update(dots, acc, now)
        self.cp = camera_point(self.track, self.options.tilt_correction,
                               self.options.distance_compensation)

        if self.session is not None:
            self._calibration_frame(self.cp, button_b, now)

        if self.session is not None:
            # durante la calibracion el cursor marca el target
            tx, ty = self.session.targets_out[min(self.session.step,
                                                  len(self.session.targets_out) - 1)]
            self.last_t = now
            return (tx, ty), buttons & CALIBRATION_BUTTONS_MASK

        cursor = self._cursor(now)
        if self.fake_cursor:
            return (0.0, 0.0), buttons
        return cursor, buttons

    def _cursor(self, now):
        area = self.options.area
        if self.cp is not None:
            sx, sy = self.map.apply(self.cp.x, self.cp.y)
            self.screen = (sx, sy)
            if self.filter is not None:
                sx, sy = self.filter((sx, sy), now)
            ox, oy = area.to_output(sx, sy)
            if self.last_t is not None and now > self.last_t:
                dt = now - self.last_t
                vx = (ox - self.cursor[0]) / dt
                vy = (oy - self.cursor[1]) / dt
                self.velocity = (self.velocity[0] * 0.5 + vx * 0.5,
                                 self.velocity[1] * 0.5 + vy * 0.5)
            self.cursor = (ox, oy)
            self.last_valid_t = now
            self.last_t = now
            return (clamp01(ox), clamp01(oy))

        self.last_t = now
        if (self.track is not None and self.track.lost and self.last_valid_t is not None
                and now - self.last_valid_t >= LOST_HOLD):
            # sin dots, el cursor sale por el borde por el que se fue
            if self.filter is not None:
                self.filter.reset()
            edge = edge_point(self.cursor, self.velocity)
            self.screen = area.to_screen(*edge)
            return edge

        return (clamp01(self.cursor[0]), clamp01(self.cursor[1]))

    def drain_actions(self):
        actions = self.actions
        self.actions = []
        return actions

    # ------------------------------------------------------------------
    def status(self):
        cal = self.calibration
        track = self.track
        st = {
            "calibrated": cal.calibrated,
            "calibration_mode": cal.mode,
            "mode_option": self.options.calibration_mode,
            "calibrating": self.calibrating,
            "calibration_step": self.session.step if self.session else None,
            "distance_compensation": self.options.distance_compensation,
            "sep_ref": cal.sep_ref,
            "affine": cal.affine.to_list(),
            # independientes del tipo de mapa (afin u homografia):
            # posicion de la barra en la TV (apuntar a la barra = camera point 0)
            "bar_position": list(self.map.apply(0.0, 0.0)),
            "scale_ratio": map_scale_ratio(self.map),
            "screen_aspect": self.options.screen_aspect,
            "area": self.options.area.name,
            "useful_zone": self.options.useful_zone,
            "filter": self.filter_params(),
            "dots": track.n_dots if track else 0,
            "roll_deg": math.degrees(track.roll) if track and track.roll is not None else None,
        }
        if self.cp is not None:
            st["separation"] = self.cp.sep
            st["distance_m"] = round(self.distance(self.cp.sep), 2)
        if cal.sep_ref:
            st["distance_ref_m"] = round(self.distance(cal.sep_ref), 2)
        st["hardware"] = self.options.hardware.to_dict()
        return st


def map_scale_ratio(m, c=(0.0, 0.0), eps=1e-3):
    """
    (d sy / d cy) / (d sx / d cx) del mapa en c (jacobiano numerico). Con una
    calibracion buena se parece al aspecto de la TV.
    """
    x0, y0 = m.apply(c[0], c[1])
    x1, _ = m.apply(c[0] + eps, c[1])
    _, y2 = m.apply(c[0], c[1] + eps)
    sx = (x1 - x0) / eps
    sy = (y2 - y0) / eps
    if sx <= 0 or sy <= 0:
        return None
    return sy / sx


def edge_point(p, v):
    """
    Punto del borde de [0, 1]^2 por el que sale el cursor: siguiendo la
    velocidad si es apreciable, si no el borde mas cercano.
    """
    px, py = clamp01(p[0]), clamp01(p[1])
    vx, vy = v
    if math.sqrt(vx * vx + vy * vy) >= LOST_MIN_SPEED:
        ts = []
        if vx > 0:
            ts.append((1.0 - px) / vx)
        elif vx < 0:
            ts.append(-px / vx)
        if vy > 0:
            ts.append((1.0 - py) / vy)
        elif vy < 0:
            ts.append(-py / vy)
        t = min(ts)
        return (clamp01(px + vx * t), clamp01(py + vy * t))

    d = {"l": px, "r": 1.0 - px, "t": py, "b": 1.0 - py}
    edge = min(d, key=lambda k: d[k])
    if edge == "l":
        return (0.0, py)
    if edge == "r":
        return (1.0, py)
    if edge == "t":
        return (px, 0.0)
    return (px, 1.0)
