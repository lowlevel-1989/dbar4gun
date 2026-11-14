"""
Daemon: Wiimotes que se conectan, cambian y desconectan (eventos de udev)
y reparto de puertos.
"""

import os
import types

import pytest

from dbar4gun.daemon import devices as devices_module
from dbar4gun.daemon.service import Dbar4Gun
from dbar4gun.monitor import classify_event


class FakeProcess(object):
    created = []

    def __init__(self, target=None, args=()):
        self.target = target
        self.args = args
        self.alive = False
        self.killed = False
        FakeProcess.created.append(self)

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive

    def kill(self):
        self.killed = True
        self.alive = False

    def join(self, timeout=None):
        self.joined = timeout


class FakeFileIO(object):
    def __init__(self, fd, mode, closefd=True):
        self.fd = fd
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def daemon(monkeypatch):
    FakeProcess.created = []
    closed_fds = []
    next_fd = [100]

    def fake_open(path, flags):
        next_fd[0] += 1
        return next_fd[0]

    monkeypatch.setattr(devices_module, "Process", FakeProcess)
    monkeypatch.setattr(devices_module, "FileIO", FakeFileIO)
    # solo el os del modulo: parchear os.close global rompe el propio pytest
    fake_os = types.SimpleNamespace(
        open=fake_open, close=closed_fds.append, O_RDWR=os.O_RDWR,
        getpid=os.getpid, kill=os.kill)
    monkeypatch.setattr(devices_module, "os", fake_os)

    config = types.SimpleNamespace(width=1920, height=1080, port=35460)
    d = Dbar4Gun(config, None, None, None)
    d.closed_fds = closed_fds
    yield d
    d.sock.close()


class FakeDevice(dict):
    def __init__(self, devname, model=None, parent=None):
        super().__init__()
        self["DEVNAME"] = devname
        if model:
            self["ID_MODEL_FROM_DATABASE"] = model
        self.parent = parent


WIIMOTE = FakeDevice("/dev/hidraw3", model="Wii Remote Controller RVL-003")


def test_sequence_add_change_dup_remove(daemon):
    raw_events = [
        ("add",    WIIMOTE),   # first scan
        ("add",    WIIMOTE),   # mismo dispositivo visto por udev
        ("change", WIIMOTE),
        ("add",    WIIMOTE),
        ("bind",   WIIMOTE),
    ]
    for action, dev in raw_events:
        ev = classify_event(action, dev)
        if ev:
            daemon.handle_event(*ev)

    assert len(FakeProcess.created) == 1
    assert list(daemon.processes) == ["/dev/hidraw3"]
    assert daemon.port[0] == 0

    proc = FakeProcess.created[0]
    fd, hid, port = daemon.files["/dev/hidraw3"]

    daemon.handle_event(*classify_event("remove", FakeDevice("/dev/hidraw3")))

    assert proc.killed
    assert hid.closed
    assert daemon.closed_fds == [fd]
    assert daemon.processes == {}
    assert daemon.files == {}
    assert daemon.port[port] == 1


def test_add_after_dead_process_recreates(daemon):
    daemon.handle_event("add", "/dev/hidraw3")
    FakeProcess.created[0].alive = False
    daemon.handle_event("add", "/dev/hidraw3")

    assert len(FakeProcess.created) == 2
    assert FakeProcess.created[1].is_alive()
    # el puerto se reutiliza, no se filtra
    assert daemon.files["/dev/hidraw3"][2] == 0
    assert daemon.port[1] == 1


def test_remove_unknown_is_ignored(daemon):
    daemon.handle_event("remove", "/dev/hidraw9")
    assert daemon.processes == {}


def test_classify_filters():
    other = FakeDevice("/dev/hidraw1", parent=types.SimpleNamespace(driver="hid-generic"))
    assert classify_event("add", other) is None
    # remove siempre pasa (el parent puede no existir ya)
    assert classify_event("remove", other) == ["remove", "/dev/hidraw1"]
    assert classify_event("change", WIIMOTE) is None
    assert classify_event("add", FakeDevice(None)) is None

    by_driver = FakeDevice("/dev/hidraw2", parent=types.SimpleNamespace(driver="wiimote"))
    assert classify_event("add", by_driver) == ["add", "/dev/hidraw2"]


def test_monitor_listens_before_first_scan(monkeypatch):
    from dbar4gun import monitor as monitor_module

    calls = []

    class FakeUdevMonitor(object):
        def filter_by(self, subsystem):
            calls.append(("filter", subsystem))

        def start(self):
            calls.append(("start",))

        def poll(self):
            calls.append(("poll",))
            return None

    class FakeContext(object):
        def list_devices(self, subsystem):
            calls.append(("scan", subsystem))
            return [WIIMOTE]

    monkeypatch.setattr(monitor_module.pyudev, "Context", FakeContext)
    monkeypatch.setattr(monitor_module.pyudev.Monitor, "from_netlink",
                        staticmethod(lambda ctx, source: FakeUdevMonitor()))

    q = []
    m = monitor_module.Monitor(types.SimpleNamespace(put=q.append))
    m.run()

    assert calls[:3] == [("filter", "hidraw"), ("start",), ("scan", "hidraw")]
    assert q == [["add", "/dev/hidraw3"]]



def test_no_free_port_closes_fd(daemon):
    """sin puerto libre se cierra el hidraw."""
    daemon.port = [0] * 16
    daemon.handle_event("add", "/dev/hidraw7")
    assert daemon.closed_fds == [101]
    assert daemon.processes == {} and daemon.files == {}


def test_remove_joins_process(daemon):
    """el proceso se recoge con join(timeout)."""
    daemon.handle_event("add", "/dev/hidraw3")
    proc = FakeProcess.created[0]
    daemon.handle_event("remove", "/dev/hidraw3")
    assert proc.joined == devices_module.JOIN_TIMEOUT


def test_preferred_port_and_take_port():
    from dbar4gun.daemon.ports import preferred_port, take_port
    assert preferred_port("usb:usb-xhci-hcd.1-1/input0") == 0
    assert preferred_port("usb:usb-xhci-hcd.1-1/input3") == 3
    assert preferred_port("bt:00:11:22:33:44:55") is None
    assert preferred_port(None) is None
    ports = [1] * 6
    assert take_port(ports, "usb:x/input2") == 2
    assert take_port(ports, "bt:aa") == 0                 # Bluetooth: el primero libre
    assert take_port(ports, "usb:x/input0") == 1          # su slot ocupado: el primero libre
    assert take_port([0, 0], "usb:x/input0") == -1


def test_dolphinbar_replug_out_of_order_keeps_slot_numbers(daemon, monkeypatch):
    """
    Al reconectar la DolphinBar, udev avisa de sus 4 slots desordenados
    (hidraw3, 2, 0, 1): cada slot sigue siendo su VirtualGun (slot 1 = 01).
    """
    iface = {"/dev/hidraw0": 0, "/dev/hidraw1": 1, "/dev/hidraw2": 2, "/dev/hidraw3": 3}
    monkeypatch.setattr(devices_module, "device_key",
                        lambda path: "usb:usb-xhci-hcd.1-1/input{}".format(iface[path]))
    for path in ("/dev/hidraw3", "/dev/hidraw2", "/dev/hidraw0", "/dev/hidraw1"):
        daemon.handle_event("add", path)
    assert {p: daemon.files[p][2] for p in iface} == iface
