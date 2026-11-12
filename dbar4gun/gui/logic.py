"""
Logica del calibrator, sin pygame (testeable con el simulador).

- PacketSource vacia el socket en cada frame y se queda con el ultimo
  paquete de cada VirtualGun; WiimoteState guarda el estado por Wiimote.
- distancia, nivel y centrado de la barra.
- reach test y distancia recomendada.
- targets adaptativos, comprobacion de geometria y verificacion.
- Autodiagnostico de hardware (enlace, calidad IR, acelerometro, FOV,
  barra y desconexion).
"""

import math
import socket

from dbar4gun.core.calibration import MAX_SPREAD_SEP
from dbar4gun.core.hardware import HardwareConfig, fov_from_focal_px
from dbar4gun.core.pointer import FOCAL
from dbar4gun.protocol import (
    Packet, SIZE, FLAG_BAR_ON_TOP, FLAG_CP_VALID, DOT_VALID, DOT_RECONSTRUCTED, RAW_ABSENT,
)

# botones (mismos bits que el Wiimote)
BTN_TWO = 1 << 0x0
BTN_ONE = 1 << 0x1
BTN_B = 1 << 0x2
BTN_A = 1 << 0x3
BTN_MINUS = 1 << 0x4
BTN_HOME = 1 << 0x7
BTN_LEFT = 1 << 0x8
BTN_RIGHT = 1 << 0x9
BTN_DOWN = 1 << 0xa
BTN_UP = 1 << 0xb
BTN_PLUS = 1 << 0xc

HISTORY = 64


class PacketSource(object):
    """Socket UDP no bloqueante; drain() devuelve todos los paquetes pendientes."""

    def __init__(self, port, host="127.0.0.1"):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.setblocking(False)

    def drain(self, limit=2000):
        out = []
        for _ in range(limit):
            try:
                data = self.sock.recv(SIZE + 16)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            p = Packet.unpack(data)
            if p is not None:
                out.append(p)
        return out

    def close(self):
        self.sock.close()


class WiimoteState(object):
    """Estado de un Wiimote en la GUI: ultimo paquete, history y flancos."""

    def __init__(self, virtualgun):
        self.virtualgun = virtualgun
        self.packet = None
        self.history = []
        self.prev_buttons = 0
        self.pressed = 0
        self.last_seen = 0.0
        self.frame_packets = []
        self.reach = None   # resultado de la reach test (fraccion de alto)
        self.status = {}    # ultimo status del socket de control

    def feed(self, packets, now):
        """Paquetes de este Wiimote recibidos en el frame (en orden)."""
        pressed = 0
        prev = self.prev_buttons
        for p in packets:
            pressed |= p.buttons & ~prev
            prev = p.buttons
            self.history.append(p)
        if len(self.history) > HISTORY:
            del self.history[:len(self.history) - HISTORY]
        self.frame_packets = packets
        if packets:
            self.packet = packets[-1]
            self.last_seen = now
        self.prev_buttons = prev
        self.pressed = pressed

    def was_pressed(self, mask):
        return bool(self.pressed & mask)

    def samples_before_last_b(self, n=8):
        """Cursores en pantalla de los n paquetes anteriores al ultimo flanco de B."""
        hist = self.history
        edge = None
        for i in range(len(hist) - 1, 0, -1):
            if hist[i].buttons & BTN_B and not hist[i - 1].buttons & BTN_B:
                edge = i
                break
        if edge is None:
            return []
        return [p.screen for p in hist[max(0, edge - n):edge]]


class Hub(object):
    """Todos los Wiimotes vistos y el reparto de paquetes por frame."""

    TIMEOUT = 2.0

    def __init__(self):
        self.guns = {}

    def update(self, packets, now):
        by_gun = {}
        for p in packets:
            by_gun.setdefault(p.virtualgun, []).append(p)
        for vg, plist in by_gun.items():
            if vg not in self.guns:
                self.guns[vg] = WiimoteState(vg)
        for vg, state in self.guns.items():
            state.feed(by_gun.get(vg, []), now)

    def active(self, now):
        return [s for vg, s in sorted(self.guns.items())
                if s.packet is not None and now - s.last_seen <= self.TIMEOUT]

    def first_pressed(self, mask, now):
        for s in self.active(now):
            if s.was_pressed(mask):
                return s
        return None

    def any_pressed(self, mask, now):
        return self.first_pressed(mask, now) is not None


