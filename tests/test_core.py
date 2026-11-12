import math

import pytest

from dbar4gun.core.parser import parse_ir_basic, parse_ir_basic_raw
from dbar4gun.core.tracker import Tracker, acc_roll, SQUARE_Y
from dbar4gun.core.pointer import camera_point, angular_separation, distance_from_separation
from dbar4gun.core.area import AreaProfile
from dbar4gun.core.feedback import Rumble
from dbar4gun.core.calibration import (
    AffineMap, CaptureBuffer, CalibrationData, CalibrationSession, solve_affine_3pt,
    solve_scale_offset_2pt, quick_recalibrate, geometry_ok, ERR_NO_IR, ERR_UNSTABLE,
    ERR_GEOMETRY, MODE_3PT,
)
from dbar4gun.core.pointer import CameraPoint

from tests.sim.payload import ir_basic_payload, acc_bytes
from tests.sim.scene import Scene


def dots_of(scene, sx, sy, roll=0.0, drop=()):
    rep = scene.report(sx, sy, roll, drop=drop)
    return parse_ir_basic(rep[6:16]), tuple(rep[3:6])


# ---------------------------------------------------------------- parser
def test_parser_absent_only_by_full_y():
    raw = parse_ir_basic_raw(ir_basic_payload([(1023, 767), (255, 255), None, (0, 0)]))
    assert raw == [(1023, 767), (255, 255), None, (0, 0)]


def test_parser_normalization():
    d = parse_ir_basic(ir_basic_payload([(0, 767), (1023, 0)]))
    assert d[0] == (1.0, 1.0, 1.0)
    assert d[1] == (0.0, 0.0, 1.0)
    assert d[2][2] == 0.0 and d[3][2] == 0.0


# ---------------------------------------------------------------- tracker
def test_tracker_order_independent_of_slot_order():
    a = Scene(dot_order="left_first")
    b = Scene(dot_order="right_first")
    sa = Tracker().update(*dots_of(a, 0.5, 0.5), t=0)
    sb = Tracker().update(*dots_of(b, 0.5, 0.5), t=0)
    assert sa.tl == sb.tl and sa.tr == sb.tr
    assert sa.tr[0] > sa.tl[0]


def test_tracker_continuity_survives_slot_swaps():
    s = Scene(dot_order="random", seed=3)
    tr = Tracker()
    first = tr.update(*dots_of(s, 0.5, 0.5), t=0.0)
    for i in range(1, 30):
        st = tr.update(*dots_of(s, 0.5, 0.5), t=i * 0.01)
        assert st.tl == first.tl and st.tr == first.tr


@pytest.mark.parametrize("drop", [0, 1])
def test_tracker_reconstructs_lost_dot(drop):
    s = Scene()
    tr = Tracker()
    full = tr.update(*dots_of(s, 0.4, 0.4), t=0.0)
    st = tr.update(*dots_of(s, 0.4, 0.4, drop=(drop,)), t=0.1)
    assert st.valid and not st.full
    assert st.tl_rec != st.tr_rec
    assert math.hypot(st.tl[0] - full.tl[0], st.tl[1] - full.tl[1]) < 1e-3
    assert math.hypot(st.tr[0] - full.tr[0], st.tr[1] - full.tr[1]) < 1e-3


def test_tracker_reconstruction_expires_without_roll():
    s = Scene()
    tr = Tracker()
    tr.update(*dots_of(s, 0.4, 0.4), t=0.0)
    dots, _ = dots_of(s, 0.4, 0.4, drop=(1,))
    assert tr.update(dots, None, t=0.4).valid
    # pasados 0.5 s desde el ultimo par completo y sin acelerometro: no hay par
    assert not tr.update(dots, None, t=1.2).valid


def test_tracker_reconstruction_uses_roll_after_timeout():
    s = Scene()
    tr = Tracker()
    tr.update(*dots_of(s, 0.4, 0.4), t=0.0)
    for k in range(1, 20):
        st = tr.update(*dots_of(s, 0.4, 0.4, drop=(1,)), t=k * 0.1)
    # el LED 1 (derecha en el mundo) es el TL: el eje x normalizado va invertido
    assert st.valid and st.tl_rec and not st.tr_rec
    assert abs(st.angle) < math.radians(3)


