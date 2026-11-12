"""P1 en el daemon: comandos repartidos a los workers por Pipe."""

import types

import pytest

from dbar4gun import dbar4gun as dbar4gun_module
from dbar4gun.dbar4gun import Dbar4Gun
from dbar4gun.core.gun import GunPipeline

from tests.fakes import FakeHidraw, make_wiimote


@pytest.fixture
def daemon(tmp_path):
    config = types.SimpleNamespace(width=1920, height=1080, port=35460,
                                   config_dir=str(tmp_path), area="full")
    d = Dbar4Gun(config, None, None, None)
    yield d
    d.sock.close()


class Worker(object):
    """Un worker real (_worker_command) atendido en el mismo proceso."""

    def __init__(self, daemon, monkeypatch, port, key):
        self.parent, self.child = dbar4gun_module.Pipe()
        self.wm, _ = make_wiimote(monkeypatch, pipeline=daemon.make_pipeline(key))
        self.wm.player = port + 1
        self.port, self.key = port, key
        self.store = daemon.store()
        daemon.workers["/dev/hidraw{}".format(port)] = [self.parent, port, key]

    def serve(self, daemon):
        while self.child.poll():
            daemon._worker_command(self.child, self.wm, self.port, self.key,
                                   "/dev/hidraw{}".format(self.port), self.store)


def ask(daemon, workers, line, monkeypatch):
    """handle_command con los workers atendiendo justo despues de cada envio."""
    real_ask = daemon._ask_workers

    def ask_and_serve(cmd, args=(), ports=None):
        orig_send = []
        for w in workers:
            orig = w.parent.send

            def send(msg, w=w, orig=orig):
                orig(msg)
                w.serve(daemon)
            monkeypatch.setattr(w.parent, "send", send, raising=False)
        return real_ask(cmd, args, ports)

    monkeypatch.setattr(daemon, "_ask_workers", ask_and_serve)
    return daemon.handle_command(line)


def test_status_area_calibrate_reload(daemon, monkeypatch):
    workers = [Worker(daemon, monkeypatch, 0, "bt:a"), Worker(daemon, monkeypatch, 1, "bt:b")]

    st = ask(daemon, workers, "status", monkeypatch)
    assert st["ok"] and [g["virtualgun"] for g in st["wiimotes"]] == [1, 2]
    assert st["wiimotes"][0]["key"] == "bt:a"

    assert ask(daemon, workers, "area 4:3", monkeypatch)["ok"]
    assert all(w.wm.pipeline.options.area.name == "4:3" for w in workers)
    assert daemon.area == "4:3"
    assert not ask(daemon, workers, "area bogus", monkeypatch)["ok"]
    assert ask(daemon, workers, "area default", monkeypatch)["area"] == "full"
    assert all(w.wm.pipeline.options.area.name == "full" for w in workers)

    r = ask(daemon, workers, "calibrate 2", monkeypatch)
    assert r["started"] == [2]
    assert workers[1].wm.pipeline.calibrating and not workers[0].wm.pipeline.calibrating
    ask(daemon, workers, "cancel", monkeypatch)
    assert not workers[1].wm.pipeline.calibrating

    from dbar4gun.core.calibration import CalibrationData, AffineMap
    daemon.store().save("bt:a", CalibrationData(affine=AffineMap(0.1, 0, 0, 0.2, 0.33, 0),
                                                calibrated=True))
    r = ask(daemon, workers, "reload", monkeypatch)
    assert r["loaded"] == [1, 2]   # bt:b no existe -> default
    assert workers[0].wm.pipeline.calibration.affine.tx == 0.33


def test_unknown_command(daemon):
    assert not daemon.handle_command("explode")["ok"]


def test_worker_without_reply_times_out(daemon, monkeypatch):
    parent, child = dbar4gun_module.Pipe()
    daemon.workers["/dev/hidraw0"] = [parent, 0, "k"]
    monkeypatch.setattr(dbar4gun_module, "WORKER_REPLY_TIMEOUT", 0.05)
    st = daemon.handle_command("status")
    assert st["wiimotes"][0]["error"] == "no response"


def test_late_replies_are_discarded(daemon, monkeypatch):
    parent, child = dbar4gun_module.Pipe()
    daemon.workers["/dev/hidraw0"] = [parent, 0, "k"]
    child.send((-5, {"stale": True}))
    monkeypatch.setattr(dbar4gun_module, "WORKER_REPLY_TIMEOUT", 0.05)
    st = daemon.handle_command("status")
    assert "stale" not in st["wiimotes"][0]


