"""
D6: paquete UDP v2 (driver -> calibrator). Struct fija en orden de red,
documentada en docs/PROTOCOL.md. Un paquete por report 0x37 y Wiimote.
"""

import math
import struct

VERSION = 2

# flags de TL/TR
DOT_VALID = 0x01
DOT_RECONSTRUCTED = 0x02

# flags generales
FLAG_CALIBRATED = 0x01
FLAG_DISTANCE_COMPENSATION = 0x02
FLAG_BAR_ON_TOP = 0x04
FLAG_FAKE_CURSOR = 0x08
FLAG_LOST = 0x10
FLAG_CP_VALID = 0x20
FLAG_CALIBRATING = 0x40

# codigos de error de captura
ERRORS = {None: 0, "no_ir": 1, "unstable": 2, "bad_geometry": 3, "inconsistent": 4}
ERROR_NAMES = {v: k for k, v in ERRORS.items()}

BATTERY_UNKNOWN = 0xFF
DOT_SIZE_UNKNOWN = 0xFF
RAW_ABSENT = 0x3FF

FORMAT = "".join([
    "!",
    "B",          # version
    "B",          # index (indice de mouse que devuelve la VirtualGun)
    "B",          # virtualgun (puerto + 1)
    "H",          # botones del Wiimote (sin mascara)
    "B",          # flags
    "HHB" * 4,    # dots en bruto: raw_x, raw_y (0x3FF = ausente), tamano
    "ffB" * 2,    # TL, TR del tracker (x, y normalizados) + flags
    "ff",         # camera point
    "ff",         # cursor (salida del gun, 0..1)
    "ff",         # cursor en pantalla completa (sin clamp)
    "b",          # paso de calibracion (-1 = no calibrando)
    "B",          # puntos capturados
    "B",          # pasos totales
    "ff",         # target actual (pantalla completa)
    "f",          # dispersion de las ultimas muestras (separaciones de barra, -1 = n/d)
    "B",          # ultimo error de captura
    "f",          # roll del acelerometro (grados, NaN = n/d)
    "f",          # angulo de TL->TR (grados)
    "f",          # separacion angular de los dots (rad)
    "f",          # sep_ref de la calibracion (rad)
    "B",          # bateria % (0xFF = n/d)
    "f",          # Hz de reports
    "ffff",       # area: x0, y0, w, h
    "f",          # useful zone
])

SIZE = struct.calcsize(FORMAT)


class Packet(object):
    """Contenido de un paquete v2 (todo con valores por defecto)."""

    __slots__ = (
        "version", "index", "virtualgun", "buttons", "flags", "raw", "dots",
        "cp", "cursor", "screen", "step", "captured", "total", "target",
        "spread", "error", "roll", "angle", "separation", "sep_ref",
        "battery", "hz", "area", "useful_zone",
    )

    def __init__(self):
        self.version = VERSION
        self.index = 0
        self.virtualgun = 0
        self.buttons = 0
        self.flags = 0
        self.raw = [(RAW_ABSENT, RAW_ABSENT, DOT_SIZE_UNKNOWN)] * 4
        self.dots = [(0.0, 0.0, 0), (0.0, 0.0, 0)]
        self.cp = (0.0, 0.0)
        self.cursor = (0.5, 0.5)
        self.screen = (0.5, 0.5)
        self.step = -1
        self.captured = 0
        self.total = 0
        self.target = (0.0, 0.0)
        self.spread = -1.0
        self.error = None
        self.roll = float("nan")
        self.angle = 0.0
        self.separation = 0.0
        self.sep_ref = 0.0
        self.battery = None
        self.hz = 0.0
        self.area = (0.0, 0.0, 1.0, 1.0)
        self.useful_zone = 0.85

    # ------------------------------------------------------------------
    def has(self, flag):
        return bool(self.flags & flag)

    @property
    def calibrating(self):
        return self.has(FLAG_CALIBRATING)

    @property
    def n_dots(self):
        return sum(1 for r in self.raw if r[1] != RAW_ABSENT)

    def pack(self):
        values = [self.version, self.index, self.virtualgun, self.buttons, self.flags]
        for r in self.raw:
            values += [r[0], r[1], r[2]]
        for d in self.dots:
            values += [d[0], d[1], d[2]]
        values += list(self.cp) + list(self.cursor) + list(self.screen)
        values += [self.step, self.captured, self.total]
        values += list(self.target)
        values += [self.spread, ERRORS.get(self.error, 0)]
        values += [self.roll, self.angle, self.separation, self.sep_ref]
        values += [BATTERY_UNKNOWN if self.battery is None else self.battery, self.hz]
        values += list(self.area) + [self.useful_zone]
        return struct.pack(FORMAT, *values)

    @classmethod
    def unpack(cls, data):
        """Packet desde bytes, o None si no es un paquete v2."""
        if len(data) != SIZE or data[0] != VERSION:
            return None
        v = list(struct.unpack(FORMAT, data))
        p = cls()
        p.version, p.index, p.virtualgun, p.buttons, p.flags = v[:5]
        i = 5
        p.raw = [tuple(v[i + 3 * k:i + 3 * k + 3]) for k in range(4)]
        i += 12
        p.dots = [tuple(v[i + 3 * k:i + 3 * k + 3]) for k in range(2)]
        i += 6
        p.cp = (v[i], v[i + 1])
        p.cursor = (v[i + 2], v[i + 3])
        p.screen = (v[i + 4], v[i + 5])
        i += 6
        p.step, p.captured, p.total = v[i:i + 3]
        i += 3
        p.target = (v[i], v[i + 1])
        p.spread = v[i + 2]
        p.error = ERROR_NAMES.get(v[i + 3])
        i += 4
        p.roll, p.angle, p.separation, p.sep_ref = v[i:i + 4]
        i += 4
        p.battery = None if v[i] == BATTERY_UNKNOWN else v[i]
        p.hz = v[i + 1]
        i += 2
        p.area = tuple(v[i:i + 4])
        p.useful_zone = v[i + 4]
        return p