# ----------------------------------------------------------------------
# instalacion
def distance_m(packet, hw=None):
    """Distancia a la barra; con `hw` usa el FOV y el ancho medidos."""
    if packet is None or packet.separation <= 0:
        return None
    return (hw or HardwareConfig()).distance(packet.separation, FOCAL)


def reference_distance_m(packet, hw=None):
    if packet is None or packet.sep_ref <= 0:
        return None
    return (hw or HardwareConfig()).distance(packet.sep_ref, FOCAL)


def bar_tilt_deg(packet):
    """
    Inclinacion de la barra respecto al suelo (grados, positivo = lado derecho
    mas alto): el angulo de los dots corregido con el roll del acelerometro.
    Con la barra nivelada, angulo = -roll; el TL del espacio normalizado es el
    LED derecho (x invertida), asi que una barra inclinada da angulo = -tilt.
    """
    if packet is None or math.isnan(packet.roll) or packet.n_dots < 2:
        return None
    t = -(packet.angle + packet.roll)
    return (t + 180.0) % 360.0 - 180.0


def bar_position(status):
    """
    Posicion de la barra en la TV segun la calibracion (status del socket de control): el
    camera point (0, 0) es apuntar justo a la barra. (x, y) normalizados.
    """
    pos = (status or {}).get("bar_position")
    return tuple(pos) if pos else None


# ----------------------------------------------------------------------
# alcance
class ReachTest(object):
    """Rastro de la reach test: (x, y, dots) en pantalla."""

    def __init__(self, bar_on_top=True):
        self.bar_on_top = bar_on_top
        self.trail = []

    def add(self, packet):
        x, y = packet.screen
        self.trail.append((x, y, min(packet.n_dots, 2)))

    def reach(self):
        """
        Fraccion del alto de la pantalla que se alcanza con los 2 dots, medida
        desde el lado de la barra. None si no hay datos.
        """
        ys = [y for x, y, n in self.trail if n >= 2 and -0.2 <= y <= 1.2]
        if not ys:
            return None
        if self.bar_on_top:
            return max(0.0, min(1.0, max(ys)))
        return max(0.0, min(1.0, 1.0 - min(ys)))


def recommend_distance(distance, reach, useful_zone):
    """
    factor = useful_zone / reach; D_nueva = D * factor. Devuelve
    (factor, distancia nueva o None).
    """
    if not reach or reach <= 0:
        return None, None
    factor = useful_zone / reach
    return factor, (distance * factor if distance else None)


# ----------------------------------------------------------------------
# wizard
TOP_TARGET = 0.10
REACH_MARGIN = 0.05


def adaptive_targets(area, useful_zone, reach=None, bar_on_top=True, points=3):
    """
    Targets de 3 puntos en pantalla completa: los del lado de la barra al 10%
    del alto y el opuesto en min(useful zone, alcance - margen).
    area: (x0, y0, w, h).
    """
    x0, y0, w, h = area
    far = useful_zone
    if reach is not None:
        far = min(far, reach - REACH_MARGIN)
    far = max(far, 0.5)
    left = x0 + 0.1 * w
    right = x0 + 0.9 * w
    center = x0 + 0.5 * w
    if bar_on_top:
        near_y = y0 + TOP_TARGET * h
        far_y = y0 + far * h
    else:
        near_y = y0 + (1.0 - TOP_TARGET) * h
        far_y = y0 + (1.0 - far) * h
    if points == 4:
        # esquinas TL, TR, BR, BL (lado de la barra primero)
        return [(left, near_y), (right, near_y), (right, far_y), (left, far_y)]
    return [(left, near_y), (right, near_y), (center, far_y)]


def geometry_check(ratio, screen_aspect, tol=0.10):
    """
    e/a (escala vertical / horizontal del mapa, `scale_ratio` del status)
    debe parecerse al aspecto de la TV: 1 unidad de camera point es igual en
    x e y, y la pantalla mide aspecto veces mas en x. Devuelve (ok, ratio).
    """
    if not ratio or ratio <= 0:
        return False, None
    return abs(ratio / screen_aspect - 1.0) <= tol, ratio


def median(values):
    v = sorted(values)
    n = len(v)
    if not n:
        return None
    m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) * 0.5


