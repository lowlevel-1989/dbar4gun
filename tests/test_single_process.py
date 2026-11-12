"""E13 (experimental): un solo proceso con select sobre todos los hidraw."""

import io
import os
import threading
import time
import types

import pytest

from dbar4gun import dbar4gun as D
from dbar4gun import wiimote as W

from tests.sim.scene import Scene, TV


class PipeDevice(object):
    """hidraw falso con fileno real (pipe): select funciona de verdad."""

    def __init__(self):
        self.r, self.w = os.pipe()
        self.rio = io.FileIO(self.r, "rb", closefd=False)
        self.written = []

    def fileno(self):
        return self.r

    def readinto(self, buf):
        return self.rio.readinto(buf)

    def write(self, data):
        self.written.append(bytes(data))

    def close(self):
        pass

    def push(self, report):
        os.write(self.w, report)


class FakeGun(object):
    created = []

    def __init__(self, width, height, port):
        self.port = port
        self.cursor = None
        self.virtualgun = types.SimpleNamespace(close=lambda: None)
        FakeGun.created.append(self)

    def create_virtual_device(self):
        return self.port + 1

    def set_buttons(self, *a):
        pass

    def set_cursor(self, c):
        self.cursor = c

    def sync(self):
        pass


class FakeMonitor(object):
    events = []

    def __init__(self, queue):
        self.queue = queue

    def run(self):
        for e in FakeMonitor.events:
            self.queue.put(e)


def test_local_pipe():
    a, b = D.local_pipe()
    assert not b.poll()
    a.send((1, "x"))
    assert b.poll(0.1) and b.recv() == (1, "x")
    t0 = time.monotonic()
    assert not a.poll(0.05)
    assert time.monotonic() - t0 >= 0.04


def wait(t):
    # time.sleep esta parcheado (es el modulo time global): Event.wait si espera
    threading.Event().wait(t)


def test_single_process_two_guns(monkeypatch, tmp_path):
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    devices = {"/dev/hidraw1": PipeDevice(), "/dev/hidraw2": PipeDevice()}
    FakeGun.created = []
    FakeMonitor.events = [["add", "/dev/hidraw1"], ["add", "/dev/hidraw2"], ["add", "/dev/hidraw1"]]

    config = types.SimpleNamespace(width=1920, height=1080, port=1, config_dir=str(tmp_path),
                                   smoothing_level=0, single_process=True)
    d = D.Dbar4Gun(config, FakeMonitor, W.WiiMoteDevice, FakeGun)
    monkeypatch.setattr(d, "open_device", lambda path: (devices[path].r, devices[path]))
    monkeypatch.setattr(D, "device_key", lambda path: "k:" + path)

    stop = threading.Event()
    th = threading.Thread(target=d.run_single, args=(stop,))
    th.start()
    try:
        deadline = time.monotonic() + 5
        while (len(d.guns) < 2 or not all(g["index"] for g in d.guns.values())) and time.monotonic() < deadline:
            wait(0.02)
        assert len(FakeGun.created) == 2          # el add duplicado no crea otra

        scene = Scene(tv=TV(45))
        for _ in range(5):
            devices["/dev/hidraw1"].push(scene.report(0.3, 0.4))
            devices["/dev/hidraw2"].push(scene.report(0.7, 0.6))
            wait(0.02)
        wait(0.2)
        g1, g2 = FakeGun.created
        assert g1.cursor is not None and g2.cursor is not None
        assert g1.cursor[0] < 0.5 < g2.cursor[0]

        # P1 con el mismo codigo que los workers
        st = d.handle_command("status")
        assert [w["virtualgun"] for w in st["wiimotes"]] == [1, 2]
        assert st["wiimotes"][0]["key"] == "k:/dev/hidraw1"
        assert d.handle_command("area 4:3")["ok"]
        assert d.guns["/dev/hidraw2"]["wiimote"].pipeline.options.area.name == "4:3"

        d.events.put(["remove", "/dev/hidraw1"])
        wait(0.2)
        assert list(d.guns) == ["/dev/hidraw2"] and d.port[0] == 1
    finally:
        stop.set()
        th.join(3)
        d.sock.close()
        for dev in devices.values():
            for fd in (dev.w, dev.r):
                try:
                    os.close(fd)
                except OSError:
                    pass      # remove_single ya cerro el de hidraw1
    assert not th.is_alive()


class EmptySlotPipe(PipeDevice):
    """Slot de la DolphinBar sin Wiimote: las escrituras fallan con EPIPE."""

    present = False

    def write(self, data):
        if not self.present:
            raise BrokenPipeError(32, "Broken pipe")
        self.written.append(bytes(data))


