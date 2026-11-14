"""
Criterios de aceptacion de precision (simulador, TV de 45", grid 7x7 en el
area 4:3), de extremo a extremo: report 0x37 -> WiiMoteDevice -> cursor.
"""

import pytest

from tests.sim.driver import NewDriver
from tests.sim.metrics import error_tv_px, AREA_43_X0, AREA_43_W
from tests.sim.scenarios import run_all, format_table
from tests.sim.scene import Scene, TV


@pytest.fixture(scope="module")
def results():
    mp = pytest.MonkeyPatch()
    try:
        rows = dict(run_all(lambda: NewDriver(mp)))
    finally:
        mp.undo()
    return rows


def test_report(results, capsys):
    with capsys.disabled():
        print(format_table("[pipeline nuevo]", list(results.items())))


def test_3m(results):
    s = results["3 m"]
    assert s.mean_tv <= 12 and s.max_tv <= 35, s


def test_roll_15(results):
    assert results["calib roll 0, juego roll 15"].mean_tv <= 12


def test_distance_change(results):
    assert results["calib 3.0 m, juego 2.6 m"].mean_tv <= 15


def test_side_50cm(results):
    assert results["50 cm de lado"].mean_tv <= 25


@pytest.mark.parametrize("corner", [(0.05, 0.05), (0.95, 0.05), (0.05, 0.95), (0.95, 0.95)])
@pytest.mark.parametrize("drop", [0, 1])
def test_dot_loss_in_corner_does_not_jump(monkeypatch, corner, drop):
    scene = Scene(tv=TV(45), player=(0.0, 0.0, 3.0))
    drv = NewDriver(monkeypatch)
    drv.calibrate(scene)

    sx = AREA_43_X0 + AREA_43_W * corner[0]
    sy = corner[1]
    for _ in range(5):
        before = drv.feed(scene.report(sx, sy))
    for _ in range(5):
        after = drv.feed(scene.report(sx, sy, drop=(drop,)))
        jump = error_tv_px(after, before)
        assert jump <= 20, "salto de {:.1f} px al perder el dot {}".format(jump, drop)


def test_dot_loss_while_moving(monkeypatch):
    """Perder un dot a mitad de una trayectoria tampoco salta."""
    from tests.sim.scene import trajectory

    scene = Scene(tv=TV(45))
    drv = NewDriver(monkeypatch)
    drv.calibrate(scene)
    path = trajectory((0.3, 0.3), (0.8, 0.6))
    for i, (x, y) in enumerate(path):
        drop = (1,) if i >= 12 else ()
        cursor = drv.feed(scene.report(x, y, drop=drop))
        assert error_tv_px(cursor, (x, y)) <= 35


@pytest.mark.parametrize("noise", [0.5, 2.0])
def test_calibration_with_sensor_noise(monkeypatch, noise):
    """Con ruido en los dots la captura (mediana) no se rechaza y la precision aguanta."""
    from tests.sim.metrics import measure_grid

    scene = Scene(tv=TV(45), noise_px=noise, seed=11)
    drv = NewDriver(monkeypatch)
    drv.calibrate(scene)
    s = measure_grid(scene, drv.feed, frames=10)
    assert s.mean_tv <= (12 if noise <= 0.5 else 40), s


def test_mode_4pt_homography(monkeypatch):
    """el modo 3 (4 puntos) mejora el maximo y la calibracion fuera del centro."""
    from dbar4gun.core.gun import GunOptions
    from tests.sim.metrics import measure_grid

    rows = dict(run_all(lambda: NewDriver(monkeypatch, GunOptions(calibration_mode=3, smoothing_level=0))))
    assert rows["3 m"].mean_tv <= 12 and rows["3 m"].max_tv <= 20
    assert rows["calib 3.0 m, juego 2.6 m"].mean_tv <= 12
    side = Scene(tv=TV(45), player=(1.0, 0.0, 2.5))
    d3 = NewDriver(monkeypatch, GunOptions(calibration_mode=3, smoothing_level=0))
    d3.calibrate(side)
    d2 = NewDriver(monkeypatch)
    d2.calibrate(side)
    assert measure_grid(side, d3.feed).mean_tv < measure_grid(side, d2.feed).mean_tv * 0.5
