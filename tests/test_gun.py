import pytest

from dbar4gun.core.calibration import CalibrationData, MODE_2PT, MODE_DISABLED, MODE_3PT, AffineMap
from dbar4gun.core.gun import (
    GunOptions, GunPipeline, BUTTON_A, BUTTON_B, BUTTON_PLUS, BUTTON_MINUS, BUTTON_HOME,
    LED_1, LED_2, LED_3, LED_4, edge_point, LOST_HOLD, parse_targets,
)
from dbar4gun.core.parser import parse_ir_basic

from tests.sim.driver import NewDriver
from tests.sim.metrics import error_tv_px
from tests.sim.scene import Scene, TV


class Clock(object):
    def __init__(self):
        self.t = 0.0

    def tick(self, dt=0.01):
        self.t += dt
        return self.t


def frame(p, scene, sx, sy, buttons=0, clock=None, drop=(), roll=0.0):
    rep = scene.report(sx, sy, roll, drop=drop)
    t = clock.tick() if clock else 0.0
    return p.process(parse_ir_basic(rep[6:16]), tuple(rep[3:6]), buttons, t)


def calibrate(p, scene, clock, start_buttons=BUTTON_A | BUTTON_PLUS):
    frame(p, scene, 0.5, 0.5, start_buttons, clock)
    frame(p, scene, 0.5, 0.5, 0, clock)
    guard = 0
    while p.calibrating:
        guard += 1
        assert guard < 10, "la calibracion no termina"
        sx, sy = p.session.targets[p.session.step]
        for _ in range(8):
            cursor, _ = frame(p, scene, sx, sy, 0, clock)
            # durante la calibracion el cursor marca el target
            assert cursor == p.session.targets_out[p.session.step]
        frame(p, scene, sx, sy, BUTTON_B, clock)
        frame(p, scene, sx, sy, 0, clock)


def test_a_plus_runs_3pt_and_saves():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    assert p.default_kind() == "3pt"
    calibrate(p, scene, clock)
    actions = p.drain_actions()
    kinds = [a[0] for a in actions]
    assert ("leds", LED_1) in actions and ("leds", LED_4) in actions
    assert ("leds", LED_2 | LED_3) in actions
    assert kinds.count("rumble") == 3
    assert kinds[-3:] == ["rumble", "restore_leds", "save"]
    data = actions[-1][1]
    assert data.calibrated and data.mode == MODE_3PT and data.sep_ref > 0
    # despues de calibrar, A+plus hace la recalibracion rapida (C19)
    assert p.default_kind() == "quick"


def test_buttons_masked_during_calibration():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    frame(p, scene, 0.5, 0.5, BUTTON_A | BUTTON_PLUS, clock)
    _, out = frame(p, scene, 0.5, 0.5, BUTTON_B | BUTTON_HOME | BUTTON_A, clock)
    assert out == BUTTON_HOME


def test_unstable_capture_gives_error_and_repeats_step():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    frame(p, scene, 0.5, 0.5, BUTTON_A | BUTTON_PLUS, clock)
    frame(p, scene, 0.5, 0.5, 0, clock)
    p.drain_actions()
    for i in range(8):
        frame(p, scene, 0.1 + 0.15 * (i % 2), 0.1, 0, clock)
    frame(p, scene, 0.1, 0.1, BUTTON_B, clock)
    actions = p.drain_actions()
    assert ("rumble", "error") in actions
    assert ("calibration_error", "unstable") in actions
    assert p.session.step == 0


def test_no_ir_capture_error():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    frame(p, scene, 0.5, 0.5, BUTTON_A | BUTTON_PLUS, clock)
    frame(p, scene, 0.5, 0.5, 0, clock)
    frame(p, scene, 0.1, 0.1, BUTTON_B, clock, drop=(0, 1))
    assert ("calibration_error", "no_ir") in p.drain_actions()


@pytest.mark.parametrize("bar_offset", [(0.10, 0.0), (0.0, 0.03), (-0.08, 0.02)])
def test_quick_recalibration_after_bar_moved(monkeypatch, bar_offset):
    """C19: la barra se ha movido; A+plus (2 puntos) recupera la precision."""
    from tests.sim.metrics import measure_grid

    tv = TV(45)
    drv = NewDriver(monkeypatch)
    drv.calibrate(Scene(tv=tv))
    moved = Scene(tv=tv, bar_offset=bar_offset)
    before = measure_grid(moved, drv.feed)
    drv.calibrate(moved)        # A+plus con calibracion -> quick
    assert drv.saved[-1].mode == MODE_3PT
    after = measure_grid(moved, drv.feed)
    assert before.mean_tv > 40
    assert after.mean_tv <= 12, after


def test_quick_recalibration_without_distance_compensation(monkeypatch):
    """Sin compensacion de distancia, la quick corrige el cambio de escala."""
    from tests.sim.metrics import measure_grid

    tv = TV(45)
    drv = NewDriver(monkeypatch, GunOptions(distance_compensation=False, smoothing_level=0))
    drv.calibrate(Scene(tv=tv))
    closer = Scene(tv=tv, player=(0.0, 0.0, 2.6))
    before = measure_grid(closer, drv.feed)
    drv.calibrate(closer)
    after = measure_grid(closer, drv.feed)
    assert after.mean_tv < before.mean_tv * 0.6