def verify_error_px(samples, target, size):
    """Error (px de TV) de la mediana de las muestras respecto al target."""
    if not samples:
        return None
    mx = median([s[0] for s in samples])
    my = median([s[1] for s in samples])
    dx = (mx - target[0]) * size[0]
    dy = (my - target[1]) * size[1]
    return math.sqrt(dx * dx + dy * dy)


VERIFY_MAX_PX = 20.0


def stability(spread):
    """'good' / 'ok' / 'bad' / None segun la dispersion (separaciones de barra)."""
    if spread is None or spread < 0:
        return None
    if spread <= MAX_SPREAD_SEP * 0.5:
        return "good"
    if spread <= MAX_SPREAD_SEP:
        return "ok"
    return "bad"


def bar_on_top(packet):
    return packet is None or packet.has(FLAG_BAR_ON_TOP)


# ----------------------------------------------------------------------
# shooting gallery
GAME_W = 320
GAME_H = 240

# que simula la galeria: (clave, area, ancho, alto). area None = el area profile
# del servicio; ancho/alto None = px de la TV (juegos a pantalla completa).
# La clave se guarda con el resultado en el history.
GALLERY_PRESETS = [
    ("profile", None, GAME_W, GAME_H),
    ("full", "full", None, None),
    ("4:3-320x240", "4:3", 320, 240),
    ("4:3-256x240", "4:3", 256, 240),
    ("4:3-288x224", "4:3", 288, 224),
    ("4:3-640x480", "4:3", 640, 480),
]


# juegos de la lista del README: (clave = ROM set, area, ancho, alto, nombre).
# Todos se ven en un monitor 4:3. La resolucion sale del codigo fuente de MAME
# (set_raw / set_visarea) o, en las placas basadas en PlayStation (la elige el
# juego en marcha), de medirla con lr-mame en RetroArch: los cambios de
# geometria que el core avisa (SET_GEOMETRY) durante el modo demo.
GALLERY_GAMES = [
    ("opwolf", "4:3", 320, 240, "Operation Wolf"),          # taito/opwolf.cpp
    ("ptblank", "4:3", 288, 224, "Point Blank"),            # namco/namconb1.cpp
    ("timecris", "4:3", 640, 480, "Time Crisis"),           # namco/namcos22.cpp
    ("gollygho", "4:3", 288, 224, "Golly! Ghost!"),         # namco/namcos2.cpp
    ("hogalley", "4:3", 256, 240, "VS. Hogan's Alley"),     # nintendo/vsnes.cpp
    ("luckywld", "4:3", 288, 224, "Lucky & Wild"),          # namco/namcos2.cpp (y MAME 2015)
    ("area51", "4:3", 320, 240, "Area 51 (MAME 2003+)"),    # drivers/cojag.c de mame2003-plus
    ("ptblank2", "4:3", 320, 240, "Point Blank 2"),         # medido (lr-mame, demo)
    ("ptblank3", "4:3", 320, 240, "Point Blank 3"),         # medido (lr-mame, demo)
    ("ghlpanic", "4:3", 512, 480, "Ghoul Panic"),           # medido (lr-mame, demo)
    # Dreamcast: la geometria que anuncia lr-flycast al cargar (640x480, 4:3);
    # sin GPU no se puede ver el juego en marcha
    ("hotd2", "4:3", 640, 480, "House of the Dead 2"),
    ("vcop2", "4:3", 640, 480, "Virtua Cop 2"),
]


def gallery_presets():
    return list(GALLERY_PRESETS) + list(GALLERY_GAMES)


def preset_area(preset, current_area, screen_aspect):
    """(x0, y0, w, h) del preset sobre la TV."""
    if preset[1] is None:
        return tuple(current_area)
    from dbar4gun.core.area import AreaProfile
    a = AreaProfile.parse(preset[1], screen_aspect)
    return (a.x0, a.y0, a.w, a.h)


def preset_game_size(preset, screen_size):
    """(ancho, alto) del juego simulado; sin resolucion propia, la TV."""
    if preset[2] is None:
        return screen_size
    return preset[2], preset[3]


