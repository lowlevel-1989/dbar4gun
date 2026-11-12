import math

import pytest

from dbar4gun.gui import logic as L
from dbar4gun.protocol import Packet

from tests.sim.driver import NewDriver
from tests.sim.gui_harness import SimGun
from tests.sim.scene import Scene, TV


def pk(buttons=0, screen=(0.5, 0.5), vg=1):
    p = Packet()
    p.virtualgun = vg
    p.buttons = buttons
    p.screen = screen
    return p


def test_hub_keeps_last_packet_and_edges():
    hub = L.Hub()
    hub.update([pk(0), pk(L.BTN_A), pk(L.BTN_A, (0.2, 0.3)), pk(0, vg=2)], now=1.0)
    g1 = hub.guns[1]
    assert g1.packet.screen == (0.2, 0.3)
    assert g1.was_pressed(L.BTN_A)
    hub.update([pk(L.BTN_A)], now=1.1)
    assert not g1.was_pressed(L.BTN_A)          # sigue pulsado: sin flanco
    assert hub.first_pressed(L.BTN_A, 1.1) is None
    hub.update([pk(0), pk(L.BTN_A)], now=1.2)
    assert hub.first_pressed(L.BTN_A, 1.2) is g1
    # Wiimote 2 sin paquetes recientes deja de estar activo
    assert [g.virtualgun for g in hub.active(10.0)] == []


def test_samples_before_last_b():
    st = L.WiimoteState(1)
    st.feed([pk(0, (0.1 * i, 0.0)) for i in range(10)] + [pk(L.BTN_B, (9.0, 9.0))], 0)
    s = st.samples_before_last_b(4)
    assert s == [(0.6000000000000001, 0.0), (0.7000000000000001, 0.0), (0.8, 0.0), (0.9, 0.0)]


def test_packet_source_drains_everything():
    import socket
    src = L.PacketSource(0)
    port = src.sock.getsockname()[1]
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for i in range(5):
        p = Packet()
        p.virtualgun = 1
        p.buttons = i
        tx.sendto(p.pack(), ("127.0.0.1", port))
    tx.sendto(b"junk", ("127.0.0.1", port))
    import time
    time.sleep(0.05)
    got = src.drain()
    assert [p.buttons for p in got] == [0, 1, 2, 3, 4]
    assert src.drain() == []
    src.close()
    tx.close()


def last_packet(monkeypatch, scene, aim=(0.5, 0.5), roll=0.0, calibrate=False):
    g = SimGun(monkeypatch, scene)
    if calibrate:
        g.drv.calibrate(scene)
    g.aim, g.roll = aim, roll
    return g.packets(3)[-1], g


@pytest.mark.parametrize("tilt", [0.0, 3.0, -5.0])
@pytest.mark.parametrize("roll", [0.0, 20.0])
def test_bar_tilt(monkeypatch, tilt, roll):
    p, _ = last_packet(monkeypatch, Scene(bar_tilt_deg=tilt), roll=roll)
    assert L.bar_tilt_deg(p) == pytest.approx(tilt, abs=1.5)


def test_distance_and_reference(monkeypatch):
    p, _ = last_packet(monkeypatch, Scene(player=(0, 0, 2.5)), calibrate=True)
    assert L.distance_m(p) == pytest.approx(2.5, abs=0.1)
    assert L.reference_distance_m(p) == pytest.approx(2.5, abs=0.1)


@pytest.mark.parametrize("offset", [(0.0, 0.0), (0.15, 0.0), (-0.1, 0.02)])
def test_bar_position_from_calibration(monkeypatch, offset):
    tv = TV(45)
    scene = Scene(tv=tv, bar_offset=offset)
    _, g = last_packet(monkeypatch, scene, calibrate=True)
    x, y = L.bar_position(g.drv.wm.status())
    assert x == pytest.approx(0.5 + offset[0] / tv.width, abs=0.01)
    bar_y = 0.5 - (tv.height / 2 + 0.03 + offset[1]) / tv.height
    assert y == pytest.approx(bar_y, abs=0.02)


def test_geometry_check_on_real_calibration(monkeypatch):
    _, g = last_packet(monkeypatch, Scene(), calibrate=True)
    ok, ratio = L.geometry_check(g.drv.wm.status()["scale_ratio"], 16.0 / 9.0)
    assert ok and ratio == pytest.approx(16.0 / 9.0, rel=0.05)
    assert not L.geometry_check(1.0, 16.0 / 9.0)[0]
    assert not L.geometry_check(None, 1.0)[0]