def test_acc_roll_matches_scene():
    s = Scene()
    for r in (-150, -60, 0, 30, 100, 170):
        _, acc = dots_of(s, 0.5, 0.5, r)
        assert abs(math.degrees(acc_roll(acc)) - r) < 3


@pytest.mark.parametrize("roll", [100, -100, 170])
def test_tracker_orders_beyond_90_with_accelerometer(roll):
    """Sin par reciente, el acelerometro decide TL/TR incluso con el Wiimote boca abajo."""
    s = Scene()
    ref = Tracker().update(*dots_of(s, 0.5, 0.5, 0), t=0)
    st = Tracker().update(*dots_of(s, 0.5, 0.5, roll), t=0)
    cp_ref = camera_point(ref)
    cp = camera_point(st)
    assert abs(cp.x - cp_ref.x) < 0.05 and abs(cp.y - cp_ref.y) < 0.05


def test_tracker_lost():
    st = Tracker().update([(1.0, 1.0, 0.0)] * 4, None, t=0)
    assert st.lost and not st.valid


def test_tracker_picks_bar_pair_among_extra_dots():
    s = Scene()
    tr = Tracker()
    base = tr.update(*dots_of(s, 0.5, 0.5), t=0)
    dots, acc = dots_of(s, 0.5, 0.5)
    dots = [(0.9, 0.1, 1.0), dots[0], (0.05, 0.9, 1.0), dots[1]]
    st = tr.update(dots, acc, t=0.01)
    assert st.tl == base.tl and st.tr == base.tr


# ---------------------------------------------------------------- camera point
def test_camera_point_roll_invariant():
    s = Scene()
    ref = camera_point(Tracker().update(*dots_of(s, 0.3, 0.7, 0), t=0))
    for r in (-30, 15, 45):
        cp = camera_point(Tracker().update(*dots_of(s, 0.3, 0.7, r), t=0))
        # unidades: ~1.7 por separacion de barra; 0.05 = ~8 px de TV a 45"
        assert abs(cp.x - ref.x) < 0.05 and abs(cp.y - ref.y) < 0.05


def test_distance_estimate():
    for d in (1.5, 3.0, 4.0):
        s = Scene(player=(0, 0, d))
        cp = camera_point(Tracker().update(*dots_of(s, 0.5, 0.0), t=0))
        assert abs(distance_from_separation(cp.sep) - d) < 0.1


def test_camera_point_without_compensation_scales_with_distance():
    near = Scene(player=(0, 0, 2.0))
    far = Scene(player=(0, 0, 4.0))
    cn = camera_point(Tracker().update(*dots_of(near, 0.2, 0.5), t=0), True, False)
    cf = camera_point(Tracker().update(*dots_of(far, 0.2, 0.5), t=0), True, False)
    assert abs(cn.x) > abs(cf.x) * 1.5


# ---------------------------------------------------------------- calibration
def test_affine_3pt_exact():
    m = AffineMap(0.12, 0.01, -0.02, 0.2, 0.5, -0.05)
    cams = [(-3.0, 1.0), (3.5, 0.8), (0.2, 4.0)]
    screens = [m.apply(*c) for c in cams]
    s = solve_affine_3pt(cams, screens)
    for got, want in zip(s.to_list(), m.to_list()):
        assert abs(got - want) < 1e-9


def test_affine_collinear_is_none():
    assert solve_affine_3pt([(0, 0), (1, 1), (2, 2)], [(0, 0), (1, 1), (0, 1)]) is None


def test_scale_offset_2pt():
    m = solve_scale_offset_2pt([(0.0, 2.0), (-2.0, 0.0)], [(0.5, 0.5), (0.1, 0.1)])
    assert m.apply(0.0, 2.0) == pytest.approx((0.5, 0.5))
    assert m.apply(-2.0, 0.0) == pytest.approx((0.1, 0.1))
    assert m.b == 0 and m.c == 0