def build_packet(wiimote, index, virtualgun):
    """Packet con el estado actual de un WiiMoteDevice (lado driver)."""
    pipeline = wiimote.pipeline
    p = Packet()
    p.index = index & 0xFF
    p.virtualgun = virtualgun & 0xFF
    p.buttons = wiimote.raw_buttons & 0xFFFF

    sizes = wiimote.ir_sizes
    p.raw = [
        (r[0], r[1], sizes[k]) if r is not None else (RAW_ABSENT, RAW_ABSENT, DOT_SIZE_UNKNOWN)
        for k, r in enumerate(wiimote.ir_raw)
    ]

    flags = 0
    cal = pipeline.calibration
    opts = pipeline.options
    if cal.calibrated:
        flags |= FLAG_CALIBRATED
    if opts.distance_compensation:
        flags |= FLAG_DISTANCE_COMPENSATION
    if opts.bar_on_top:
        flags |= FLAG_BAR_ON_TOP
    if pipeline.fake_cursor:
        flags |= FLAG_FAKE_CURSOR

    track = pipeline.track
    if track is not None:
        if track.lost:
            flags |= FLAG_LOST
        if track.valid:
            from dbar4gun.core.tracker import SQUARE_Y
            p.dots = [
                (track.tl[0], track.tl[1] / SQUARE_Y,
                 DOT_VALID | (DOT_RECONSTRUCTED if track.tl_rec else 0)),
                (track.tr[0], track.tr[1] / SQUARE_Y,
                 DOT_VALID | (DOT_RECONSTRUCTED if track.tr_rec else 0)),
            ]
            p.angle = math.degrees(track.angle)
        if track.roll is not None:
            p.roll = math.degrees(track.roll)

    cp = pipeline.cp
    if cp is not None:
        flags |= FLAG_CP_VALID
        p.cp = (cp.x, cp.y)
        p.separation = cp.sep

    p.cursor = tuple(wiimote.cursor)
    p.screen = pipeline.screen

    session = pipeline.session
    if session is not None:
        flags |= FLAG_CALIBRATING
        p.step = session.step
        p.captured = session.shots_taken
        p.total = len(session.targets)
        p.target = session.targets[min(session.step, len(session.targets) - 1)]
        spread = session.buffer.spread()
        p.spread = -1.0 if spread is None else spread
    p.error = pipeline.last_error

    p.sep_ref = cal.sep_ref
    p.battery = wiimote.battery
    p.hz = wiimote.hz
    area = opts.area
    p.area = (area.x0, area.y0, area.w, area.h)
    p.useful_zone = opts.useful_zone
    p.flags = flags
    return p