def test_adaptive_targets():
    t = L.adaptive_targets((0.0, 0.0, 1.0, 1.0), 0.85)
    assert t == [(0.1, 0.1), (0.9, 0.1), (0.5, 0.85)]
    t = L.adaptive_targets((0.125, 0.0, 0.75, 1.0), 0.85, reach=0.75)
    assert t[0] == pytest.approx((0.2, 0.1)) and t[2] == pytest.approx((0.5, 0.70))
    t = L.adaptive_targets((0.0, 0.0, 1.0, 1.0), 0.85, bar_on_top=False)
    assert t[0] == pytest.approx((0.1, 0.9)) and t[2] == pytest.approx((0.5, 0.15))


def test_verify_error():
    samples = [(0.5, 0.5)] * 5 + [(0.9, 0.9)]
    assert L.verify_error_px(samples, (0.5, 0.5), (1920, 1080)) == 0
    assert L.verify_error_px([(0.51, 0.5)] * 3, (0.5, 0.5), (1920, 1080)) == pytest.approx(19.2)
    assert L.verify_error_px([], (0.5, 0.5), (1920, 1080)) is None


def sweep_reach(monkeypatch, distance):
    tv = TV(45)
    scene = Scene(tv=tv, player=(0, 0, distance))
    g = SimGun(monkeypatch, Scene(tv=tv, player=(0, 0, 3.0)))
    g.drv.calibrate(Scene(tv=tv, player=(0, 0, 3.0)))
    g.scene = scene
    # el jugador se coloca en su sitio antes de barrer (el simulador cambia de
    # distancia de golpe; el tracker tarda 0.5 s en descartar la separacion vieja)
    g.aim = (0.5, 0.2)
    g.packets(60)
    test = L.ReachTest()
    y = 0.0
    p = None
    while y <= 1.2:
        g.aim = (0.5, y)
        for p in g.packets(1):
            test.add(p)
        y += 0.01
    return test, p


def test_reach_and_recommendation(monkeypatch):
    """D11: de cerca no se llega abajo; a la distancia recomendada, si."""
    test, p = sweep_reach(monkeypatch, 1.8)
    reach = test.reach()
    assert 0.3 < reach < 0.85
    factor, d_new = L.recommend_distance(1.8, reach, 0.85)
    assert factor > 1 and d_new > 1.8
    test2, _ = sweep_reach(monkeypatch, d_new)
    assert test2.reach() >= 0.85 - 0.03


def test_reach_far_enough(monkeypatch):
    test, _ = sweep_reach(monkeypatch, 3.0)
    factor, _ = L.recommend_distance(3.0, test.reach(), 0.85)
    assert factor <= 1.0


def test_stability_levels():
    assert L.stability(-1) is None
    assert L.stability(0.01) == "good"
    assert L.stability(0.1) == "ok"
    assert L.stability(0.5) == "bad"


# ---------------------------------------------------------------- D5
def test_gallery_targets_inside_area_and_useful_zone():
    t = L.gallery_targets((0.125, 0.0, 0.75, 1.0), 0.8)
    assert len(t) == 15                     # 5x3: con columna central
    assert all(0.125 < x < 0.875 for x, _ in t)
    assert min(y for _, y in t) == pytest.approx(0.1) and max(y for _, y in t) == pytest.approx(0.8)


def test_shot_error_units():
    tv, game, d = L.shot_error([(0.5 + 0.75 / 320, 0.5)] * 3, (0.5, 0.5), (1920, 1080), (0.125, 0, 0.75, 1))
    assert game == pytest.approx(1.0)
    assert tv == pytest.approx(4.5)
    s = L.summarize([(4.5, 1.0), (9.0, 2.0)])
    assert s["mean_tv"] == 6.75 and s["max_game"] == 2.0


# ---------------------------------------------------------------- D13
def record(monkeypatch, path):
    scene = Scene(tv=TV(45), noise_px=0.5, seed=5)
    g = SimGun(monkeypatch, scene)
    g.drv.calibrate(Scene(tv=TV(45)))
    out = []
    for aim in path:
        g.aim = aim
        out += [p.screen for p in g.packets(1)]
    return out


AREA43 = (0.125, 0.0, 0.75, 1.0)