def test_single_process_empty_slot_and_idle(monkeypatch, tmp_path):
    """
    Un slot vacio responde a status (paired: false) sin acumular peticiones, y
    un Wiimote que deja de enviar reports apaga el rumble y se da por
    desconectado (E6), como en el modo normal.
    """
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    devices = {"/dev/hidraw1": PipeDevice(), "/dev/hidraw2": EmptySlotPipe()}
    FakeGun.created = []
    FakeMonitor.events = [["add", "/dev/hidraw1"], ["add", "/dev/hidraw2"]]
    config = types.SimpleNamespace(width=1920, height=1080, port=1, config_dir=str(tmp_path),
                                   smoothing_level=0, single_process=True)
    d = D.Dbar4Gun(config, FakeMonitor, W.WiiMoteDevice, FakeGun)
    monkeypatch.setattr(d, "open_device", lambda path: (devices[path].r, devices[path]))
    monkeypatch.setattr(D, "device_key", lambda path: "k:" + path)

    stop = threading.Event()
    th = threading.Thread(target=d.run_single, args=(stop,))
    th.start()
    try:
        deadline = time.monotonic() + 5
        while (len(d.guns) < 2 or not d.guns["/dev/hidraw1"]["index"]) and time.monotonic() < deadline:
            wait(0.02)
        for _ in range(3):
            t0 = time.monotonic()
            st = d.handle_command("status")
            assert time.monotonic() - t0 < 0.4            # sin esperar el timeout
        by_vg = {w["virtualgun"]: w for w in st["wiimotes"]}
        assert by_vg[1]["paired"] is True
        assert by_vg[2]["paired"] is False and by_vg[2].get("ok") is not False
        assert not d.guns["/dev/hidraw2"]["conn"].inbox  # nada pendiente

        # el Wiimote 1 vibra y deja de enviar reports: el rumble se apaga solo
        wm = d.guns["/dev/hidraw1"]["wiimote"]
        clock = [100.0]
        wm.clock = lambda: clock[0]
        wm.rumble.start("ok", clock[0])
        wm.rumble.on = True                              # motor encendido
        wm.rumble_bit = 0x01
        devices["/dev/hidraw1"].written[:] = []
        clock[0] += 5.0
        wait(0.2)
        assert wm.rumble_bit == 0
        assert bytes([0x10, 0x00]) in devices["/dev/hidraw1"].written
        # y a los 10 s sin reports se da por desconectado (E6)
        wm.last_change_time = clock[0]
        clock[0] += W.NO_REPORT_TIMEOUT + 1
        wait(0.2)
        assert bytes([0x11, 0xf0]) in devices["/dev/hidraw1"].written
    finally:
        stop.set()
        th.join(3)
        d.sock.close()
        for dev in devices.values():
            for fd in (dev.w, dev.r):
                try:
                    os.close(fd)
                except OSError:
                    pass
    assert not th.is_alive()


def test_single_process_bluetooth_reconnect_keeps_virtualgun(monkeypatch, tmp_path):
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    devices = {"/dev/hidraw6": PipeDevice(), "/dev/hidraw7": PipeDevice()}
    FakeGun.created = []
    closed = []

    class KeepGun(FakeGun):
        def __init__(self, *a):
            FakeGun.__init__(self, *a)
            self.virtualgun = types.SimpleNamespace(close=lambda: closed.append(self))

    FakeMonitor.events = [["add", "/dev/hidraw6"]]
    config = types.SimpleNamespace(width=1920, height=1080, port=1, config_dir=str(tmp_path),
                                   smoothing_level=0, single_process=True)
    d = D.Dbar4Gun(config, FakeMonitor, W.WiiMoteDevice, KeepGun)
    monkeypatch.setattr(d, "open_device", lambda path: (devices[path].r, devices[path]))
    monkeypatch.setattr(D, "device_key", lambda path: "bt:00:11:22:33:44:55")

    stop = threading.Event()
    th = threading.Thread(target=d.run_single, args=(stop,))
    th.start()
    try:
        deadline = time.monotonic() + 5
        while not (d.guns.get("/dev/hidraw6") or {}).get("index") and time.monotonic() < deadline:
            wait(0.02)
        d.events.put(["remove", "/dev/hidraw6"])
        wait(0.3)
        assert "detached:bt:00:11:22:33:44:55" in d.guns and not closed
        st = d.handle_command("status")
        assert st["wiimotes"][0]["paired"] is False

        d.events.put(["add", "/dev/hidraw7"])               # vuelve la misma MAC
        deadline = time.monotonic() + 5
        while not any(w[:1] == b"\x13" for w in devices["/dev/hidraw7"].written) \
                and time.monotonic() < deadline:
            wait(0.02)
        assert any(w[:1] == b"\x13" for w in devices["/dev/hidraw7"].written)
        assert list(d.guns) == ["/dev/hidraw7"] and len(FakeGun.created) == 1 and not closed
        assert d.handle_command("status")["wiimotes"][0]["paired"] is True
    finally:
        stop.set()
        th.join(3)
        d.sock.close()
        for dev in devices.values():
            for fd in (dev.w, dev.r):
                try:
                    os.close(fd)
                except OSError:
                    pass
    assert not th.is_alive()