def test_saved_calibration_loaded_at_start(daemon):
    from dbar4gun.core.calibration import CalibrationData, AffineMap
    daemon.store().save("bt:z", CalibrationData(affine=AffineMap(0.1, 0, 0, 0.2, 0.44, 0),
                                                calibrated=True))
    p = daemon.make_pipeline("bt:z")
    assert p.calibration.calibrated and p.calibration.affine.tx == 0.44
    assert p.default_kind() == "quick"


def test_filter_usefulzone_save_history(daemon, monkeypatch, tmp_path):
    workers = [Worker(daemon, monkeypatch, 0, "bt:a")]
    from dbar4gun.core.calibration import CalibrationData, AffineMap

    # una calibracion hecha (para que el filter se guarde)
    cal = CalibrationData(affine=AffineMap(0.12, 0, 0, 0.2, 0.5, 0), calibrated=True, timestamp=1.0)
    workers[0].wm.pipeline.set_calibration(cal)
    workers[0].wm.on_save = lambda data, h=True: daemon.store().save("bt:a", data, h)
    daemon.store().save("bt:a", cal)

    r = ask(daemon, workers, "filter 1 0.6 7", monkeypatch)
    assert r["ok"] and r["filter"]["fc_min"] == 0.6
    assert not ask(daemon, workers, "filter 1 x", monkeypatch)["ok"]
    workers[0].wm._run_actions(0.0)        # el worker procesa el guardado
    assert daemon.store().load("bt:a").filter["beta"] == 7.0

    assert ask(daemon, workers, "usefulzone 0.8", monkeypatch)["ok"]
    assert workers[0].wm.pipeline.options.useful_zone == 0.8
    assert not ask(daemon, workers, "usefulzone 2", monkeypatch)["ok"]

    ask(daemon, workers, "area 4:3", monkeypatch)
    r = ask(daemon, workers, "save", monkeypatch)
    assert r["ok"]
    text = open(r["path"]).read()
    assert "default = 4:3" in text and "useful_zone = 0.800" in text
    # al arrancar se leen de profiles.cfg
    d2 = Dbar4Gun(daemon.config, None, None, None)
    d2.load_profile_defaults()
    assert d2.area == "4:3" and d2.useful_zone == 0.8
    d2.sock.close()

    h = ask(daemon, workers, "history 1", monkeypatch)
    assert h["ok"] and len(h["history"]) == 1
    assert ask(daemon, workers, "accuracy 1 9.5 31 2.1 6.9", monkeypatch)["ok"]
    assert ask(daemon, workers, "history 1", monkeypatch)["history"][0]["accuracy"]["mean_tv"] == 9.5
    daemon.store().save("bt:a", CalibrationData(affine=AffineMap(0.1, 0, 0, 0.2, 0.7, 0),
                                                calibrated=True, timestamp=2.0))
    assert ask(daemon, workers, "restore 1 0", monkeypatch)["ok"]
    assert workers[0].wm.pipeline.calibration.affine.tx == 0.5
    assert not ask(daemon, workers, "restore 9 0", monkeypatch)["ok"]


def test_set_entry_keeps_user_lines(tmp_path):
    from dbar4gun.profiles import set_entry, load_profiles
    p = tmp_path / "profiles.cfg"
    p.write_text("# mio\narcade = 4:3\ndefault = full  # comentario\n")
    set_entry(str(p), "default", "custom:0.1,0,0.8,1")
    set_entry(str(p), "useful_zone", "0.8")
    text = p.read_text()
    assert text.startswith("# mio\narcade = 4:3\n")
    assert load_profiles(str(p)) == {"arcade": "4:3", "default": "custom:0.1,0,0.8,1", "useful_zone": "0.8"}


def test_hw_command_saves_and_applies(daemon, monkeypatch, tmp_path):
    """`hw` cambia hardware.json y lo aplica a los Wiimotes en marcha."""
    workers = [Worker(daemon, monkeypatch, 0, "bt:a"), Worker(daemon, monkeypatch, 1, "bt:b")]
    r = ask(daemon, workers, "hw", monkeypatch)
    assert r["ok"] and r["hardware"]["fov_h_deg"] == 33.0

    r = ask(daemon, workers, "hw fov 38.5 acc_x_sign 1 bar_width 0.22", monkeypatch)
    assert r["ok"], r
    assert (tmp_path / "hardware.json").exists()
    for w in workers:
        hw = w.wm.pipeline.options.hardware
        assert (hw.fov_h_deg, hw.acc_x_sign, hw.bar_width_m) == (38.5, 1.0, 0.22)
        assert w.wm.pipeline.tracker.acc_x_sign == 1.0
    st = ask(daemon, workers, "status", monkeypatch)
    assert st["hardware"]["fov_h_deg"] == 38.5
    assert st["wiimotes"][0]["hardware"]["bar_width_m"] == 0.22

    for bad in ("hw fov", "hw fov 99", "hw acc_x_sign 0", "hw color red"):
        assert not ask(daemon, workers, bad, monkeypatch)["ok"], bad
    assert daemon.load_hardware().fov_h_deg == 38.5

    # un Wiimote nuevo arranca con los valores guardados
    assert daemon.make_pipeline("bt:c").options.hardware.acc_x_sign == 1.0
    # reload vuelve a leer el archivo
    (tmp_path / "hardware.json").write_text('{"fov_h_deg": 40}')
    ask(daemon, workers, "reload", monkeypatch)
    assert workers[0].wm.pipeline.options.hardware.fov_h_deg == 40.0


