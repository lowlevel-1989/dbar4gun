"""Valores de hardware medidos (hardware.json) y autodiagnostico del calibrator."""

import json
import math

import pytest

import tests.sim.camera as cam
from dbar4gun.core.gun import GunOptions
from dbar4gun.core.hardware import HardwareConfig, focal_norm, fov_from_focal_px, focal_px
from dbar4gun.core.pointer import FOCAL
from dbar4gun.gui.logic import calibration, hardware
from dbar4gun.protocol import Packet, RAW_ABSENT
from dbar4gun.store import HardwareStore

from tests.sim.gui_harness import SimGun
from tests.sim.scene import Scene


@pytest.fixture
def fov(monkeypatch):
    """Cambia el FOV real de la camara simulada."""
    def set_fov(deg):
        monkeypatch.setattr(cam, "FOCAL_PX", focal_px(deg))
    return set_fov


def opts(**kw):
    kw.setdefault("smoothing_level", 0)
    return GunOptions(**kw)


# ----------------------------------------------------------------------
# core
def test_hardware_config_defaults_and_validation():
    hw = HardwareConfig()
    assert hw.to_dict() == {"fov_h_deg": 33.0, "acc_x_sign": 1.0, "bar_width_m": 0.20,
                            "ir_sensitivity": None}
    assert abs(focal_norm(33.0) - FOCAL) < 1e-12
    assert hw.set("fov", "38.5") == "fov_h_deg" and hw.fov_h_deg == 38.5
    assert hw.set("bar_width", 0.22) == "bar_width_m"
    hw.set("acc_x_sign", "1")
    assert hw.acc_x_sign == 1.0
    for k, v in (("fov", 5), ("fov", 80), ("acc_x_sign", 0), ("bar_width", 2), ("nope", 1)):
        with pytest.raises(ValueError):
            hw.set(k, v)
    # valores invalidos en el json: se queda el defecto
    hw2 = HardwareConfig.from_dict({"fov_h_deg": 99, "bar_width_m": 0.25, "junk": 1})
    assert hw2.fov_h_deg == 33.0 and hw2.bar_width_m == 0.25


def test_distance_uses_measured_fov_and_bar_width(fov, monkeypatch):
    """Con la camara a 40 grados, la distancia es correcta solo con el FOV medido."""
    fov(40.0)
    gun = SimGun(monkeypatch, Scene(player=(0.0, 0.0, 3.0)), options=opts())
    p = gun.packets(3)[-1]
    nominal = calibration.distance_m(p)
    measured = calibration.distance_m(p, HardwareConfig(fov_h_deg=40.0))
    assert abs(nominal - 3.0) > 0.4
    assert abs(measured - 3.0) < 0.05
    # el ancho de la barra escala la distancia
    wide = calibration.distance_m(p, HardwareConfig(fov_h_deg=40.0, bar_width_m=0.22))
    assert abs(wide / measured - 1.1) < 1e-6


def test_pipeline_status_reports_hardware(monkeypatch):
    gun = SimGun(monkeypatch, Scene(player=(0.0, 0.0, 2.0)),
                 options=opts(hardware=HardwareConfig(bar_width_m=0.20)))
    gun.packets(3)
    st = gun.drv.pipeline.status()
    assert st["hardware"]["fov_h_deg"] == 33.0
    assert abs(st["distance_m"] - 2.0) < 0.05


# ----------------------------------------------------------------------
# paso 1: enlace
def test_link_check_dolphinbar_and_bluetooth():
    p = Packet()
    p.hz, p.battery = 175.0, 39
    r = hardware.link_check({"key": "usb:usb-0000:00:14.0-3/input2"}, p)
    assert r["link"] == "dolphinbar" and r["slot"] == 3 and r["verdict"] == hardware.OK
    p.battery = 10
    r = hardware.link_check({"key": "bt:00:1f:32:aa:bb:cc"}, p)
    assert r["link"] == "bluetooth" and r["verdict"] == hardware.WARN and "low_battery" in r["notes"]
    p.battery, p.hz = 80, 40.0
    assert "low_hz" in hardware.link_check({}, p)["notes"]


