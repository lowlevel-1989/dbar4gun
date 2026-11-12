import math

import pytest

from dbar4gun.protocol import (
    Packet, build_packet, SIZE, VERSION, RAW_ABSENT, DOT_VALID, DOT_RECONSTRUCTED,
    FLAG_CALIBRATING, FLAG_CALIBRATED, FLAG_BAR_ON_TOP, FLAG_CP_VALID,
)
from dbar4gun.core.gun import BUTTON_A, BUTTON_B, BUTTON_PLUS

from tests.sim.driver import NewDriver
from tests.sim.scene import Scene


def test_roundtrip_defaults():
    p = Packet()
    data = p.pack()
    assert len(data) == SIZE and data[0] == VERSION
    q = Packet.unpack(data)
    assert q.step == -1 and q.battery is None and math.isnan(q.roll)
    assert q.raw[0][1] == RAW_ABSENT and q.n_dots == 0


def test_rejects_other_versions_and_sizes():
    data = bytearray(Packet().pack())
    data[0] = 1
    assert Packet.unpack(bytes(data)) is None
    assert Packet.unpack(b"\x02" * 10) is None


def test_packet_from_driver(monkeypatch):
    scene = Scene()
    drv = NewDriver(monkeypatch)
    drv.wm.battery = 80
    drv.feed(scene.report(0.3, 0.4))
    p = Packet.unpack(build_packet(drv.wm, 5, 1).pack())
    assert p.index == 5 and p.virtualgun == 1 and p.battery == 80
    assert p.n_dots == 2
    assert p.has(FLAG_BAR_ON_TOP) and p.has(FLAG_CP_VALID) and not p.has(FLAG_CALIBRATED)
    assert all(d[2] == DOT_VALID for d in p.dots)
    assert p.screen == pytest.approx((0.3, 0.4), abs=0.06)    # mapa nominal
    assert abs(p.roll) < 2 and abs(p.angle) < 1
    assert p.separation == pytest.approx(0.0667, abs=0.003)


def test_packet_during_calibration_and_reconstruction(monkeypatch):
    scene = Scene()
    drv = NewDriver(monkeypatch)
    drv.press(scene, BUTTON_A | BUTTON_PLUS)
    for _ in range(8):
        drv.feed(scene.report(0.1, 0.1))
    drv.feed(scene.report(0.1, 0.1, drop=(1,), buttons=BUTTON_B))
    p = Packet.unpack(build_packet(drv.wm, 1, 1).pack())
    assert p.has(FLAG_CALIBRATING) and p.total == 3
    assert p.step == 1 and p.captured == 1
    assert p.buttons & BUTTON_B        # botones sin mascara
    assert p.dots[0][2] == DOT_VALID | DOT_RECONSTRUCTED
    assert p.target == pytest.approx(drv.pipeline.session.targets[1])
    assert p.n_dots == 1
