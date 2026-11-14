"""
Shooting gallery: targets, error de cada disparo y analisis.

El error se da en pixeles del juego que se simula (preset), y el analisis
dice que tipo de error domina (desplazamiento, escala o pulso).
"""

import math

from dbar4gun.gui.logic.calibration import median


# juego de referencia (320x240): los errores se dan en sus pixeles
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
    ("carnevil", "4:3", 512, 400, "CarnEvil (MAME 2003+)"),  # medido (lr-mame2003-plus, 54 fps)
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


def gallery_targets(area, useful_zone, cols=5, rows=3, margin=0.1):
    """Grid de targets (pantalla completa) dentro del area y de la useful zone."""
    x0, y0, w, h = area
    top, bottom = margin, useful_zone
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
