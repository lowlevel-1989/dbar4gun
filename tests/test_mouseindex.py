"""Mouse index como RetroArch (udev): LED y teclas de cada pistola."""

import types

import pytest

from dbar4gun import mouseindex
from dbar4gun import virtualgun as V


class FakeContext(object):
    """list_devices(subsystem="input", ID_INPUT_X="1") con el orden de libudev."""

    def __init__(self, devices):
        # (sys_name, propiedades)
        self.devices = devices

    def list_devices(self, subsystem=None, **props):
        (prop, value), = props.items()
        for name, p in self.devices:
            if p.get(prop) == value:
                node = "/dev/input/" + name if name.startswith(("event", "mouse")) else None
                yield types.SimpleNamespace(sys_name=name, device_node=node)


# orden medido en un PC (2026-11-12): las VirtualGun (virtual/input) antes que
# un raton Bluetooth (virtual/misc/uhid) y el touchpad (ID_INPUT_TOUCHPAD) al final
PC = FakeContext([
    ("input40", {"ID_INPUT_MOUSE": "1"}),           # sin devnode: no cuenta
    ("event13", {"ID_INPUT_MOUSE": "1"}),           # VirtualGun 01
    ("mouse4", {"ID_INPUT_MOUSE": "1"}),            # /dev/input/mouseN: no cuenta
    ("event14", {"ID_INPUT_MOUSE": "1"}),           # VirtualGun 05
    ("event12", {"ID_INPUT_MOUSE": "1"}),           # ProtoArc (Bluetooth)
    ("event3", {"ID_INPUT_TOUCHPAD": "1"}),         # touchpad
    ("event5", {"ID_INPUT_KEY": "1"}),              # teclado
])


def test_pointer_order_like_retroarch():
    assert mouseindex.pointer_order(PC) == ["event13", "event14", "event12", "event3"]
    assert mouseindex.mouse_index("event14", PC) == 2
    assert mouseindex.mouse_index("/dev/input/event13", PC) == 1
    assert mouseindex.mouse_index("event3", PC) == 4
    assert mouseindex.mouse_index("event99", PC) is None


def test_mouse_index_without_udev(monkeypatch):
    def broken():
        raise OSError("no udev")
    monkeypatch.setattr(mouseindex, "_context", broken)
    assert mouseindex.mouse_index("event13") is None


class FakeUInput(object):
    def __init__(self, path="/dev/input/event14"):
        self.device = types.SimpleNamespace(path=path)
        self.writes = []

    def write(self, etype, code, value):
        self.writes.append((code, value))

    def syn(self):
        pass


def test_keys_follow_the_mouse_index():
    gun = V.VirtualGunDevice(1920, 1080, 4)      # puerto 5 (Bluetooth con la barra)
    gun.virtualgun = FakeUInput()
    gun.set_index(2)
    assert gun.index_map == V._MAP_INDEX_MAX      # teclas del jugador 2
    gun.set_index(5)
    assert gun.index_map == 0                     # ciclo de 4, como los LEDs
    # al cambiar de jugador se sueltan las teclas del anterior
    p2 = V._MAP[V._MAP_INDEX_MAX:2 * V._MAP_INDEX_MAX]
    assert all((code, 0) in gun.virtualgun.writes for code in p2)


def test_refresh_index(monkeypatch):
    gun = V.VirtualGunDevice(1920, 1080, 0)
    gun.virtualgun = FakeUInput("/dev/input/event14")
    gun.set_index(3)
    monkeypatch.setattr(mouseindex, "_context", lambda: PC)
    assert gun.refresh_index() == 2
    monkeypatch.setattr(mouseindex, "_context", lambda: FakeContext([]))
    assert gun.refresh_index() == 3                # udev no lo da: el anterior


def test_daemon_follows_mouse_index_changes(monkeypatch, tmp_path):
    from dbar4gun import dbar4gun as D
    from dbar4gun.wiimote import player_leds
    from tests.fakes import make_wiimote

    d = D.Dbar4Gun(types.SimpleNamespace(width=1920, height=1080, port=35460,
                                         config_dir=str(tmp_path)), None, None, None)
    try:
        wm, io = make_wiimote(monkeypatch)
        wm.update_index(1)
        gun = V.VirtualGunDevice(1920, 1080, 0)
        gun.virtualgun = FakeUInput("/dev/input/event14")
        gun.set_index(1)
        monkeypatch.setattr(mouseindex, "_context", lambda: PC)   # ahora es el raton 2
        io.written.clear()
        assert d._refresh_index(wm, gun, 1) == 2
        assert io.written[-1] == bytes([0x11, player_leds(2)])
        assert gun.index_map == V._MAP_INDEX_MAX
        # hasta INDEX_REFRESH s no se vuelve a mirar
        monkeypatch.setattr(mouseindex, "_context", lambda: FakeContext([]))
        assert d._refresh_index(wm, gun, 2) == 2
    finally:
        d.sock.close()
