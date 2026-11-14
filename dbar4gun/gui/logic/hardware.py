"""
Hardware check: cada paso mide algo y da un veredicto (OK, WARN, FAIL, NA).

- link_check: Bluetooth o DolphinBar, bateria, Hz.
- IRQuality: LEDs debiles y fuentes IR extra.
- AccSignCheck: signo del acelerometro.
- FovMeasure: FOV de la camara IR.
- BarSideCheck: barra encima de la TV (debajo, solo con una TV pequena).
- DisconnectCheck: que el Wiimote se recupera al apagarlo y encenderlo.
"""

import math

from dbar4gun.core.hardware import fov_from_focal_px
from dbar4gun.gui.logic.calibration import median
from dbar4gun.protocol import (
    DOT_RECONSTRUCTED, DOT_VALID, FLAG_CP_VALID, RAW_ABSENT,
)


# Autodiagnostico de hardware
OK, WARN, FAIL, NA = "ok", "warn", "fail", "na"

SENSOR_CENTER = (511.5, 383.5)


def _wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def link_check(status, packet):
    """
    Paso 1: tipo de conexion (clave del Wiimote), Hz y bateria.
    Devuelve dict con verdict y los valores.
    """
    status = status or {}
    key = status.get("key") or ""
    if key.startswith("usb:"):
        link = "dolphinbar"
        slot = None
        tail = key.rsplit("input", 1)
        if len(tail) == 2 and tail[1].isdigit():
            slot = int(tail[1]) + 1
    elif key.startswith("bt:"):
        link, slot = "bluetooth", None
    else:
        link, slot = "unknown", None
    hz = packet.hz if packet is not None else 0.0
    battery = packet.battery if packet is not None else None
    verdict = OK
    notes = []
    if hz < 80:
        verdict = WARN
        notes.append("low_hz")
    if battery is not None and battery < 20:
        verdict = WARN
        notes.append("low_battery")
    if link == "unknown":
        notes.append("no_key")
    return {"verdict": verdict, "link": link, "slot": slot, "key": key, "hz": round(hz, 1),
            "battery": battery, "notes": notes}


class IRQuality(object):
    """
    Paso 2: con el Wiimote apuntando a la TV (mejor apoyado y quieto):
    - % de paquetes con los 2 dots vistos (sin reconstruir);
    - dot reconstruido por lado (un LED debil o tapado);
    - fuentes IR de mas;
    - jitter del punto medio (px del sensor, desviacion tipica).
    """

    MIN_PACKETS = 150

    def __init__(self):
        self.n = 0
        self.both = 0
        self.lost = 0
        self.rebuilt = [0, 0]   # por indice de dot del paquete (0 = TL, 1 = TR)
        self.extra = 0
        self.max_dots = 0
        self.mids = []

    def add(self, p):
        self.n += 1
        d0, d1 = p.dots
        v0, v1 = bool(d0[2] & DOT_VALID), bool(d1[2] & DOT_VALID)
        r0, r1 = bool(d0[2] & DOT_RECONSTRUCTED), bool(d1[2] & DOT_RECONSTRUCTED)
        if v0 and v1 and not r0 and not r1:
            self.both += 1
            raw = [r for r in p.raw if r[1] != RAW_ABSENT]
            if len(raw) == 2:
                self.mids.append(((raw[0][0] + raw[1][0]) / 2.0, (raw[0][1] + raw[1][1]) / 2.0))
        if not v0 and not v1:
            self.lost += 1
        if v0 and r0:
            self.rebuilt[0] += 1
        if v1 and r1:
            self.rebuilt[1] += 1
        n = p.n_dots
        self.max_dots = max(self.max_dots, n)
        if n > 2:
            self.extra += 1

    def jitter_px(self):
        if len(self.mids) < 10:
            return None
        mx = sum(m[0] for m in self.mids) / len(self.mids)
        my = sum(m[1] for m in self.mids) / len(self.mids)
        var = sum((m[0] - mx) ** 2 + (m[1] - my) ** 2 for m in self.mids) / len(self.mids)
        return math.sqrt(var)

    def ready(self):
        return self.n >= self.MIN_PACKETS

    def result(self):
        if not self.n:
            return {"verdict": NA}
        both = self.both / float(self.n)
        extra = self.extra / float(self.n)
        lost = self.lost / float(self.n)
        # el TL del espacio normalizado es el LED derecho (x invertida)
        weak = None
        r_right, r_left = self.rebuilt[0] / float(self.n), self.rebuilt[1] / float(self.n)
        if max(r_right, r_left) >= 0.05 and max(r_right, r_left) >= 3 * min(r_right, r_left):
            weak = "right" if r_right > r_left else "left"
        notes = []
        verdict = OK
        if lost >= 0.5:
            verdict = FAIL
            notes.append("no_bar")
        if extra >= 0.05:
            verdict = WARN if verdict == OK else verdict
            notes.append("extra_ir")
        if weak:
            verdict = WARN if verdict == OK else verdict
            notes.append("weak_" + weak)
        elif both < 0.95 and lost < 0.5:
            verdict = WARN if verdict == OK else verdict
            notes.append("dots_drop")
        # recomendacion de --ir-sensitivity
        sensitivity = None
        if "extra_ir" in notes:
            sensitivity = "lower"
        elif "dots_drop" in notes or weak:
            sensitivity = "higher"
        j = self.jitter_px()
        return {"verdict": verdict, "both": round(both, 3), "extra": round(extra, 3),
                "lost": round(lost, 3), "weak_led": weak, "max_dots": self.max_dots,
                "jitter_px": round(j, 2) if j is not None else None,
                "sensitivity": sensitivity, "notes": notes}