def test_quick_recalibrate_keeps_vertical_scale_and_rotation():
    base = AffineMap(0.12, 0.01, 0.02, 0.21, 0.5, -0.05)
    # el jugador se ha movido: x desplazado y escalado, y desplazado
    true = AffineMap(0.12 * 1.1, 0.01 * 1.1, 0.02, 0.21, 0.5 * 1.1 - 0.08, -0.05 + 0.03)
    cams = [(-3.0, 0.5), (3.0, 0.6)]
    screens = [true.apply(*c) for c in cams]
    q = quick_recalibrate(base, cams, screens)
    assert q.c == base.c and q.d == base.d
    for c in cams + [(0.0, 3.0), (2.0, 2.0)]:
        assert q.apply(*c) == pytest.approx(true.apply(*c), abs=1e-9)


def test_geometry_ok():
    assert geometry_ok(AffineMap(0.1, 0, 0, 0.2, 0, 0))
    assert not geometry_ok(AffineMap(-0.1, 0, 0, 0.2, 0, 0))
    assert not geometry_ok(AffineMap(0, 0, 0, 0, 0, 0))
    assert not geometry_ok(None)


def cp(x, y, unit=1.7):
    return CameraPoint(x, y, 0.0667, 0.0, unit)


def test_capture_median_rejects_outlier():
    b = CaptureBuffer()
    for i in range(7):
        b.push(cp(1.0 + 0.001 * i, 2.0))
    b.push(cp(1.0, 2.0))
    point, sep, err = b.capture()
    assert err is None and point == pytest.approx((1.003, 2.0), abs=1e-3)


def test_capture_unstable():
    b = CaptureBuffer()
    for i in range(8):
        b.push(cp(1.0 + 0.8 * (i % 2), 2.0))   # 0.4 / 1.7 = 0.24 sep > 0.15
    assert b.capture()[2] == ERR_UNSTABLE


def test_capture_no_ir():
    b = CaptureBuffer()
    for i in range(8):
        b.push(cp(1.0, 2.0))
    b.push(None)
    b.push(cp(1.0, 2.0))
    assert b.capture()[2] == ERR_NO_IR


def test_session_uses_frames_before_b_edge():
    targets = [(0.1, 0.1), (0.9, 0.1), (0.5, 0.85)]
    cams = [(-2.0, 1.0), (2.0, 1.0), (0.0, 4.0)]
    s = CalibrationSession("3pt", targets)
    s.feed(None, True)        # B ya pulsado al empezar: no captura
    for c in cams:
        for _ in range(8):
            assert s.feed(cp(*c), False) is None
        # el frame del disparo (con el tiron) no entra en la captura
        ev = s.feed(cp(c[0] + 5, c[1] + 5), True)
        s.feed(cp(*c), False)
    assert ev[0] == "done"
    data = ev[1]
    for c, t in zip(cams, targets):
        assert data.affine.apply(*c) == pytest.approx(t)


def _shoot(s, c):
    for _ in range(8):
        s.feed(cp(*c), False)
    ev = s.feed(cp(*c), True)
    s.feed(cp(*c), False)
    return ev


def test_session_rounds_are_averaged():
    """
    Dos vueltas (TL, TR, BC, TL, TR, BC): la captura de cada target es la media
    de sus dos disparos, asi un disparo desviado pesa la mitad.
    """
    from dbar4gun.core.calibration import MAX_SHOT_DIFF_SEP
    targets = [(0.1, 0.1), (0.9, 0.1), (0.5, 0.85)]
    cams = [(-2.0, 1.0), (2.0, 1.0), (0.0, 4.0)]
    s = CalibrationSession("3pt", targets, shots=2)
    off = 0.2 * 1.7                     # 0.2 separaciones: dentro de MAX_SHOT_DIFF_SEP
    assert 0.2 < MAX_SHOT_DIFF_SEP
    order = []
    for c in cams:                                          # primera vuelta
        order.append(s.step)
        assert _shoot(s, c)[0] == "captured"
    ev = None
    for c in cams:                                          # segunda, algo desviada
        order.append(s.step)
        ev = _shoot(s, (c[0] + off, c[1]))
    assert order == [0, 1, 2, 0, 1, 2]
    assert ev[0] == "done"
    for c, t in zip(cams, targets):
        assert ev[1].affine.apply(c[0] + off / 2, c[1]) == pytest.approx(t)


