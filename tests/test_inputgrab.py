"""Bloqueo del mando de botones de hid-wiimote (Wiimote por Bluetooth)."""

import os
import types

from dbar4gun.inputgrab import InputGrab, hid_input_events, GRAB_REFRESH


def fake_sysfs(tmp_path, hidraw="hidraw1", devices=None):
    """
    /sys como en un PC con un Wiimote RVL-CNT-01-TR por Bluetooth (medido):
    los eventN cuelgan del mismo dispositivo HID que el hidraw.
    """
    hid = tmp_path / "devices" / "0005:057E:0330.0002"
    (tmp_path / "class" / "hidraw" / hidraw).mkdir(parents=True)
    os.symlink(str(hid), str(tmp_path / "class" / "hidraw" / hidraw / "device"))
    devices = devices if devices is not None else [
        ("input30", "event12", "Nintendo Wii Remote Accelerometer"),
        ("input31", "event13", "Nintendo Wii Remote IR"),
        ("input32", "event14", "Nintendo Wii Remote"),
        ("input33", "event15", "Nintendo Wii Remote Motion Plus"),
        ("input35", "event17", "Nintendo Wii Remote Nunchuk"),
    ]
    for inp, ev, name in devices:
        (hid / "input" / inp / ev).mkdir(parents=True)
        (hid / "input" / inp / "name").write_text(name + "\n")
    return str(tmp_path)


class FakeDevice(object):
    def __init__(self, path, opened):
        self.path = path
        self.grabbed = False
        self.closed = False
        opened.append(self)

    def grab(self):
        self.grabbed = True

    def ungrab(self):
        self.grabbed = False

    def close(self):
        self.closed = True


def make(tmp_path, **kw):
    opened = []
    sysfs = fake_sysfs(tmp_path, **kw)
    grab = InputGrab("/dev/hidraw1", sysfs=sysfs, open_device=lambda p: FakeDevice(p, opened))
    return grab, opened


def test_events_of_the_same_wiimote(tmp_path):
    sysfs = fake_sysfs(tmp_path)
    names = dict(hid_input_events("/dev/hidraw1", sysfs))
    assert names["Nintendo Wii Remote"] == "/dev/input/event14"
    assert len(names) == 5
    assert hid_input_events("/dev/hidraw9", sysfs) == []


def test_only_buttons_and_nunchuk_are_grabbed(tmp_path):
    """Nunca se abren IR, acelerometro ni Motion Plus: abrirlos y cerrarlos apaga la camara."""
    grab, opened = make(tmp_path)
    grab.update(0.0)
    assert sorted(d.path for d in opened) == ["/dev/input/event14", "/dev/input/event17"]
    assert all(d.grabbed for d in opened)
    grab.update(0.5)                         # antes de GRAB_REFRESH: no busca otra vez
    assert len(opened) == 2


def test_release_ungrabs_and_closes(tmp_path):
    grab, opened = make(tmp_path)
    grab.update(0.0)
    grab.release()
    assert all(not d.grabbed and d.closed for d in opened)
    assert grab.grabbed == {}


def test_devices_that_appear_later_are_grabbed(tmp_path):
    """hid-wiimote crea los eventN un poco despues que el hidraw."""
    grab, opened = make(tmp_path, devices=[])
    grab.update(0.0)
    assert opened == []
    hid = tmp_path / "devices" / "0005:057E:0330.0002" / "input" / "input32"
    (hid / "event14").mkdir(parents=True)
    (hid / "name").write_text("Nintendo Wii Remote\n")
    grab.update(GRAB_REFRESH)
    assert [d.path for d in opened] == ["/dev/input/event14"]


def test_gone_device_is_released(tmp_path):
    grab, opened = make(tmp_path)
    grab.update(0.0)
    import shutil
    # se desconecta el Nunchuk: se suelta solo ese
    shutil.rmtree(str(tmp_path / "devices" / "0005:057E:0330.0002" / "input" / "input35"))
    grab.update(GRAB_REFRESH)
    nunchuk = [d for d in opened if d.path == "/dev/input/event17"][0]
    assert nunchuk.closed and list(grab.grabbed) == ["/dev/input/event14"]


def test_open_error_is_retried_later(tmp_path):
    calls = []

    def failing(path):
        calls.append(path)
        raise OSError(13, "Permission denied")

    grab = InputGrab("/dev/hidraw1", sysfs=fake_sysfs(tmp_path), open_device=failing)
    grab.update(0.0)
    grab.update(GRAB_REFRESH)
    assert len(calls) == 4 and grab.grabbed == {}      # 2 dispositivos, 2 intentos


def test_disabled_does_nothing(tmp_path):
    opened = []
    grab = InputGrab("/dev/hidraw1", enabled=False, sysfs=fake_sysfs(tmp_path),
                     open_device=lambda p: FakeDevice(p, opened))
    grab.update(0.0)
    assert opened == []


def test_daemon_grabs_only_bluetooth_and_obeys_the_option():
    from dbar4gun.daemon.service import Dbar4Gun
    d = Dbar4Gun(types.SimpleNamespace(width=1920, height=1080, port=35460), None, None, None)
    try:
        assert d.input_grab("bt:aa:bb:cc:dd:ee:ff", "/dev/hidraw1").enabled
        assert not d.input_grab("usb:usb-xhci-hcd.1-1/input0", "/dev/hidraw0").enabled
        d.config.no_input_grab = True
        assert not d.input_grab("bt:aa:bb:cc:dd:ee:ff", "/dev/hidraw1").enabled
    finally:
        d.sock.close()
