"""
Filtro One Euro (smoothing) e historial de calibraciones.
"""

import math
import random

import pytest

from dbar4gun.core.calibration.data import CalibrationData
from dbar4gun.core.calibration.maps import AffineMap
from dbar4gun.core.filters import OneEuro2D, params_for_level, DEFAULT_FC_MIN
from dbar4gun.core.gun import GunOptions
from dbar4gun.store import CalibrationStore, HISTORY_MAX

from tests.sim.driver import NewDriver
from tests.sim.scene import Scene, TV


def game_px(a, b):
    # area 4:3 de una TV 16:9: 320 px de juego en 0.75 de ancho, 240 en el alto
    return math.hypot((a[0] - b[0]) * 320 / 0.75, (a[1] - b[1]) * 240)


# ---------------------------------------------------------------- One Euro
def test_one_euro_still_and_step():
    rng = random.Random(1)
    f = OneEuro2D()
    out = None
    for i in range(300):
        out = f((0.5 + rng.gauss(0, 0.002), 0.5 + rng.gauss(0, 0.002)), i * 0.01)
    assert abs(out[0] - 0.5) < 0.001 and abs(out[1] - 0.5) < 0.001
    # salto: converge sin pasarse
    for i in range(300, 400):
        out = f((0.8, 0.5), i * 0.01)
    assert out[0] == pytest.approx(0.8, abs=0.001)
    f.reset()
    assert f((0.1, 0.1), 5.0) == (0.1, 0.1)


def test_levels():
    assert params_for_level(0) is None
    assert params_for_level(3)["fc_min"] == DEFAULT_FC_MIN
    assert params_for_level(6)["fc_min"] < params_for_level(3)["fc_min"]


def drv_with_filter(monkeypatch, level=3):
    drv = NewDriver(monkeypatch, GunOptions(smoothing_level=level))
    drv.calibrate(Scene(tv=TV(45)))
    return drv


def test_filter_reduces_jitter_in_driver(monkeypatch):
    """One Euro filter en el driver: quieto, el jitter del cursor baja mucho respecto al raw."""
    scene = Scene(tv=TV(45), noise_px=0.5, seed=5)
    drv = drv_with_filter(monkeypatch)
    raw, out = [], []
    for i in range(300):
        out.append(drv.feed(scene.report(0.5, 0.5)))
        raw.append(drv.pipeline.screen)
    def spread(seq):
        m = (sum(p[0] for p in seq) / len(seq), sum(p[1] for p in seq) / len(seq))
        return max(game_px(p, m) for p in seq)
    assert spread(raw[100:]) > 3.0
    assert spread(out[100:]) < 1.2


def test_filter_lag_is_like_old_moving_average(monkeypatch):
    scene = Scene(tv=TV(45), noise_px=0.5, seed=5)
    drv = drv_with_filter(monkeypatch)
    lag = []
    for i in range(200):
        x = 0.5 + 0.3 * math.sin(2 * math.pi * i / 100.0)
        out = drv.feed(scene.report(x, 0.5))
        if i >= 50:
            lag.append(game_px(out, (x, 0.5)))
    # media movil de 3 frames de la v0.18: ~5.6 px de juego en el simulador
    assert sum(lag) / len(lag) < 7.0


def test_smoothing_level_0_disables(monkeypatch):
    drv = drv_with_filter(monkeypatch, level=0)
    assert drv.pipeline.filter is None
    out = drv.feed(Scene(tv=TV(45)).report(0.4, 0.4))
    assert out == pytest.approx(drv.pipeline.screen)


def test_filter_reset_when_lost(monkeypatch):
    scene = Scene(tv=TV(45))
    drv = drv_with_filter(monkeypatch)
    for _ in range(30):
        drv.feed(scene.report(0.3, 0.3))
    for _ in range(10):
        drv.feed(scene.report(0.3, 0.3, drop=(0, 1)))
    assert drv.pipeline.filter.x is None


def test_set_filter_persists_without_history(monkeypatch):
    drv = drv_with_filter(monkeypatch)
    drv.saved.clear()
    drv.pipeline.set_filter(0.5, 4.0)
    drv.feed(Scene(tv=TV(45)).report(0.5, 0.5))
    assert drv.saved and drv.saved[-1].filter == {"fc_min": 0.5, "beta": 4.0}
    assert drv.pipeline.filter.fc_min == 0.5 and drv.pipeline.filter.beta == 4.0
    # recalibrar conserva el filter ajustado
    drv.pipeline.reset_calibration()
    assert drv.pipeline.filter.fc_min == 0.5


# ---------------------------------------------------------------- history
def cal(tx, ts):
    return CalibrationData(affine=AffineMap(0.12, 0, 0, 0.2, tx, 0), calibrated=True, timestamp=ts)


def test_history_and_restore(tmp_path):
    store = CalibrationStore(str(tmp_path))
    store.save("bt:a", cal(0.1, 100.0))
    store.save("bt:a", cal(0.2, 200.0))
    assert [h["timestamp"] for h in store.history("bt:a")] == [100.0, 200.0]

    assert store.set_accuracy("bt:a", {"mean_tv": 9.0, "max_tv": 30.0})
    assert store.history("bt:a")[-1]["accuracy"]["mean_tv"] == 9.0
    assert not store.set_accuracy("bt:none", {})

    # ajuste de filter: actualiza la entrada vigente, no anade otra
    c = cal(0.2, 200.0)
    c.filter = {"fc_min": 0.7, "beta": 8.0}
    store.save("bt:a", c, add_history=False)
    hist = store.history("bt:a")
    assert len(hist) == 2 and hist[-1]["calibration"]["filter"]["fc_min"] == 0.7
    assert hist[-1]["accuracy"]["mean_tv"] == 9.0

    restored = store.restore("bt:a", 0)
    assert restored.affine.tx == 0.1
    assert store.load("bt:a").affine.tx == 0.1
    assert store.restore("bt:a", 5) is None


def test_history_is_bounded(tmp_path):
    store = CalibrationStore(str(tmp_path))
    for i in range(HISTORY_MAX + 5):
        store.save("k", cal(i / 100.0, float(i)))
    hist = store.history("k")
    assert len(hist) == HISTORY_MAX and hist[0]["timestamp"] == 5.0


def test_calibration_timestamp_is_wall_clock(monkeypatch):
    import time
    drv = NewDriver(monkeypatch)
    drv.calibrate(Scene(tv=TV(45)))
    assert abs(drv.saved[-1].timestamp - time.time()) < 60