def test_session_inconsistent_shots_are_repeated():
    from dbar4gun.core.calibration import ERR_INCONSISTENT
    targets = [(0.1, 0.1), (0.9, 0.1), (0.5, 0.85)]
    cams = [(-2.0, 1.0), (2.0, 1.0), (0.0, 4.0)]
    s = CalibrationSession("3pt", targets, shots=2)
    for c in cams:
        _shoot(s, c)
    assert s.step == 0 and s.shots_taken == 3
    assert _shoot(s, (-2.0, 2.0)) == ("error", ERR_INCONSISTENT)   # 1/1.7 = 0.59 sep
    # los dos del target se repiten, seguidos
    assert s.step == 0 and s.shots_taken == 2
    assert _shoot(s, cams[0]) == ("shot", 0)
    assert _shoot(s, cams[0]) == ("captured", 1)
    _shoot(s, cams[1])
    assert _shoot(s, cams[2])[0] == "done"


def test_session_bad_geometry_restarts():
    s = CalibrationSession("3pt", [(0.1, 0.1), (0.9, 0.1), (0.5, 0.85)])
    events = []
    for c in [(2.0, 1.0), (-2.0, 1.0), (0.0, 4.0)]:   # izquierda/derecha cambiadas
        for _ in range(8):
            s.feed(cp(*c), False)
        events.append(s.feed(cp(*c), True))
        s.feed(cp(*c), False)
    assert events[-1] == ("error", ERR_GEOMETRY)
    assert s.step == 0 and not s.done


def test_calibration_data_roundtrip_and_conversion():
    d = CalibrationData(mode=MODE_3PT, affine=AffineMap(0.12, 0, 0, 0.21, 0.5, -0.05),
                        sep_ref=0.0667, targets=[(0.1, 0.1)], calibrated=True, timestamp=5.0)
    d2 = CalibrationData.from_dict(d.to_dict())
    assert d2.to_dict() == d.to_dict()
    # mismo cursor con y sin compensacion a la distancia de referencia
    c_comp = (1.5, 2.0)
    c_raw = (1.5 * 0.0667, 2.0 * 0.0667)
    assert d.map_for(False).apply(*c_raw) == pytest.approx(d.map_for(True).apply(*c_comp))


# ---------------------------------------------------------------- area (M1)
def test_area_profiles():
    full = AreaProfile.parse("full")
    assert full.to_output(0.3, 0.7) == (0.3, 0.7)

    a43 = AreaProfile.parse("4:3")
    assert (a43.x0, a43.w) == pytest.approx((0.125, 0.75))
    assert a43.to_output(0.125, 0.0) == pytest.approx((0.0, 0.0))
    assert a43.to_output(0.875, 1.0) == pytest.approx((1.0, 1.0))
    assert a43.to_screen(*a43.to_output(0.4, 0.6)) == pytest.approx((0.4, 0.6))

    wide = AreaProfile.parse("21:9")
    assert wide.x0 == 0 and wide.h < 1

    c = AreaProfile.parse("custom:0.1,0.05,0.8,0.9")
    assert c.to_output(0.5, 0.5) == pytest.approx((0.5, 0.5))


@pytest.mark.parametrize("bad", ["nope", "4:0", "custom:1,2", "custom:0.5,0,0.8,1"])
def test_area_invalid(bad):
    with pytest.raises(ValueError):
        AreaProfile.parse(bad)


# ---------------------------------------------------------------- rumble
def test_rumble_error_pattern_two_pulses_without_sleep():
    r = Rumble()
    r.start("error", 10.0)
    states = []
    t = 10.0
    while t < 10.5:
        s = r.update(t)
        if s is not None:
            states.append((round(t - 10.0, 2), s))
        t += 0.01
    assert [s for _, s in states] == [True, False, True, False]
    assert not r.active


# ----------------------------------------------------------------
from dbar4gun.core.tracker import merge_close