class AccSignCheck(object):
    """
    Paso 3: girando el Wiimote despacio (+-45 grados) con la barra a la
    vista, el angulo de los dots no depende del acelerometro: con el signo bien,
    angulo = -roll (+ inclinacion fija de la barra). Pendiente de la recta
    angulo/roll: ~ -1 bien, ~ +1 invertido.
    """

    MIN_RANGE = 40.0      # grados de roll recorridos
    MAX_ROLL = 70.0

    def __init__(self):
        self.samples = []

    def add(self, p):
        if p.n_dots < 2 or math.isnan(p.roll) or abs(p.roll) > self.MAX_ROLL:
            return
        d0, d1 = p.dots
        if not (d0[2] & DOT_VALID and d1[2] & DOT_VALID):
            return
        if (d0[2] | d1[2]) & DOT_RECONSTRUCTED:
            return
        # el orden TL/TR puede invertirse: el angulo se reduce a (-90, 90]
        a = _wrap180(p.angle)
        if a > 90.0:
            a -= 180.0
        elif a <= -90.0:
            a += 180.0
        self.samples.append((p.roll, a))

    def roll_range(self):
        if not self.samples:
            return 0.0
        rolls = [r for r, _ in self.samples]
        return max(rolls) - min(rolls)

    def ready(self):
        return len(self.samples) >= 30 and self.roll_range() >= self.MIN_RANGE

    def slope(self):
        n = len(self.samples)
        if n < 2:
            return None
        mr = sum(r for r, _ in self.samples) / n
        ma = sum(a for _, a in self.samples) / n
        sxx = sum((r - mr) ** 2 for r, _ in self.samples)
        if sxx <= 1e-9:
            return None
        sxy = sum((r - mr) * (a - ma) for r, a in self.samples)
        return sxy / sxx

    def result(self, current_sign):
        k = self.slope()
        if k is None or not self.ready():
            return {"verdict": NA, "slope": k, "range": round(self.roll_range(), 1)}
        if k <= -0.6:
            verdict, sign = OK, current_sign
        elif k >= 0.6:
            verdict, sign = FAIL, -current_sign
        else:
            verdict, sign = WARN, None
        return {"verdict": verdict, "slope": round(k, 3), "range": round(self.roll_range(), 1),
                "acc_x_sign": sign}


def expected_separation(distance, bar_width):
    """Angulo (rad) entre los 2 LEDs vistos de frente a `distance` m."""
    return 2.0 * math.atan(bar_width / (2.0 * distance))


def _ray_angle(p1, p2, f, center=SENSOR_CENTER):
    x1, y1 = p1[0] - center[0], p1[1] - center[1]
    x2, y2 = p2[0] - center[0], p2[1] - center[1]
    dot = x1 * x2 + y1 * y2 + f * f
    n1 = math.sqrt(x1 * x1 + y1 * y1 + f * f)
    n2 = math.sqrt(x2 * x2 + y2 * y2 + f * f)
    return math.acos(max(-1.0, min(1.0, dot / (n1 * n2))))