def test_hwreport_command(daemon, tmp_path):
    import json
    r = daemon.handle_command('hwreport {"link": {"verdict": "ok", "note": "with spaces"}}')
    assert r["ok"]
    data = json.load(open(r["path"]))
    assert data["link"]["note"] == "with spaces" and "saved" in data
    assert not daemon.handle_command("hwreport [1, 2]")["ok"]
    assert not daemon.handle_command("hwreport")["ok"]


class EmptySlot(object):
    """Slot de la DolphinBar sin Wiimote: las escrituras fallan con EPIPE."""

    def __init__(self):
        self.present = False
        self.written = []

    def write(self, data):
        if not self.present:
            raise BrokenPipeError(32, "Broken pipe")
        self.written.append(bytes(data))
        return len(data)

    def readinto(self, buf):
        raise IOError("no more reports")

    def fileno(self):
        raise ValueError("no fd")

    def close(self):
        pass


def test_waiting_worker_answers_status(daemon, monkeypatch):
    """
    La DolphinBar expone siempre 4 slots: el worker de un slot vacio responde
    a P1 (paired: false) en vez de dejar `status` esperando el timeout.
    """
    import threading
    from dbar4gun import wiimote as W
    from tests.test_single_process import FakeGun

    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    daemon.class_wiimotedevice = W.WiiMoteDevice
    daemon.class_virtualgundevice = FakeGun
    slot = EmptySlot()
    parent, child = dbar4gun_module.Pipe()
    th = threading.Thread(target=daemon._create_virtualgun,
                          args=(slot, 1, "usb:x/input1", child, "/dev/hidraw3"))
    th.daemon = True
    th.start()

    parent.send((7, "status", []))
    assert parent.poll(2.0)
    rid, reply = parent.recv()
    assert rid == 7 and reply["paired"] is False and reply["virtualgun"] == 2
    assert reply["key"] == "usb:x/input1"

    # aparece el Wiimote: se empareja y sale del bucle de espera
    slot.present = True
    th.join(3.0)
    assert not th.is_alive()
    assert any(w[0] == 0x11 for w in slot.written)


def test_hw_ir_sensitivity_applies_and_overrides_service_option(daemon, monkeypatch, tmp_path):
    from dbar4gun.wiimote import IR_SENSITIVITY
    daemon.config.ir_sensitivity = "2"
    workers = [Worker(daemon, monkeypatch, 0, "bt:a")]
    wm = workers[0].wm
    wm.ir_sensitivity = daemon.ir_sensitivity(daemon.load_hardware())
    assert wm.ir_sensitivity == "2"                # sin hardware.json: el del servicio

    r = ask(daemon, workers, "hw ir_sensitivity 5", monkeypatch)
    assert r["ok"] and r["hardware"]["ir_sensitivity"] == "5"
    assert wm.ir_sensitivity == "5" and not wm.is_pair     # se reconfigura en el proximo read
    assert daemon.make_pipeline("bt:z").options.hardware.ir_sensitivity == "5"

    assert not ask(daemon, workers, "hw ir_sensitivity 7", monkeypatch)["ok"]
    r = ask(daemon, workers, "hw ir_sensitivity default", monkeypatch)
    assert r["ok"] and wm.ir_sensitivity == "2"
    assert set(IR_SENSITIVITY) >= {"2", "5"}