# ----------------------------------------------------------------------
# paso 2: calidad IR
def _ir_run(monkeypatch, scene, n=200, drop_every=None, drop_led=1):
    gun = SimGun(monkeypatch, scene, options=opts())
    q = hardware.IRQuality()
    for i in range(n):
        drop = (drop_led,) if drop_every and i % drop_every == 0 else ()
        gun.drv.feed(scene.report(0.5, 0.5, 0.0, 0, drop))
        from dbar4gun.protocol import build_packet
        q.add(Packet.unpack(build_packet(gun.drv.wm, 1, 1).pack()))
    return q.result()


def test_ir_quality_ok(monkeypatch):
    r = _ir_run(monkeypatch, Scene(noise_px=0.5))
    assert r["verdict"] == hardware.OK and r["both"] == 1.0 and r["sensitivity"] is None
    assert 0.2 < r["jitter_px"] < 1.5


def test_ir_quality_detects_weak_led(monkeypatch):
    """Un LED que se pierde 1 de cada 3 reports (como uno danado)."""
    r = _ir_run(monkeypatch, Scene(), drop_every=3, drop_led=1)
    assert r["verdict"] == hardware.WARN
    assert r["weak_led"] == "right"
    assert r["sensitivity"] == "higher"
    r = _ir_run(monkeypatch, Scene(), drop_every=3, drop_led=0)
    assert r["weak_led"] == "left"


def test_ir_quality_detects_extra_source(monkeypatch):
    s = Scene(extra_ir=[(0.6, 0.45, 0.0)])
    r = _ir_run(monkeypatch, s)
    assert "extra_ir" in r["notes"] and r["sensitivity"] == "lower"


def test_ir_quality_no_bar():
    q = hardware.IRQuality()
    for _ in range(200):
        q.add(Packet())
    assert q.result()["verdict"] == hardware.FAIL


# ----------------------------------------------------------------------
# paso 3: signo del acelerometro
def _acc_run(monkeypatch, sign):
    gun = SimGun(monkeypatch, Scene(), options=opts(hardware=HardwareConfig(acc_x_sign=sign)))
    chk = hardware.AccSignCheck()
    for i in range(120):
        gun.roll = 45.0 * math.sin(i / 120.0 * 2 * math.pi)
        for p in gun.packets(1):
            chk.add(p)
    assert chk.ready()
    return chk.result(sign)


def test_acc_sign_ok(monkeypatch):
    r = _acc_run(monkeypatch, 1.0)
    assert r["verdict"] == hardware.OK and r["acc_x_sign"] == 1.0
    assert abs(r["slope"] + 1.0) < 0.1


def test_acc_sign_inverted_is_detected(monkeypatch):
    """Como el hardware real con el signo antiguo (-1): pendiente ~ +1."""
    r = _acc_run(monkeypatch, -1.0)
    assert r["verdict"] == hardware.FAIL and r["acc_x_sign"] == 1.0
    assert abs(r["slope"] - 1.0) < 0.1


def test_acc_sign_needs_rotation(monkeypatch):
    gun = SimGun(monkeypatch, Scene(), options=opts())
    chk = hardware.AccSignCheck()
    for p in gun.packets(60):
        chk.add(p)
    assert not chk.ready()
    assert chk.result(-1.0)["verdict"] == hardware.NA


# ----------------------------------------------------------------------
# paso 4: FOV
def bar_distance(scene):
    """Distancia real del Wiimote al centro de la barra (lo que se mide con la cinta)."""
    (x1, y1, z1), (x2, y2, z2) = scene.leds
    px, py, pz = scene.player
    cx, cy, cz = (x1 + x2) / 2.0, (y1 + y2) / 2.0, (z1 + z2) / 2.0
    return math.sqrt((px - cx) ** 2 + (py - cy) ** 2 + (pz - cz) ** 2)