def solve_focal_px(p1, p2, alpha, lo=200.0, hi=10000.0):
    """
    Focal (px) con la que los dots p1, p2 (px del sensor) forman el angulo
    `alpha`. El angulo baja al subir la focal: biseccion. None si no hay
    solucion en el rango.
    """
    if alpha <= 0 or not (_ray_angle(p1, p2, hi) <= alpha <= _ray_angle(p1, p2, lo)):
        return None
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if _ray_angle(p1, p2, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


class FovMeasure(object):
    """
    Paso 4 (R3): de pie a una distancia conocida (cinta metrica, de frente a
    la barra y apuntando cerca de ella), la focal sale de la separacion de los
    dots en px y del angulo que forman los LEDs: f -> FOV horizontal.
    """

    MIN_SAMPLES = 60
    MAX_OFF_CENTER = 250.0   # px: apuntar cerca de la barra

    def __init__(self, distance, bar_width):
        self.distance = distance
        self.bar_width = bar_width
        self.focals = []

    def add(self, p):
        raw = [r for r in p.raw if r[1] != RAW_ABSENT]
        if len(raw) != 2:
            return
        a, b = (raw[0][0], raw[0][1]), (raw[1][0], raw[1][1])
        mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
        if math.hypot(mx - SENSOR_CENTER[0], my - SENSOR_CENTER[1]) > self.MAX_OFF_CENTER:
            return
        f = solve_focal_px(a, b, expected_separation(self.distance, self.bar_width))
        if f is not None:
            self.focals.append(f)

    def ready(self):
        return len(self.focals) >= self.MIN_SAMPLES

    def result(self):
        if not self.focals:
            return {"verdict": NA, "samples": 0}
        f = median(self.focals)
        fov = fov_from_focal_px(f)
        q = sorted(self.focals)
        lo, hi = q[len(q) // 10], q[(len(q) * 9) // 10]
        spread = fov_from_focal_px(lo) - fov_from_focal_px(hi)
        verdict = OK if spread <= 1.5 else WARN
        return {"verdict": verdict, "fov_h_deg": round(fov, 2), "focal_px": round(f, 1),
                "spread_deg": round(spread, 2), "samples": len(self.focals),
                "distance_m": self.distance, "bar_width_m": self.bar_width}


def combine_fov(results):
    """Media de varias medidas validas del FOV (a distintas distancias)."""
    v = [r["fov_h_deg"] for r in results if r.get("fov_h_deg")]
    if not v:
        return None
    return sum(v) / len(v)


class BarSideCheck(object):
    """
    Paso 5: apuntando al centro de la TV, la barra queda por encima del punto
    apuntado si esta arriba: camera point y > 0 (y < 0 si esta abajo). La barra
    va encima; debajo es un aviso: solo funciona si se alcanza la parte de
    arriba de la pantalla, donde los juegos ponen los targets (una TV pequena).
    """

    MIN_SAMPLES = 30
    MIN_ABS = 0.3

    def __init__(self):
        self.ys = []

    def add(self, p):
        if not p.has(FLAG_CP_VALID) or p.n_dots < 1:
            return
        self.ys.append(p.cp[1])

    def ready(self):
        return len(self.ys) >= self.MIN_SAMPLES

    def result(self):
        if not self.ys:
            return {"verdict": NA}
        y = median(self.ys)
        if abs(y) < self.MIN_ABS:
            measured = None
        else:
            measured = "top" if y > 0 else "bottom"
        if measured is None:
            verdict = WARN
        else:
            verdict = OK if measured == "top" else WARN
        return {"verdict": verdict, "measured": measured, "cp_y": round(y, 3)}


class DisconnectCheck(object):
    """
    Paso 6: el jugador apaga el Wiimote y lo vuelve a encender.
    - stop: los paquetes dejan de llegar (o llegan identicos: la barra repite).
    - back: vuelven a llegar paquetes de ese Wiimote (reconexion automatica).
    """

    GAP = 1.0           # s sin paquetes = apagado
    TIMEOUT = 90.0

    def __init__(self, now):
        self.t0 = now
        self.state = "wait_off"
        self.last_packet_t = now
        self.last_sig = None
        self.same_since = None
        self.max_same = 0.0
        self.off_t = None
        self.back_t = None
        self.stopped = None     # "stopped" | "repeating"

    @staticmethod
    def _sig(p):
        return (p.buttons, tuple(p.raw), p.roll)

    def update(self, packets, now):
        for p in packets:
            sig = self._sig(p)
            if sig == self.last_sig:
                if self.same_since is None:
                    self.same_since = now
                self.max_same = max(self.max_same, now - self.same_since)
            else:
                self.same_since = None
            self.last_sig = sig
        if self.state == "wait_off":
            if packets:
                self.last_packet_t = now
                if self.same_since is not None and now - self.same_since >= 3.0:
                    self.state, self.off_t, self.stopped = "wait_on", now, "repeating"
            elif now - self.last_packet_t >= self.GAP:
                self.state, self.off_t, self.stopped = "wait_on", now, "stopped"
        elif self.state == "wait_on":
            if packets and (self.stopped == "stopped" or self.same_since is None):
                self.state, self.back_t = "done", now
        if self.state != "done" and now - self.t0 >= self.TIMEOUT:
            self.state = "timeout"

    def result(self):
        if self.state == "done":
            return {"verdict": OK, "stopped": self.stopped,
                    "reconnect_s": round(self.back_t - self.off_t, 1)}
        if self.state == "timeout":
            return {"verdict": FAIL if self.off_t else NA, "stopped": self.stopped,
                    "reconnect_s": None}
        return {"verdict": NA, "stopped": self.stopped}


def overall(results):
    """Peor veredicto de los pasos hechos."""
    order = {OK: 0, NA: 0, WARN: 1, FAIL: 2}
    worst = OK
    for r in results.values():
        v = (r or {}).get("verdict", NA)
        if order.get(v, 0) > order[worst]:
            worst = v
    return worst