def gallery_targets(area, useful_zone, cols=5, rows=3, margin=0.1, bar_on_top=True):
    """Grid de targets (pantalla completa) dentro del area y de la useful zone."""
    x0, y0, w, h = area
    top, bottom = (margin, useful_zone) if bar_on_top else (1.0 - useful_zone, 1.0 - margin)
    out = []
    for j in range(rows):
        fy = top + (bottom - top) * (j / float(rows - 1) if rows > 1 else 0.5)
        for i in range(cols):
            fx = margin + (1.0 - 2 * margin) * (i / float(cols - 1) if cols > 1 else 0.5)
            out.append((x0 + fx * w, y0 + fy * h))
    return out


def shot_error(samples, target, size, area, game=(GAME_W, GAME_H)):
    """
    Error de un disparo: (px de TV, px de juego, (dx, dy) normalizado).
    Juego de `game` px (por defecto 320x240) estirado sobre el area.
    """
    if not samples:
        return None
    mx = median([s[0] for s in samples])
    my = median([s[1] for s in samples])
    dx, dy = mx - target[0], my - target[1]
    tv = math.sqrt((dx * size[0]) ** 2 + (dy * size[1]) ** 2)
    game = math.sqrt((dx / area[2] * game[0]) ** 2 + (dy / area[3] * game[1]) ** 2)
    return tv, game, (dx, dy)


# un disparo con la mira moviendose no mide la calibracion sino el tiron al
# apretar el gatillo: si las posiciones antes del disparo se separan mas que
# esto (fraccion de la TV), se repite (como la captura de la calibracion)
MAX_SHOT_SPREAD = 0.03


def shot_spread(samples):
    """Distancia maxima (fraccion de la TV) de las muestras a su mediana."""
    if not samples:
        return None
    mx = median([s[0] for s in samples])
    my = median([s[1] for s in samples])
    return max(math.sqrt((s[0] - mx) ** 2 + (s[1] - my) ** 2) for s in samples)


# la galeria dispara por vueltas: en cada una salen todos los targets, en otro
# orden y un poco movidos (que no se note que se repiten). La media de los
# disparos a cada target reduce el error de punteria y su dispersion lo mide.
# Despues de cada vuelta se calcula el margen de la estimacion (punteria /
# raiz de los disparos por target) y se para si ya es pequeno, como mucho tras
# MAX_ROUNDS vueltas (mas disparos cansan y empeoran la punteria).
MAX_ROUNDS = 3
# con una sola vuelta (un disparo por target) la punteria no se puede separar
# del error no lineal de la calibracion (medido con punteria perfecta: 1.7 px
# de juego a 320x240, 3.4 a 640x480): como minimo 2 vueltas
MIN_ROUNDS = 2
MARGIN_OK = 1.5          # px de juego
TARGET_JITTER = 0.04     # fraccion del area: cuanto se mueve cada target


def jitter_target(base, area, rng):
    """El target `base` movido al azar como mucho TARGET_JITTER del area."""
    return (base[0] + rng.uniform(-TARGET_JITTER, TARGET_JITTER) * area[2],
            base[1] + rng.uniform(-TARGET_JITTER, TARGET_JITTER) * area[3])


# color de cada target del mapa: juzga la calibracion, no el pulso. Un target
# esta bien si su error cabe en lo que explica la punteria (2 veces el margen
# de su media) y mal si pasa de 3 veces; con pulso perfecto, 2 y 5 px de juego
TARGET_GOOD_PX = 2.0
TARGET_OK_PX = 5.0


def target_level(error_game, margin):
    """'good', 'ok' o 'bad' para el error medio de un target (px de juego)."""
    m = margin or 0.0
    if error_game <= max(TARGET_GOOD_PX, 2.0 * m):
        return "good"
    if error_game <= max(TARGET_OK_PX, 3.0 * m):
        return "ok"
    return "bad"


def gallery_margin(aim, rounds):
    """Margen (px de juego) de la media de cada target tras `rounds` vueltas."""
    if aim is None or rounds <= 0:
        return None
    return aim / math.sqrt(rounds)


def gallery_done(aim, rounds):
    """True si con esa punteria y esas vueltas el resultado ya es fiable."""
    if rounds >= MAX_ROUNDS:
        return True
    if rounds < MIN_ROUNDS:
        return False
    margin = gallery_margin(aim, rounds)
    return margin is not None and margin <= MARGIN_OK