@pytest.mark.parametrize("real_fov", [30.0, 33.0, 38.0, 42.0])
@pytest.mark.parametrize("distance", [1.5, 3.0])
def test_fov_measure(fov, monkeypatch, real_fov, distance):
    fov(real_fov)
    scene = Scene(player=(0.0, 0.0, distance), noise_px=0.3)
    gun = SimGun(monkeypatch, scene, options=opts())
    # apuntando cerca de la barra (de frente)
    gun.aim = (0.5, 0.0)
    m = hardware.FovMeasure(bar_distance(scene), 0.20)
    for p in gun.packets(80):
        m.add(p)
    assert m.ready()
    r = m.result()
    assert abs(r["fov_h_deg"] - real_fov) < 0.5, r
    assert r["verdict"] == hardware.OK


def test_fov_measure_ignores_off_center_and_extra_dots():
    m = hardware.FovMeasure(2.0, 0.20)
    p = Packet()
    p.raw = [(10, 10, 0xFF), (100, 10, 0xFF)] + [(RAW_ABSENT, RAW_ABSENT, 0xFF)] * 2
    m.add(p)
    p.raw = [(500, 380, 0xFF), (600, 380, 0xFF), (700, 300, 0xFF), (RAW_ABSENT, RAW_ABSENT, 0xFF)]
    m.add(p)
    assert m.focals == []


def test_fov_with_wrong_bar_width_is_proportional(fov, monkeypatch):
    """Si el ancho real es otro, la focal sale escalada en la misma proporcion."""
    fov(33.0)
    scene = Scene(player=(0.0, 0.0, 2.0))
    gun = SimGun(monkeypatch, scene, options=opts())
    gun.aim = (0.5, 0.0)
    m = hardware.FovMeasure(bar_distance(scene), 0.22)
    for p in gun.packets(80):
        m.add(p)
    assert abs(m.result()["focal_px"] / focal_px(33.0) - 1 / 1.1) < 0.01


def test_combine_fov():
    assert hardware.combine_fov([{"fov_h_deg": 38.0}, {"fov_h_deg": 39.0}, {"verdict": "na"}]) == 38.5
    assert hardware.combine_fov([]) is None
    assert abs(fov_from_focal_px(focal_px(37.0)) - 37.0) < 1e-9


# ----------------------------------------------------------------------
# paso 5: barra encima de la TV; debajo, un aviso
@pytest.mark.parametrize("real_top,verdict", [(True, hardware.OK), (False, hardware.WARN)])
def test_bar_side(monkeypatch, real_top, verdict):
    scene = Scene(bar_on_top=real_top)
    gun = SimGun(monkeypatch, scene, options=opts())
    gun.roll = 10.0
    chk = hardware.BarSideCheck()
    for p in gun.packets(40):
        chk.add(p)
    assert chk.ready()
    r = chk.result()
    assert r["verdict"] == verdict
    assert r["measured"] == ("top" if real_top else "bottom")


def test_bar_side_needs_valid_camera_point():
    chk = hardware.BarSideCheck()
    p = Packet()
    p.flags = 0
    chk.add(p)
    assert chk.result()["verdict"] == hardware.NA


# ----------------------------------------------------------------------
# paso 6: desconexion
def _pk(roll=0.0):
    p = Packet()
    p.virtualgun = 1
    p.roll = roll
    return p


def test_disconnect_stopped_and_back():
    d = hardware.DisconnectCheck(0.0)
    t = 0.0
    for i in range(30):
        t += 0.1
        d.update([_pk(i)], t)
    for _ in range(30):        # apagado: sin paquetes 3 s
        t += 0.1
        d.update([], t)
    assert d.state == "wait_on" and d.stopped == "stopped"
    for _ in range(20):        # encendido 2 s despues
        t += 0.1
        d.update([], t)
    t += 0.1
    d.update([_pk(1.0)], t)
    r = d.result()
    assert r["verdict"] == hardware.OK and r["stopped"] == "stopped"
    assert 3.0 < r["reconnect_s"] < 4.5