def test_silent_paired_worker_answers_quickly(daemon, monkeypatch):
    """
    Un Wiimote emparejado que deja de enviar reports (apagado en la DolphinBar,
    antes de los 10 s de E6): su worker responde a status sin esperar al
    timeout de lectura.
    """
    import os
    import threading
    import time
    from dbar4gun import wiimote as W
    from tests.test_single_process import FakeGun, PipeDevice

    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    daemon.class_wiimotedevice = W.WiiMoteDevice
    daemon.class_virtualgundevice = FakeGun
    class Dev(PipeDevice):
        gone = False

        def readinto(self, buf):
            if self.gone:
                raise IOError("device removed")     # termina el bucle del worker
            return PipeDevice.readinto(self, buf)

    dev = Dev()
    parent, child = dbar4gun_module.Pipe()
    th = threading.Thread(target=daemon._create_virtualgun,
                          args=(dev, 0, "usb:x/input0", child, "/dev/hidraw2"))
    th.daemon = True
    th.start()
    try:
        deadline = time.monotonic() + 3
        while not any(w[:1] == b"\x11" for w in dev.written) and time.monotonic() < deadline:
            threading.Event().wait(0.02)
        worst = 0.0
        for rid in range(5):
            t0 = time.monotonic()
            parent.send((rid, "status", []))
            assert parent.poll(2.0)
            got_rid, reply = parent.recv()
            worst = max(worst, time.monotonic() - t0)
            assert got_rid == rid and reply["paired"] is True
        assert worst < 0.3, worst
    finally:
        dev.gone = True
        os.write(dev.w, b"\x37" + bytes(21))
        th.join(3)
        assert not th.is_alive()
        os.close(dev.w)
        os.close(dev.r)


def test_status_does_not_reread_hardware_json(daemon, monkeypatch, tmp_path):
    workers = [Worker(daemon, monkeypatch, 0, "bt:a")]
    assert ask(daemon, workers, "hw fov 37", monkeypatch)["ok"]
    calls = []
    real = daemon.store

    def counting_store():
        st = real()
        orig = st.load_hardware
        st.load_hardware = lambda: calls.append(1) or orig()
        return st
    monkeypatch.setattr(daemon, "store", counting_store)
    for _ in range(5):
        assert ask(daemon, workers, "status", monkeypatch)["hardware"]["fov_h_deg"] == 37.0
    assert calls == []
    # un cambio a mano en el archivo se ve con reload
    (tmp_path / "hardware.json").write_text('{"fov_h_deg": 41}')
    ask(daemon, workers, "reload", monkeypatch)
    assert ask(daemon, workers, "status", monkeypatch)["hardware"]["fov_h_deg"] == 41.0


def test_periodic_ir_check_only_over_bluetooth(daemon, monkeypatch):
    """
    La comprobacion de la camara cada 5 s es para hid-wiimote (Bluetooth): con
    la DolphinBar no se escribe a la barra periodicamente.
    """
    from dbar4gun import wiimote as W
    from tests.fakes import FakeHidraw
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    daemon.class_wiimotedevice = W.WiiMoteDevice
    made = {}

    class StopLoop(Exception):
        pass

    def fake_create(io, pipeline, sens):
        wm = W.WiiMoteDevice(io, pipeline, sens)
        made[len(made)] = wm
        return wm
    daemon.class_wiimotedevice = fake_create

    class NoGun(object):
        def __init__(self, *a):
            raise StopLoop()
    daemon.class_virtualgundevice = NoGun
    for key in ("usb:usb-0000:00:14.0-3/input0", "bt:00:11:22:33:44:55"):
        with pytest.raises(StopLoop):
            daemon._create_virtualgun(FakeHidraw(), 0, key)
    assert made[0].ir_check is False and made[1].ir_check is True