def test_autotune_still_and_moving(monkeypatch):
    still = record(monkeypatch, [(0.5, 0.5)] * 300)
    assert L.jitter_game(still, AREA43) > 2.0
    fc, jitter = L.choose_fc_min(still, AREA43)
    assert jitter <= L.JITTER_TARGET_GAME and 0.25 <= fc <= 2.0

    path = [(0.5 + 0.3 * math.sin(2 * math.pi * i / 100.0), 0.5) for i in range(300)]
    moving = record(monkeypatch, path)
    assert L.motion_amount(moving, AREA43) > 500
    beta, lag = L.choose_beta(moving, fc, AREA43)
    assert lag <= L.LAG_TARGET_GAME and beta in L.BETA_CANDIDATES


def test_every_gui_text_exists():
    """Cada t("clave") literal del calibrator tiene texto (en ingles)."""
    import os
    import re
    from dbar4gun.gui.i18n import STRINGS
    src = open(os.path.join(os.path.dirname(L.__file__), "app.py")).read()
    # sin los prefijos (t("hw.acc." + v)): se comprueban abajo
    keys = set(k for k in re.findall(r'\bt\("([a-z0-9_.]+)"', src) if not k.endswith((".", "_")))
    assert len(keys) > 50
    missing = sorted(k for k in keys if k not in STRINGS["en"])
    assert not missing, missing
    # las claves que se arman con un prefijo
    for prefix, names in (("hw.step.", ("link", "ir", "acc", "fov", "bar", "disconnect")),
                          ("hw.disconnect.", ("wait_off", "wait_on", "done", "timeout",
                                              "stopped", "repeating")),
                          ("hw.acc.", ("ok", "warn", "fail")),
                          ("hw.bar.", ("ok", "fail", "top", "bottom")),
                          ("hw.link.", ("dolphinbar", "bluetooth", "unknown")),
                          ("hw.note.", ("low_hz", "low_battery", "no_key", "no_bar", "extra_ir",
                                        "weak_left", "weak_right", "dots_drop")),
                          ("hw.ir.sens_", ("higher", "lower"))):
        for n in names:
            assert prefix + n in STRINGS["en"], prefix + n
    for step in ("ir", "acc", "fov", "bar", "disconnect"):
        assert "hw.{}.help".format(step) in STRINGS["en"]
        assert "hw.{}.run".format(step) in STRINGS["en"]


def test_gallery_games_from_the_readme_list():
    presets = L.gallery_presets()
    keys = [p[0] for p in presets]
    assert keys[:2] == ["profile", "full"]
    games = {p[0]: p for p in presets if len(p) > 4}
    assert games["opwolf"][2:4] == (320, 240) and games["timecris"][2:4] == (640, 480)
    assert games["ptblank"][2:4] == (288, 224) and games["hogalley"][2:4] == (256, 240)
    assert all(p[1] == "4:3" for p in games.values())
    assert len(set(keys)) == len(keys)                 # claves unicas (history por juego)


# ----------------------------------------------------------------------
# analisis de la shooting gallery
AREA43 = (0.125, 0.0, 0.75, 1.0)
GAME = (320, 240)


def _synthetic(err_fn):
    """Errores de una rejilla 5x3 con err_fn(ux, uy) -> (dx, dy) en px de juego."""
    targets = L.gallery_targets(AREA43, 0.85)
    cx, cy = 0.5, 0.5
    errors = []
    for tx, ty in targets:
        ux, uy = (tx - cx) / (AREA43[2] / 2), (ty - cy) / (AREA43[3] / 2)
        gx, gy = err_fn(ux, uy)
        d = (gx / GAME[0] * AREA43[2], gy / GAME[1] * AREA43[3])
        errors.append((0.0, (gx ** 2 + gy ** 2) ** 0.5, d))
    return targets, errors


def test_gallery_analysis_good():
    t, e = _synthetic(lambda ux, uy: (0.5, -0.4))
    a = L.gallery_analysis(t, e, AREA43, GAME)
    assert a["kind"] == "good"


def test_gallery_analysis_offset():
    """Todo desplazado 6 px a la derecha: la calibracion esta corrida."""
    t, e = _synthetic(lambda ux, uy: (6.0, 0.0))
    a = L.gallery_analysis(t, e, AREA43, GAME)
    assert a["kind"] == "offset" and abs(a["offset"][0] - 6.0) < 0.01
    # el mismo error en todas partes: los anillos casi iguales
    assert abs(a["rings"]["center"] - a["rings"]["edge"]) < 0.5