def test_disconnect_repeating_reports():
    """Una barra que repite el ultimo report al apagar el Wiimote."""
    d = hardware.DisconnectCheck(0.0)
    t = 0.0
    for i in range(10):
        t += 0.1
        d.update([_pk(i)], t)
    for _ in range(40):
        t += 0.1
        d.update([_pk(9)], t)
    assert d.state == "wait_on" and d.stopped == "repeating"
    t += 0.1
    d.update([_pk(42.0)], t)
    assert d.result()["verdict"] == hardware.OK


def test_disconnect_timeout():
    d = hardware.DisconnectCheck(0.0)
    d.update([_pk()], 0.1)
    d.update([], 2.0)
    d.update([], 100.0)
    assert d.state == "timeout" and d.result()["verdict"] == hardware.FAIL


def test_overall():
    assert hardware.overall({"a": {"verdict": hardware.OK}, "b": {"verdict": hardware.NA}}) == hardware.OK
    assert hardware.overall({"a": {"verdict": hardware.WARN}, "b": {"verdict": hardware.OK}}) == hardware.WARN
    assert hardware.overall({"a": {"verdict": hardware.WARN}, "b": {"verdict": hardware.FAIL}}) == hardware.FAIL


# ----------------------------------------------------------------------
# store y daemon
def test_hardware_store_roundtrip(tmp_path):
    store = HardwareStore(str(tmp_path / "cfg"))
    assert store.load_hardware().to_dict() == HardwareConfig().to_dict()
    store.save_hardware(HardwareConfig(fov_h_deg=39.0, acc_x_sign=1.0))
    hw = store.load_hardware()
    assert hw.fov_h_deg == 39.0 and hw.acc_x_sign == 1.0
    path = store.save_report({"fov": {"verdict": "ok"}})
    assert json.load(open(path))["fov"]["verdict"] == "ok"
    (tmp_path / "cfg" / "hardware.json").write_text("{broken")
    assert store.load_hardware().fov_h_deg == 33.0


# ----------------------------------------------------------------------
# IR sensitivity desde hardware.json
def test_ir_sensitivity_ladder_and_config():
    from dbar4gun.core.hardware import next_ir_sensitivity, IR_LEVELS
    from dbar4gun.wiimote import IR_SENSITIVITY
    assert set(IR_LEVELS) == set(IR_SENSITIVITY)
    assert next_ir_sensitivity("marcan", "higher") == "4"
    assert next_ir_sensitivity("marcan", "lower") == "2"
    assert next_ir_sensitivity("cliff", "higher") == "4"
    assert next_ir_sensitivity("5", "higher") is None
    assert next_ir_sensitivity("1", "lower") is None
    hw = HardwareConfig()
    assert hw.ir_sensitivity is None and hw.to_dict()["ir_sensitivity"] is None
    hw.set("ir", "4")
    assert hw.ir_sensitivity == "4" and hw.copy().ir_sensitivity == "4"
    hw.set("ir_sensitivity", "default")
    assert hw.ir_sensitivity is None
    with pytest.raises(ValueError):
        hw.set("ir_sensitivity", "9")
    assert HardwareConfig.from_dict({"ir_sensitivity": "5"}).ir_sensitivity == "5"
    assert HardwareConfig.from_dict({"ir_sensitivity": None}).ir_sensitivity is None


def test_set_ir_sensitivity_reconfigures_camera(monkeypatch):
    from dbar4gun.wiimote import IR_SENSITIVITY
    from tests.sim.driver import NewDriver
    drv = NewDriver(monkeypatch)
    scene = Scene()
    drv.feed(scene.report(0.5, 0.5))
    drv.io.written.clear()
    drv.wm.set_ir_sensitivity("marcan")          # sin cambio: nada
    drv.feed(scene.report(0.5, 0.5))
    assert not any(w[:1] == b"\x13" for w in drv.io.written)
    drv.wm.set_ir_sensitivity("4")
    drv.feed(scene.report(0.5, 0.5))
    block1 = IR_SENSITIVITY["4"][0]
    assert any(w[:1] == b"\x16" and block1 in w for w in drv.io.written)
    assert drv.wm.status()["ir_sensitivity"] == "4"
    drv.wm.set_ir_sensitivity("bogus")
    assert drv.wm.ir_sensitivity == "4"