def gallery_order(n, repeats, rng=None):
    """
    Orden de los disparos: cada uno de los n targets `repeats` veces, en rondas
    mezcladas y sin el mismo target dos veces seguidas.
    """
    import random
    rng = rng or random.Random()
    order = []
    for _ in range(max(1, repeats)):
        block = list(range(n))
        rng.shuffle(block)
        if order and n > 1 and block[0] == order[-1]:
            block[0], block[1] = block[1], block[0]
        order.extend(block)
    return order


def aggregate_shots(shots, n, size, area, game):
    """
    shots: [(indice del target, (tv, px de juego, (dx, dy)))]. Devuelve los
    errores medios por target (en el formato de shot_error) y la dispersion de
    la punteria: cuanto se separan los disparos al mismo target de su media (px
    de juego), o None con un disparo por target.
    """
    by = {}
    for i, e in shots:
        by.setdefault(i, []).append(e[2])
    errors = []
    dev2, dof = 0.0, 0
    gx, gy = game[0] / float(area[2]), game[1] / float(area[3])
    for i in range(n):
        ds = by.get(i)
        if not ds:
            errors.append(None)
            continue
        mx = sum(d[0] for d in ds) / len(ds)
        my = sum(d[1] for d in ds) / len(ds)
        tv = math.sqrt((mx * size[0]) ** 2 + (my * size[1]) ** 2)
        errors.append((tv, math.sqrt((mx * gx) ** 2 + (my * gy) ** 2), (mx, my)))
        for d in ds:
            dev2 += ((d[0] - mx) * gx) ** 2 + ((d[1] - my) * gy) ** 2
        dof += len(ds) - 1
    aim = math.sqrt(dev2 / dof) if dof > 0 else None
    return errors, aim


def summarize(errors):
    """errors: lista de (tv, game, ...) -> dict para mostrar y guardar."""
    errors = [e for e in errors if e is not None]
    tv = [e[0] for e in errors]
    game = [e[1] for e in errors]
    return {"mean_tv": sum(tv) / len(tv), "max_tv": max(tv),
            "mean_game": sum(game) / len(game), "max_game": max(game)}


# ----------------------------------------------------------------------
# Analisis de la shooting gallery: error segun la distancia al centro y que
# tipo de error domina (desplazamiento, escala o pulso)
RING_NAMES = ("center", "middle", "edge")
# por debajo de esto (px de juego) el error no merece consejo
GALLERY_GOOD = 2.0
# un desplazamiento o una escala cuentan si superan 3 veces su error tipico
# (con 15 disparos de punteria irregular, ~4 % de falsos patrones; con 2.5, ~9 %)
SIGNIFICANCE = 3.0


def _area_center(area):
    return area[0] + area[2] / 2.0, area[1] + area[3] / 2.0


