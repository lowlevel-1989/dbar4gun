"""Validacion del simulador y baseline del pipeline actual."""

import math


from tests.fakes import make_wiimote
from tests.sim.camera import FOCAL_PX
from tests.sim.metrics import grid_43, GAME_PX
from tests.sim.payload import ir_basic_payload, DOT_ABSENT
from tests.sim.scene import Scene, TV, trajectory


def test_focal():
    assert abs(FOCAL_PX - 1728.5) < 0.1


def test_tv_size():
    tv = TV(45)
    assert abs(tv.width - 0.9962) < 1e-3
    assert abs(tv.height - 0.5603) < 1e-3


def test_payload_roundtrip_with_real_parser(monkeypatch):
    wm, _ = make_wiimote(monkeypatch)
    # (1023, 767) es un dot valido (el parser antiguo lo daba por ausente)
    dots = [(1, 2), (1023, 767), (512, 300), None]
    wm.parser_ir(ir_basic_payload(dots))
    for (rx, ry), parsed in zip(dots[:3], wm.core_ir_dot[:3]):
        assert parsed[2] == 1.0
        assert abs(parsed[0] - (1 - rx / 1023.0)) < 1e-9
        assert abs(parsed[1] - ry / 767.0) < 1e-9
    assert wm.core_ir_dot[3][2] == 0.0
    assert ir_basic_payload([None])[:2] == bytes([DOT_ABSENT & 0xFF] * 2)


def test_center_aim_projects_symmetric():
    s = Scene(player=(0.0, 0.0, 3.0))
    (x1, y1), (x2, y2) = s.raw_dots(0.5, 0.5)
    assert abs((x1 + x2) / 2.0 - 511.5) <= 1
    # separacion = f * 0.20 / distancia
    sep = math.hypot(x2 - x1, y2 - y1)
    # f * 0.20 / ~3 m = ~115 px
    assert 110 < sep < 120
    # barra arriba -> dots arriba en la imagen (v pequena) -> raw_y = 767 - v grande
    assert y1 > 383 and y2 > 383


def test_aim_right_moves_dots_left_and_cursor_right():
    s = Scene()
    left = s.raw_dots(0.2, 0.5)
    right = s.raw_dots(0.8, 0.5)
    assert right[0][0] < left[0][0]


def test_roll_rotates_dots():
    s = Scene()
    (x1, y1), (x2, y2) = s.raw_dots(0.5, 0.5, roll_deg=15)
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    assert abs(abs(angle) - 15) < 1.0


def test_dot_out_of_fov_is_absent():
    s = Scene(player=(0.0, 0.0, 1.0))
    # muy cerca y apuntando lejos de la barra: los LEDs salen del FOV
    assert s.raw_dots(0.5, 3.0) == [None, None]


def test_noise_is_deterministic():
    a = Scene(noise_px=1.0, seed=7).raw_dots(0.5, 0.5)
    b = Scene(noise_px=1.0, seed=7).raw_dots(0.5, 0.5)
    assert a == b


def test_trajectory():
    t = trajectory((0.0, 0.0), (1.0, 0.5))
    assert len(t) == 25 and t[0] == (0.0, 0.0) and t[-1] == (1.0, 0.5)


def test_grid():
    g = grid_43()
    assert len(g) == 49
    assert all(0.125 <= x <= 0.875 for x, _ in g)
    assert abs(GAME_PX - 4.5) < 1e-9