def test_quick_with_bar_bottom_uses_bottom_corners():
    p = GunPipeline(GunOptions(smoothing_level=0, bar_on_top=False, useful_zone=0.8))
    assert p.calibration_targets("quick") == [(0.1, 0.8), (0.9, 0.8)]
    assert p.calibration_targets("3pt") == [(0.1, 0.1), (0.9, 0.1), (0.5, 0.8)]


def test_mode_1_two_points():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0, calibration_mode=MODE_2PT))
    calibrate(p, scene, clock)
    data = p.drain_actions()[-1][1]
    assert data.mode == MODE_2PT and data.affine.b == 0 and data.affine.c == 0
    cursor, _ = frame(p, scene, 0.5, 0.5, 0, clock)
    assert error_tv_px(cursor, (0.5, 0.5)) < 5


def test_mode_0_disabled():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0, calibration_mode=MODE_DISABLED))
    frame(p, scene, 0.5, 0.5, BUTTON_A | BUTTON_PLUS, clock)
    assert not p.calibrating


def test_nominal_map_is_usable_without_calibration():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    for pt in [(0.2, 0.2), (0.5, 0.5), (0.8, 0.7)]:
        cursor, _ = frame(p, scene, pt[0], pt[1], 0, clock)
        assert error_tv_px(cursor, pt) < 60


def test_a_minus_resets_to_nominal():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    calibrate(p, scene, clock)
    frame(p, scene, 0.5, 0.5, BUTTON_A | BUTTON_MINUS, clock)
    assert not p.calibration.calibrated
    assert p.default_kind() == "3pt"


def test_fake_cursor_toggle():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    frame(p, scene, 0.5, 0.5, BUTTON_B | BUTTON_PLUS, clock)
    cursor, _ = frame(p, scene, 0.5, 0.5, 0, clock)
    assert cursor == (0.0, 0.0)
    frame(p, scene, 0.5, 0.5, BUTTON_B | BUTTON_PLUS, clock)
    cursor, _ = frame(p, scene, 0.5, 0.5, 0, clock)
    assert cursor != (0.0, 0.0)


def test_area_profile_output():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0, area="4:3"))
    calibrate(p, scene, clock)
    # apuntar al borde del area 4:3 da 0 / 1 en la salida
    left, _ = frame(p, scene, 0.125, 0.5, 0, clock)
    right, _ = frame(p, scene, 0.875, 0.5, 0, clock)
    assert left[0] == pytest.approx(0.0, abs=0.02)
    assert right[0] == pytest.approx(1.0, abs=0.02)
    # fuera del area: clamp
    out, _ = frame(p, scene, 0.05, 0.5, 0, clock)
    assert out[0] == 0.0


def test_calibration_valid_across_area_profiles():
    """La calibracion se guarda en espacio de pantalla: cambiar de perfil no la rompe."""
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0, area="4:3"))
    calibrate(p, scene, clock)
    p.set_area("full")
    cursor, _ = frame(p, scene, 0.3, 0.4, 0, clock)
    assert error_tv_px(cursor, (0.3, 0.4)) < 25


# ---------------------------------------------------------------- C18
def test_lost_goes_to_exit_edge():
    scene, clock = Scene(tv=TV(45), player=(0, 0, 2.5)), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    calibrate(p, scene, clock)
    # bajar el Wiimote hasta perder la barra (esta arriba): sale por abajo
    y = 0.5
    cursor = None
    while y < 3.0:
        cursor, _ = frame(p, scene, 0.5, y, 0, clock)
        if p.track.lost:
            break
        y += 0.05
    assert p.track.lost
    held, _ = frame(p, scene, 0.5, y, 0, clock)
    for _ in range(int(LOST_HOLD / 0.01) + 2):
        cursor, _ = frame(p, scene, 0.5, y, 0, clock)
    assert cursor[1] == 1.0
    assert 0.3 < cursor[0] < 0.7


def test_lost_hold_does_not_jump_on_flicker():
    scene, clock = Scene(), Clock()
    p = GunPipeline(GunOptions(smoothing_level=0))
    calibrate(p, scene, clock)
    a, _ = frame(p, scene, 0.4, 0.4, 0, clock)
    b, _ = frame(p, scene, 0.4, 0.4, 0, clock, drop=(0, 1))
    assert a == b


@pytest.mark.parametrize("p,v,want", [
    ((0.5, 0.9), (0.0, 0.0), (0.5, 1.0)),
    ((0.1, 0.5), (0.0, 0.0), (0.0, 0.5)),
    ((0.5, 0.5), (2.0, 0.0), (1.0, 0.5)),
    ((0.5, 0.5), (0.0, -3.0), (0.5, 0.0)),
    ((0.5, 0.5), (1.0, 1.0), (1.0, 1.0)),
])
def test_edge_point(p, v, want):
    assert edge_point(p, v) == pytest.approx(want)


def test_parse_targets():
    assert parse_targets("0.1,0.1,0.9,0.1,0.5,0.8") == [(0.1, 0.1), (0.9, 0.1), (0.5, 0.8)]
    with pytest.raises(ValueError):
        parse_targets("0.1,0.1")