def gallery_analysis(targets, errors, area, game):
    """
    targets: [(x, y)] normalizados a la TV; errors: [(tv, game_px, (dx, dy))].
    Devuelve un dict con:
    - rings: error medio (px de juego) en el centro, la zona media y los bordes,
      segun la distancia de cada target al centro del area;
    - offset: desplazamiento comun (px de juego, x/y);
    - scale: error de escala (%, x/y): + el gun llega mas lejos que la pantalla;
    - residual: lo que queda (px de juego, pulso o ruido);
    - kind: "good", "offset", "scale" o "random"; corners: True si las esquinas
      fallan bastante mas que el resto.
    """
    cx, cy = _area_center(area)
    gx, gy = game[0] / float(area[2]), game[1] / float(area[3])
    pts = []
    for (tx, ty), e in zip(targets, errors):
        if e is None:
            continue
        ux, uy = (tx - cx) / (area[2] / 2.0), (ty - cy) / (area[3] / 2.0)   # -1..1
        pts.append((ux, uy, e[2][0] * gx, e[2][1] * gy, e[1]))
    if not pts:
        return None

    # anillos por distancia (normalizada, 0 = centro, ~1.27 = esquina)
    rings = {}
    for name, lo, hi in (("center", 0.0, 0.35), ("middle", 0.35, 0.85), ("edge", 0.85, 9.0)):
        v = [p[4] for p in pts if lo <= (p[0] ** 2 + p[1] ** 2) ** 0.5 < hi]
        rings[name] = sum(v) / len(v) if v else None

    # d = offset + k * u en cada eje (minimos cuadrados)
    def fit(us, ds):
        """d = off + k * u; devuelve off, k, residuos y sus errores tipicos."""
        n = len(us)
        mu, md = sum(us) / n, sum(ds) / n
        sxx = sum((u - mu) ** 2 for u in us)
        k = sum((u - mu) * (d - md) for u, d in zip(us, ds)) / sxx if sxx > 1e-9 else 0.0
        off = md - k * mu
        res = [d - off - k * u for u, d in zip(us, ds)]
        sigma = math.sqrt(sum(r * r for r in res) / max(1, n - 2))
        se_k = sigma / math.sqrt(sxx) if sxx > 1e-9 else float("inf")
        se_off = sigma * math.sqrt(1.0 / n + (mu * mu / sxx if sxx > 1e-9 else 0.0))
        return off, k, res, se_off, se_k
    ox, kx, rx, se_ox, se_kx = fit([p[0] for p in pts], [p[2] for p in pts])
    oy, ky, ry, se_oy, se_ky = fit([p[1] for p in pts], [p[3] for p in pts])
    # la puntería de una persona es irregular: un desplazamiento o una escala
    # solo cuentan si son claramente mayores que la dispersion de sus disparos
    def significant(v, se):
        return abs(v) > SIGNIFICANCE * se
    offset_sig = significant(ox, se_ox) or significant(oy, se_oy)
    scale_sig = significant(kx, se_kx) or significant(ky, se_ky)
    residual = (sum(a * a + b * b for a, b in zip(rx, ry)) / len(pts)) ** 0.5
    offset = (ox ** 2 + oy ** 2) ** 0.5
    # k en px de juego por media pantalla -> % del tamano del juego
    scale_x = 100.0 * kx / (game[0] / 2.0)
    scale_y = 100.0 * ky / (game[1] / 2.0)
    scale_px = max(abs(kx), abs(ky))

    mean = sum(p[4] for p in pts) / len(pts)
    corners = [p[4] for p in pts if abs(p[0]) > 0.5 and abs(p[1]) > 0.5]
    others = [p[4] for p in pts if not (abs(p[0]) > 0.5 and abs(p[1]) > 0.5)]
    corners_bad = bool(corners and others and
                       sum(corners) / len(corners) > 1.8 * (sum(others) / len(others)) + 1.0)

    parts = {"offset": offset if offset_sig else 0.0,
             "scale": scale_px if scale_sig else 0.0,
             "random": residual}
    if mean <= GALLERY_GOOD:
        kind, also = "good", []
    else:
        systematic = {k: v for k, v in parts.items() if k != "random" and v > GALLERY_GOOD}
        # sin un patron claro, lo que queda es la punteria (o ruido del IR)
        kind = max(systematic, key=systematic.get) if systematic else "random"
        # otros errores que tambien pesan (p. ej. acercarse sin distance
        # compensation da escala y desplazamiento a la vez)
        also = [k for k in ("offset", "scale", "random")
                if k != kind and parts[k] > GALLERY_GOOD and parts[k] >= 0.5 * parts[kind]]
    return {"rings": rings, "offset": (round(ox, 2), round(oy, 2)),
            "scale": (round(scale_x, 1), round(scale_y, 1)), "residual": round(residual, 2),
            "mean": round(mean, 2), "kind": kind, "also": also, "corners": corners_bad}


# ----------------------------------------------------------------------
# auto-tune del One Euro
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


# ----------------------------------------------------------------------
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
    apuntado si esta arriba: camera point y > 0 (y < 0 si esta abajo). Se
    compara con la opcion --bar del servicio (flag del paquete).
    """

    MIN_SAMPLES = 30
    MIN_ABS = 0.3

    def __init__(self):
        self.ys = []
        self.configured_top = None

    def add(self, p):
        if not p.has(FLAG_CP_VALID) or p.n_dots < 1:
            return
        self.ys.append(p.cp[1])
        self.configured_top = p.has(FLAG_BAR_ON_TOP)

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
        configured = "top" if self.configured_top else "bottom"
        if measured is None:
            verdict = WARN
        else:
            verdict = OK if measured == configured else FAIL
        return {"verdict": verdict, "measured": measured, "configured": configured,
                "cp_y": round(y, 3)}


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