def test_bluetooth_worker_keeps_virtualgun_until_the_wiimote_returns(daemon, monkeypatch):
    """
    Un Wiimote de Bluetooth se desconecta (el hidraw desaparece) y vuelve: el
    mismo worker sigue con la misma VirtualGun (mismo raton para el emulador).
    """
    import errno
    import os
    import threading
    import time
    from dbar4gun import wiimote as W
    from tests.test_single_process import FakeGun, PipeDevice

    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    daemon.class_wiimotedevice = W.WiiMoteDevice
    FakeGun.created = []
    daemon.class_virtualgundevice = FakeGun

    class BtDevice(PipeDevice):
        gone = False

        def readinto(self, buf):
            if self.gone:
                raise OSError(errno.ENODEV, "No such device")
            return PipeDevice.readinto(self, buf)

        def write(self, data):
            if self.gone:
                raise OSError(errno.ENODEV, "No such device")
            PipeDevice.write(self, data)

    first, second = BtDevice(), BtDevice()
    monkeypatch.setattr(daemon, "open_device", lambda path: (second.r, second))
    parent, child = dbar4gun_module.Pipe()
    th = threading.Thread(target=daemon._create_virtualgun,
                          args=(first, 4, "bt:00:11:22:33:44:55", child, "/dev/hidraw6"))
    th.daemon = True
    th.start()

    def ask_status(rid):
        parent.send((rid, "status", []))
        assert parent.poll(2.0)
        return parent.recv()[1]

    try:
        deadline = time.monotonic() + 3
        while not FakeGun.created and time.monotonic() < deadline:
            threading.Event().wait(0.02)
        assert ask_status(1)["paired"] is True

        first.gone = True                          # Bluetooth desconectado
        os.write(first.w, b"\x37" + bytes(21))     # despierta el select
        threading.Event().wait(0.3)
        st = ask_status(2)
        assert st["paired"] is False and th.is_alive()

        parent.send((3, "attach", ["/dev/hidraw7"]))
        assert parent.poll(2.0) and parent.recv() == (3, {"ok": True})
        deadline = time.monotonic() + 3
        while not any(w[:1] == b"\x13" for w in second.written) and time.monotonic() < deadline:
            threading.Event().wait(0.02)
        assert any(w[:1] == b"\x13" for w in second.written)   # IR configurado en el nuevo
        assert ask_status(4)["paired"] is True
        assert len(FakeGun.created) == 1                       # la misma VirtualGun
    finally:
        second.gone = True
        os.write(second.w, b"\x37" + bytes(21))
        threading.Event().wait(0.3)
        parent.close()                 # el daemon se va: el worker en espera termina
        th.join(3)
        assert not th.is_alive()
        for dev in (first, second):
            for fd in (dev.w, dev.r):
                try:
                    os.close(fd)
                except OSError:
                    pass


def test_daemon_routes_bluetooth_remove_and_add(daemon, monkeypatch):
    """remove de un Wiimote bt: no se mata su worker; add de la misma MAC: attach."""
    from dbar4gun import dbar4gun as D

    class Proc(object):
        killed = False

        def is_alive(self):
            return not self.killed

        def kill(self):
            self.killed = True

        def join(self, t=None):
            pass

    class Conn(object):
        def close(self):
            pass

    bt, usb = Proc(), Proc()
    daemon.workers = {"/dev/hidraw6": [Conn(), 4, "bt:aa"], "/dev/hidraw2": [Conn(), 0, "usb:x/input0"]}
    daemon.processes = {"/dev/hidraw6": bt, "/dev/hidraw2": usb}
    daemon.files = {"/dev/hidraw6": [None, None, 4], "/dev/hidraw2": [None, None, 0]}
    daemon.port[4] = daemon.port[0] = 0
    created, asked = [], []
    monkeypatch.setattr(daemon, "create_virtualgun", lambda path: created.append(path))
    monkeypatch.setattr(daemon, "_ask_workers",
                        lambda cmd, args=(), ports=None: asked.append((cmd, args, ports)) or [(4, {"ok": True})])
    monkeypatch.setattr(D, "device_key", lambda path: {"/dev/hidraw9": "bt:aa", "/dev/hidraw8": "bt:bb"}[path])

    daemon.handle_event("remove", "/dev/hidraw6")
    assert not bt.killed and daemon.port[4] == 0          # sigue vivo, puerto reservado
    assert "detached:bt:aa" in daemon.workers
    daemon.handle_event("remove", "/dev/hidraw2")          # la DolphinBar: como siempre
    assert usb.killed and daemon.port[0] == 1

    daemon.handle_event("add", "/dev/hidraw9")             # vuelve la misma MAC
    assert asked == [("attach", ["/dev/hidraw9"], [4])] and created == []
    assert daemon.workers["/dev/hidraw9"][1] == 4 and "detached:bt:aa" not in daemon.workers

    daemon.handle_event("add", "/dev/hidraw8")             # otro Wiimote: worker nuevo
    assert created == ["/dev/hidraw8"]


def test_accuracy_stores_gallery_analysis(daemon):
    from dbar4gun.core.calibration import CalibrationData
    daemon.workers = {"/dev/hidraw0": [None, 0, "bt:a"]}
    daemon.store().save("bt:a", CalibrationData())
    r = daemon.handle_command("accuracy 1 9.5 30 2.1 6.4 game=ptblank kind=scale "
                              "offset=0.40,-0.20 scale=4.8,5.1 residual=0.90 rings=0.80,2.10,-")
    assert r["ok"], r
    acc = daemon.store().history("bt:a")[-1]["accuracy"]
    a = acc["games"]["ptblank"]["analysis"]
    assert a["kind"] == "scale" and a["scale"] == [4.8, 5.1] and a["rings"] == [0.8, 2.1, None]