def test_merge_close():
    pts = merge_close([(0.5, 0.3), (0.505, 0.302), (0.7, 0.3)])
    assert len(pts) == 2 and pts[0] == pytest.approx((0.5025, 0.301))


def test_tracker_ignores_reflections_and_lamps():
    from tests.sim.scene import TV
    clean = Scene(tv=TV(45))
    dirty = Scene(tv=TV(45), split_px=6, extra_ir=[(-0.9, 0.55, -0.3)])
    tr = Tracker()
    ref = Tracker().update(*dots_of(clean, 0.4, 0.4), t=0)
    tr.update(*dots_of(clean, 0.4, 0.4), t=0)
    st = tr.update(*dots_of(dirty, 0.4, 0.4), t=0.01)
    assert math.hypot(st.tl[0] - ref.tl[0], st.tl[1] - ref.tl[1]) < 0.01
    assert math.hypot(st.tr[0] - ref.tr[0], st.tr[1] - ref.tr[1]) < 0.01


def test_lost_led_plus_lamp_reconstructs_instead_of_pairing():
    from tests.sim.scene import TV
    clean = Scene(tv=TV(45))
    lamp = Scene(tv=TV(45), extra_ir=[(0.35, 0.36, 0.0)])
    tr = Tracker()
    full = tr.update(*dots_of(clean, 0.5, 0.5), t=0)
    st = tr.update(*dots_of(lamp, 0.5, 0.5, drop=(0,)), t=0.01)
    assert st.valid and (st.tl_rec or st.tr_rec)
    assert math.hypot(st.tl[0] - full.tl[0], st.tl[1] - full.tl[1]) < 0.003


def test_tracker_recovers_after_sudden_distance_change():
    from tests.sim.scene import TV
    tr = Tracker()
    tr.update(*dots_of(Scene(tv=TV(45), player=(0, 0, 3.0)), 0.5, 0.5), t=0)
    near = Scene(tv=TV(45), player=(0, 0, 1.8))
    ref = Tracker().update(*dots_of(near, 0.5, 0.5), t=0)
    st = None
    for k in range(1, 80):
        st = tr.update(*dots_of(near, 0.5, 0.5), t=k * 0.01)
    assert st.full and st.tl == ref.tl and st.tr == ref.tr


# ----------------------------------------------------------------
from dbar4gun.core.calibration import HomographyMap, solve_homography_4pt, MODE_4PT


def test_homography_exact_and_roundtrip():
    h = HomographyMap([0.12, 0.01, 0.5, -0.02, 0.21, -0.05, 0.003, -0.002, 1.0])
    cams = [(-3.0, 1.0), (3.0, 1.2), (3.2, 4.0), (-2.8, 4.1)]
    screens = [h.apply(*c) for c in cams]
    s = solve_homography_4pt(cams, screens)
    for got, want in zip(s.to_list(), h.to_list()):
        assert got == pytest.approx(want, abs=1e-9)
    d = CalibrationData(mode=MODE_4PT, affine=s, sep_ref=0.0667, calibrated=True)
    d2 = CalibrationData.from_dict(d.to_dict())
    assert isinstance(d2.affine, HomographyMap) and d2.affine.apply(1, 2) == pytest.approx(s.apply(1, 2))
    # conversion entre modos de compensacion
    assert d.map_for(False).apply(1.5 * 0.0667, 2 * 0.0667) == pytest.approx(d.map_for(True).apply(1.5, 2))


def test_homography_collinear_is_none():
    assert solve_homography_4pt([(0, 0), (1, 1), (2, 2), (3, 3)],
                                [(0, 0), (1, 0), (1, 1), (0, 1)]) is None


def test_quick_recalibrate_on_homography():
    base = HomographyMap([0.12, 0.01, 0.5, -0.02, 0.21, -0.05, 0.003, -0.002, 1.0])
    cams = [(-3.0, 0.5), (3.0, 0.6)]
    shifted = [(x + 0.03, y - 0.02) for x, y in (base.apply(*c) for c in cams)]
    q = quick_recalibrate(base, cams, shifted)
    assert isinstance(q, HomographyMap)
    for c, t in zip(cams, shifted):
        assert q.apply(*c) == pytest.approx(t, abs=1e-9)