def test_gallery_analysis_scale_grows_with_distance():
    """El gun llega un 5 % mas lejos que la pantalla: bien en el centro, mal en los bordes."""
    t, e = _synthetic(lambda ux, uy: (0.05 * 160 * ux, 0.05 * 120 * uy))
    a = L.gallery_analysis(t, e, AREA43, GAME)
    assert a["kind"] == "scale"
    assert abs(a["scale"][0] - 5.0) < 0.2 and abs(a["scale"][1] - 5.0) < 0.2
    assert a["rings"]["center"] < a["rings"]["middle"] < a["rings"]["edge"]


def test_gallery_analysis_random():
    """
    Punteria irregular (5 px de juego) sin error de calibracion: casi nunca
    debe inventar un desplazamiento o una escala (umbral de 3 errores tipicos).
    """
    import random
    kinds = {}
    for seed in range(300):
        rng = random.Random(seed)
        t, e = _synthetic(lambda ux, uy: (rng.gauss(0, 5), rng.gauss(0, 5)))
        k = L.gallery_analysis(t, e, AREA43, GAME)["kind"]
        kinds[k] = kinds.get(k, 0) + 1
    assert kinds.get("random", 0) >= 0.93 * 300, kinds


def test_gallery_analysis_finds_calibration_errors_despite_aim():
    """Con punteria irregular (3 px), un desplazamiento de 6 px y una escala del 8 % se ven."""
    import random
    for seed in range(50):
        rng = random.Random(seed)
        t, e = _synthetic(lambda ux, uy: (6 + rng.gauss(0, 3), rng.gauss(0, 3)))
        assert L.gallery_analysis(t, e, AREA43, GAME)["kind"] == "offset"
        t, e = _synthetic(lambda ux, uy: (0.08 * 160 * ux + rng.gauss(0, 3), 0.08 * 120 * uy + rng.gauss(0, 3)))
        assert L.gallery_analysis(t, e, AREA43, GAME)["kind"] == "scale"


def test_gallery_analysis_corners():
    """Solo fallan las esquinas (un mapa de 3 puntos con el jugador descentrado)."""
    t, e = _synthetic(lambda ux, uy: (8.0, 6.0) if abs(ux) > 0.5 and abs(uy) > 0.5 else (0.5, 0.0))
    a = L.gallery_analysis(t, e, AREA43, GAME)
    assert a["corners"] is True


def test_gallery_order_mixes_and_repeats():
    import random
    order = L.gallery_order(15, 3, random.Random(1))
    assert len(order) == 45 and all(order.count(i) == 3 for i in range(15))
    assert all(a != b for a, b in zip(order, order[1:]))          # nunca dos seguidos
    assert order[:15] != list(range(15))                           # mezclado


def test_aggregate_shots_averages_aim_and_measures_it():
    """Dos disparos por target, +-3 px alrededor de un error de 1 px: media 1 px, punteria 3 px."""
    area, game, size = AREA43, GAME, (1920, 1080)
    targets = L.gallery_targets(area, 0.85)
    shots = []
    for i in range(len(targets)):
        for jit in (3.0, -3.0):
            gx = 1.0 + jit
            shots.append((i, (0.0, abs(gx), (gx / game[0] * area[2], 0.0))))
    errors, aim = L.aggregate_shots(shots, len(targets), size, area, game)
    assert all(abs(e[1] - 1.0) < 1e-6 for e in errors)
    assert abs(aim - 3.0 * 2 ** 0.5) < 1e-6       # 2 disparos: (3^2 + 3^2) / 1 grado de libertad
    errors, aim = L.aggregate_shots([(i, e) for i, e in shots[::2]], len(targets), size, area, game)
    assert aim is None                             # un disparo por target: no se puede medir


def test_gallery_stop_rule():
    assert not L.gallery_done(0.5, 1)              # una vuelta nunca basta
    assert L.gallery_done(1.0, 2)                  # buen pulso: 2 vueltas
    assert not L.gallery_done(4.0, 2)              # pulso irregular: otra vuelta
    assert L.gallery_done(9.0, 3)                  # como mucho 3
    assert abs(L.gallery_margin(3.0, 3) - 3.0 / 3 ** 0.5) < 1e-9
    import random
    rng = random.Random(1)
    area = (0.125, 0.0, 0.75, 1.0)
    for _ in range(100):
        x, y = L.jitter_target((0.5, 0.5), area, rng)
        assert abs(x - 0.5) <= L.TARGET_JITTER * 0.75 + 1e-9 and abs(y - 0.5) <= L.TARGET_JITTER + 1e-9
