import json
import time
import os
import threading
import time
import types

import pytest

from dbar4gun.control import ControlServer, send_command, parse_command
from dbar4gun.core.calibration import CalibrationData, AffineMap
from dbar4gun.core.gun import BUTTON_A, BUTTON_B, BUTTON_PLUS
from dbar4gun.store import (
    CalibrationStore, key_from_uevent, parse_uevent, device_key, default_config_dir,
)
from dbar4gun.wiimote import WIIMOTE_LED_1, WIIMOTE_LED_4

from tests.fakes import make_wiimote
from tests.sim.driver import NewDriver
from tests.sim.scene import Scene


# ---------------------------------------------------------------- wiimote I/O
def test_rumble_pulse_without_blocking(monkeypatch):
    scene = Scene()
    drv = NewDriver(monkeypatch)
    io = drv.io
    t0 = time.monotonic()
    drv.calibrate(scene)
    assert time.monotonic() - t0 < 1.0, "la calibracion no debe bloquear"
    rumble = [w for w in io.written if w[0] == 0x10]
    assert rumble and rumble[0] == bytes([0x10, 0x01])


def test_rumble_bit_is_kept_in_other_reports(monkeypatch):
    wm, io = make_wiimote(monkeypatch)
    wm.set_rumble(True)
    wm.set_leds(WIIMOTE_LED_4)
    assert io.written[-1] == bytes([0x11, WIIMOTE_LED_4 | 0x01])
    wm.set_rumble(False)
    wm.set_leds(WIIMOTE_LED_4)
    assert io.written[-1] == bytes([0x11, WIIMOTE_LED_4])


def test_leds_restored_after_calibration(monkeypatch):
    """E12: al terminar la calibracion vuelven los LEDs del jugador."""
    drv = NewDriver(monkeypatch)
    drv.wm.update_index(1)
    drv.calibrate(Scene())
    leds = [w for w in drv.io.written if w[0] == 0x11]
    assert leds[-1][1] & 0xF0 == WIIMOTE_LED_1      # jugador 1, como en la Wii


def test_status_report_only_resends_drm(monkeypatch):
    """E8: un status report no reinicia el IR, solo reenvia el DRM, y da la bateria."""
    wm, io = make_wiimote(monkeypatch)
    io.reports.append(bytes([0x20, 0, 0, 0x0A, 0, 0, 0x64]) + bytes(15))
    wm.read()
    assert io.written == [bytes([0x12, 0x00, 0x37])]
    assert wm.battery == 50
    assert wm.enable_nunchuck


def test_status_dict(monkeypatch):
    drv = NewDriver(monkeypatch)
    drv.feed(Scene().report(0.5, 0.5))
    st = drv.wm.status()
    json.dumps(st)
    assert st["player"] == 1 and st["dots"] == 2
    assert 2.5 < st["distance_m"] < 3.5


def test_calibration_error_reported(monkeypatch):
    drv = NewDriver(monkeypatch)
    scene = Scene()
    drv.press(scene, BUTTON_A | BUTTON_PLUS)
    drv.feed(scene.report(0.1, 0.1, buttons=BUTTON_B, drop=(0, 1)))
    assert drv.wm.status()["last_calibration_error"] == "no_ir"


# ---------------------------------------------------------------- store (C11)
UEVENT_BT = """DRIVER=wiimote
HID_ID=0005:0000057E:00000306
HID_NAME=Nintendo RVL-CNT-01
HID_PHYS=00:1a:7d:da:71:13
HID_UNIQ=00:1F:32:AA:BB:CC
"""

UEVENT_USB = """DRIVER=hid-generic
HID_ID=0003:0000057E:00000306
HID_NAME=Nintendo RVL-CNT-01
HID_PHYS=usb-0000:01:00.0-1.3/input2
HID_UNIQ=
"""


def test_keys_from_uevent():
    assert key_from_uevent(parse_uevent(UEVENT_BT)) == "bt:00:1f:32:aa:bb:cc"
    assert key_from_uevent(parse_uevent(UEVENT_USB)) == "usb:usb-0000:01:00.0-1.3/input2"
    assert key_from_uevent({}) is None


def test_device_key_from_sysfs(tmp_path):
    d = tmp_path / "class" / "hidraw" / "hidraw4" / "device"
    d.mkdir(parents=True)
    (d / "uevent").write_text(UEVENT_BT)
    assert device_key("/dev/hidraw4", str(tmp_path)) == "bt:00:1f:32:aa:bb:cc"
    assert device_key("/dev/hidraw9", str(tmp_path)) == "hidraw:hidraw9"


def test_default_config_dir(tmp_path):
    assert default_config_dir(str(tmp_path / "missing")) == "/var/lib/dbar4gun"
    assert default_config_dir(str(tmp_path)) == str(tmp_path / "dbar4gun")
    other = tmp_path / "other"
    other.mkdir()
    platforms = [("retropie", str(tmp_path / "nope"), "dbar4gun"), ("x", str(other), "dbar4gun")]
    assert default_config_dir(platforms=platforms) == str(other / "dbar4gun")


def test_info_email_is_a_string():
    """R1: __email__ era una tupla por una coma final."""
    from dbar4gun import info
    assert isinstance(info.__email__, str)


def data(tx):
    return CalibrationData(affine=AffineMap(0.12, 0, 0, 0.2, tx, 0), sep_ref=0.07,
                           calibrated=True, timestamp=1.0)


def test_store_save_load_and_default(tmp_path):
    store = CalibrationStore(str(tmp_path / "cfg"))
    assert store.load("bt:x") is None
    store.save("bt:x", data(0.4))
    store.save("usb:y", data(0.6))
    assert store.load("bt:x").affine.tx == 0.4
    assert store.load("usb:y").affine.tx == 0.6
    # una clave nueva usa la ultima guardada (default)
    assert store.load("bt:new").affine.tx == 0.6
    content = json.loads((tmp_path / "cfg" / "calibration.json").read_text())
    assert set(content["devices"]) == {"bt:x", "usb:y", "default"}
    assert not [f for f in os.listdir(str(tmp_path / "cfg")) if ".tmp" in f]


def test_store_survives_corrupt_file(tmp_path):
    store = CalibrationStore(str(tmp_path))
    (tmp_path / "calibration.json").write_text("{not json")
    assert store.load("bt:x") is None
    store.save("bt:x", data(0.5))
    assert store.load("bt:x").affine.tx == 0.5


def test_store_concurrent_writers(tmp_path):
    store = CalibrationStore(str(tmp_path))
    errors = []

    def worker(i):
        try:
            for _ in range(10):
                CalibrationStore(str(tmp_path)).save("k{}".format(i), data(i / 10.0))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    for i in range(4):
        assert store.load("k{}".format(i)).affine.tx == i / 10.0


# ---------------------------------------------------------------- control (P1)
def test_control_roundtrip(tmp_path):
    path = str(tmp_path / "ctl.sock")
    seen = []

    def handler(line):
        seen.append(line)
        return {"ok": True, "echo": line}

    srv = ControlServer(handler, path)
    srv.bind()
    srv.start()
    try:
        assert oct(os.stat(path).st_mode & 0o777) == oct(0o666)
        assert send_command("status", path) == {"ok": True, "echo": "status"}
        assert send_command("area 4:3", path)["echo"] == "area 4:3"
    finally:
        srv.stop()
    assert not os.path.exists(path)


def test_parse_command():
    assert parse_command("Calibrate 2 quick") == ("calibrate", ["2", "quick"])
    assert parse_command("  ") == ("", [])


# ---------------------------------------------------------------- D9 (experimental)
def test_extended_ir_report(monkeypatch):
    from dbar4gun.core.parser import parse_ir_extended_raw

    def dot(x, y, size):
        return bytes([x & 0xFF, y & 0xFF, ((y >> 8) << 6) | ((x >> 8) << 4) | size])

    payload = dot(500, 400, 3) + dot(620, 410, 5) + bytes([0xFF] * 6)
    assert parse_ir_extended_raw(payload) == [(500, 400, 3), (620, 410, 5), None, None]

    wm, io = make_wiimote(monkeypatch)
    wm.set_ir_extended(True)
    assert bytes([0x12, 0x00, 0x33]) in io.written
    assert any(w[:7] == bytes([0x16, 0x04, 0xb0, 0x00, 0x33, 0x01, 0x03]) for w in io.written)
    io.reports.append(bytes([0x33, 0x00, 0x00, 0x80, 0x80, 0x9a]) + payload + bytes(4))
    wm.read()
    assert wm.ir_sizes[:2] == [3, 5] and wm.ir_raw[2] is None
    assert wm.pipeline.track.n_dots == 2


def test_irmode_needs_flag(tmp_path):
    import types as _t
    from dbar4gun.dbar4gun import Dbar4Gun
    d = Dbar4Gun(_t.SimpleNamespace(width=1920, height=1080, port=1, config_dir=str(tmp_path)), None, None, None)
    try:
        assert not d.handle_command("irmode extended")["ok"]
        d.config.experimental_ir_extended = True
        assert d.handle_command("irmode extended")["ok"]
        assert not d.handle_command("irmode bogus")["ok"]
    finally:
        d.sock.close()


# ---------------------------------------------------------------- C15
def test_default_ir_sensitivity_is_the_old_block(monkeypatch):
    """El bloque por defecto es byte a byte el que enviaba la v0.18.2."""
    wm, io = make_wiimote(monkeypatch)
    io.written.clear()
    wm.enable_ir()
    assert bytes(b"\x16\x04\xb0\x00\x00\x09\x00\x00\x00\x00\x00\x00\x90\x00\xC0\x00\x00\x00\x00\x00\x00\x00") in io.written
    assert bytes(b"\x16\x04\xb0\x00\x1a\x02\x40\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00") in io.written


@pytest.mark.parametrize("level,b1,b2", [("3", b"\x02\x00\x00\x71\x01\x00\xaa\x00\x64", b"\x63\x03"),
                                          ("cliff", b"\x00\x00\x00\x00\x00\x00\x90\x00\x41", b"\x40\x00")])
def test_ir_sensitivity_levels(monkeypatch, level, b1, b2):
    from dbar4gun import wiimote as W
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    from tests.fakes import FakeHidraw
    io = FakeHidraw()
    W.WiiMoteDevice(io, None, level)
    assert bytes(b"\x16\x04\xb0\x00\x00\x09") + b1 + bytes(7) in io.written
    assert bytes(b"\x16\x04\xb0\x00\x1a\x02") + b2 + bytes(14) in io.written


# ---------------------------------------------------------------- E6 / E7
class Clock(object):
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_short_report_is_ignored(monkeypatch):
    wm, io = make_wiimote(monkeypatch)
    io.reports.append(Scene().report(0.5, 0.5)[:10])
    wm.read()
    assert wm.pipeline.track is None


def test_read_timeout_does_not_block(monkeypatch):
    import os as _os
    from dbar4gun import wiimote as W
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    r, w = _os.pipe()
    import io as _io
    rio = _io.FileIO(r, "rb", closefd=True)

    class PipeIO(object):
        def __init__(self):
            self.written = []

        def fileno(self):
            return r

        def readinto(self, buf):
            return rio.readinto(buf)

        def write(self, data):
            self.written.append(bytes(data))

    dev = PipeIO()
    wm = W.WiiMoteDevice(dev)
    clock = Clock()
    wm.clock = clock
    t0 = time.monotonic()
    wm.read(timeout=0.05)
    assert time.monotonic() - t0 < 0.5
    # llega un report por el pipe: se procesa
    _os.write(w, Scene().report(0.5, 0.5))
    wm.read(timeout=0.5)
    assert wm.pipeline.track is not None and wm.pipeline.track.n_dots == 2
    # sin reports durante NO_REPORT_TIMEOUT: desconectado
    clock.t += W.NO_REPORT_TIMEOUT + 1
    wm.read(timeout=0.01)
    assert not wm.is_pair and bytes([0x11, 0xf0]) in dev.written
    _os.close(w)
    rio.close()


def test_repeated_identical_reports_mean_disconnected(monkeypatch):
    from dbar4gun import wiimote as W
    wm, io = make_wiimote(monkeypatch)
    wm.update_index(1)
    clock = Clock()
    wm.clock = clock
    rep = Scene().report(0.5, 0.5)
    for i in range(12):
        io.reports.append(rep)
        wm.read()
        clock.t += 1.0
    assert bytes([0x11, 0xf0]) in io.written
    # los reports normales (que cambian) no desconectan
    wm2, io2 = make_wiimote(monkeypatch)
    wm2.update_index(1)
    wm2.clock = clock
    for i in range(12):
        io2.reports.append(Scene().report(0.4 + i * 0.01, 0.5))
        wm2.read()
        clock.t += 1.0
    assert bytes([0x11, 0xf0]) not in io2.written


def test_other_data_report_resends_drm(monkeypatch):
    wm, io = make_wiimote(monkeypatch)
    io.reports.append(bytes([0x31, 0, 0, 0x80, 0x80, 0x9a]) + bytes(16))
    wm.read()
    assert bytes([0x12, 0x00, 0x37]) in io.written


def test_nunchuk_connected_before_pairing(monkeypatch):
    """
    Nunchuk ya enchufado al emparejar: el Wiimote no envia un status por si
    solo, asi que el driver lo pide (y lo repite si la primera peticion se
    pierde, como con la DolphinBar durante la configuracion del IR).
    """
    drv = NewDriver(monkeypatch)
    scene = Scene()
    status_req = bytes([0x15, 0x00])
    # la primera peticion se pierde
    for _ in range(50):
        drv.feed(scene.report(0.5, 0.5))
    reqs = [w for w in drv.io.written if w == status_req]
    assert 1 <= len(reqs) <= 2
    # llega el status con la extension conectada
    drv.io.reports.append(bytes([0x20, 0, 0, 0x0A, 0, 0, 0x64]) + bytes(15))
    drv.wm.read()
    assert drv.wm.enable_nunchuck
    n = len([w for w in drv.io.written if w == status_req])
    for _ in range(300):
        drv.feed(scene.report(0.5, 0.5))
    assert len([w for w in drv.io.written if w == status_req]) == n

    # reconexion (E6): se vuelve a preguntar
    drv.wm.is_pair = False
    drv.wm.update_index(1)
    for _ in range(5):
        drv.feed(scene.report(0.5, 0.5))
    assert len([w for w in drv.io.written if w == status_req]) == n + 1


def test_status_retries_are_bounded(monkeypatch):
    from dbar4gun import wiimote as W
    monkeypatch.setattr(W, "STATUS_RETRIES", 3)
    drv = NewDriver(monkeypatch)
    scene = Scene()
    # 9 s (reports identicos: a los 10 s E6 volveria a emparejar y a preguntar)
    for _ in range(900):
        drv.feed(scene.report(0.5, 0.5))
    reqs = [w for w in drv.io.written if w == bytes([0x15, 0x00])]
    assert len(reqs) == 3


def test_ir_camera_turned_off_is_enabled_again(monkeypatch):
    """
    Por Bluetooth, hid-wiimote apaga la camara IR al cerrarse sus evdev
    (medido: status LF 0x88 -> 0x80). El driver lo ve en el status y vuelve a
    configurar el IR.
    """
    drv = NewDriver(monkeypatch)
    scene = Scene()
    drv.feed(scene.report(0.5, 0.5))
    drv.io.reports.append(bytes([0x20, 0, 0, 0x08, 0, 0, 0x64]) + bytes(15))
    drv.wm.read()
    assert drv.wm.is_pair
    drv.io.written.clear()
    # camara apagada
    drv.io.reports.append(bytes([0x20, 0, 0, 0x00, 0, 0, 0x64]) + bytes(15))
    drv.wm.read()
    assert not drv.wm.is_pair
    drv.feed(scene.report(0.5, 0.5))
    assert drv.wm.is_pair
    assert bytes([0x13, 0x04]) in drv.io.written and bytes([0x1a, 0x04]) in drv.io.written
    assert bytes([0x12, 0x00, 0x37]) in drv.io.written


def test_status_polled_after_pairing(monkeypatch):
    """Tras el primer status, se vuelve a pedir cada IR_CHECK_INTERVAL s."""
    from dbar4gun.wiimote import IR_CHECK_INTERVAL
    drv = NewDriver(monkeypatch)
    scene = Scene(noise_px=0.3)   # reports distintos: E6 no reconecta
    drv.feed(scene.report(0.5, 0.5))
    drv.io.reports.append(bytes([0x20, 0, 0, 0x08, 0, 0, 0x64]) + bytes(15))
    drv.wm.read()
    req = bytes([0x15, 0x00])
    n = len([w for w in drv.io.written if w == req])
    steps = int(IR_CHECK_INTERVAL * 3 / 0.01) + 10
    for _ in range(steps):
        drv.feed(scene.report(0.5, 0.5))
    assert len([w for w in drv.io.written if w == req]) - n == 3


def test_reconnect_configures_ir_once(monkeypatch):
    """Al reconectar, la secuencia del IR se escribe una sola vez (antes, dos)."""
    drv = NewDriver(monkeypatch)
    scene = Scene()
    drv.feed(scene.report(0.5, 0.5))
    drv.io.written.clear()
    drv.wm.is_pair = False
    drv.feed(scene.report(0.5, 0.5))
    assert drv.wm.is_pair
    assert drv.io.written.count(bytes([0x13, 0x04])) == 1
    assert drv.io.written.count(bytes([0x12, 0x00, 0x37])) == 1


def test_ack_report_does_not_leak_trigger_during_calibration(monkeypatch):
    """
    Durante la calibracion, los ACK (0x22) de los LEDs/rumble traen los botones:
    B (gatillo) no debe llegar al juego, igual que con los reports 0x37.
    """
    from dbar4gun.core.gun import BUTTON_A, BUTTON_B, BUTTON_PLUS
    drv = NewDriver(monkeypatch)
    scene = Scene()
    drv.press(scene, BUTTON_A | BUTTON_PLUS)
    assert drv.pipeline.calibrating
    drv.io.reports.append(bytes([0x22, 0x00, BUTTON_B, 0x11, 0x00]) + bytes(17))
    drv.wm.read()
    assert not drv.wm.core_button & BUTTON_B
    assert drv.wm.raw_buttons & BUTTON_B          # la GUI si ve el boton
    # fuera de la calibracion pasa tal cual
    drv.pipeline.cancel_calibration()
    drv.io.reports.append(bytes([0x22, 0x00, BUTTON_B, 0x11, 0x00]) + bytes(17))
    drv.wm.read()
    assert drv.wm.core_button & BUTTON_B


def test_ir_reenable_is_rate_limited(monkeypatch):
    """Un status con la camara apagada una y otra vez no reconfigura cada 5 s."""
    from dbar4gun.wiimote import IR_REENABLE_INTERVAL
    drv = NewDriver(monkeypatch)
    scene = Scene(noise_px=0.3)
    drv.feed(scene.report(0.5, 0.5))
    off = bytes([0x20, 0, 0, 0x00, 0, 0, 0x64]) + bytes(15)

    def status_off():
        drv.io.reports.append(off)
        drv.wm.read()
        drv.feed(scene.report(0.5, 0.5))

    base = drv.io.written.count(bytes([0x13, 0x04]))     # el emparejamiento inicial
    status_off()
    first = drv.io.written.count(bytes([0x13, 0x04]))
    assert first == base + 1 and drv.wm.is_pair
    for _ in range(3):                      # otra vez a los 5 s: se espera
        for _ in range(500):
            drv.feed(scene.report(0.5, 0.5))
        status_off()
    assert drv.io.written.count(bytes([0x13, 0x04])) == first
    for _ in range(int(IR_REENABLE_INTERVAL / 0.01)):
        drv.feed(scene.report(0.5, 0.5))
    status_off()
    assert drv.io.written.count(bytes([0x13, 0x04])) == first + 1


def test_reconnect_attempts_back_off(monkeypatch):
    """
    Un Wiimote que no responde (apagado en la DolphinBar): los intentos de
    configurarlo se espacian de 0.2 s a 2 s. Antes eran uno por lectura
    (~10 por segundo), dias seguidos si el servicio quedaba encendido.
    """
    from dbar4gun import wiimote as W

    class DeadSlot(object):
        def __init__(self):
            self.attempts = 0

        def write(self, data):
            if data[:1] == b"\x13":
                self.attempts += 1
            raise BrokenPipeError(32, "Broken pipe")

        def readinto(self, buf):
            return 0

    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    dev = DeadSlot()
    wm = W.WiiMoteDevice(dev)
    clock = [0.0]
    wm.clock = lambda: clock[0]
    wm.next_reset = -1e9
    dev.attempts = 0
    for _ in range(200):                  # 20 s leyendo cada 0.1 s
        wm.read(timeout=None)
        clock[0] += 0.1
    assert not wm.is_pair
    assert 8 <= dev.attempts <= 14, dev.attempts     # antes: 200
    # el Wiimote vuelve: se empareja en el siguiente intento (<= 2 s)
    dev.write = lambda data: len(data)
    t0 = clock[0]
    while not wm.is_pair and clock[0] - t0 < 3:
        wm.read(timeout=None)
        clock[0] += 0.1
    assert wm.is_pair and clock[0] - t0 <= W.RESET_BACKOFF_MAX + 0.2
    assert wm.reset_backoff == W.RESET_BACKOFF_MIN


def _leds_written(io):
    return [w[1] & 0xF0 for w in io.written if w[:1] == b"\x11"]


def test_connection_signal_rumble_and_led_sweep(monkeypatch):
    """
    Al tomar el Wiimote (y al reconectar), vibracion corta y barrido de LEDs
    1-2-3-4-todos que acaba en el LED del jugador: la DolphinBar solo enciende
    un LED fijo, asi se ve que el driver lo tiene.
    """
    from dbar4gun.wiimote import (WIIMOTE_LED_1, WIIMOTE_LED_2, WIIMOTE_LED_3,
                                  WIIMOTE_LED_ALL, player_leds)
    drv = NewDriver(monkeypatch)
    scene = Scene(noise_px=0.3)
    drv.wm.update_index(1)
    drv.io.written.clear()
    drv.wm.announce()
    for _ in range(80):                         # 0.8 s de reports
        drv.feed(scene.report(0.5, 0.5))
    leds = _leds_written(drv.io)
    assert leds[:5] == [WIIMOTE_LED_1, WIIMOTE_LED_2, WIIMOTE_LED_3, WIIMOTE_LED_4, WIIMOTE_LED_ALL]
    assert leds[-1] == player_leds(1)
    rumble = [w for w in drv.io.written if w[:1] == b"\x10"]
    assert rumble[0][1] & 1 and not rumble[-1][1] & 1     # vibra y se apaga

    # reconexion (E6): otra vez la senal
    drv.io.written.clear()
    drv.wm.is_pair = False
    for _ in range(80):
        drv.feed(scene.report(0.5, 0.5))
    leds = _leds_written(drv.io)
    assert WIIMOTE_LED_ALL in leds and leds[-1] == player_leds(1)
    assert any(w[:1] == b"\x10" and w[1] & 1 for w in drv.io.written)


def test_no_connection_signal_on_deliberate_reconfiguration(monkeypatch):
    """Cambiar la IR sensitivity reconfigura la camara pero no vibra ni barre LEDs."""
    drv = NewDriver(monkeypatch)
    scene = Scene(noise_px=0.3)
    drv.wm.update_index(1)
    drv.feed(scene.report(0.5, 0.5))
    drv.io.written.clear()
    drv.wm.set_ir_sensitivity("4")
    for _ in range(80):
        drv.feed(scene.report(0.5, 0.5))
    assert any(w[:1] == b"\x13" for w in drv.io.written)       # se reconfiguro
    assert not any(w[:1] == b"\x10" and w[1] & 1 for w in drv.io.written)
    assert len(set(_leds_written(drv.io))) <= 1


def test_no_connection_signal_during_calibration(monkeypatch):
    from dbar4gun.core.gun import BUTTON_A, BUTTON_PLUS
    drv = NewDriver(monkeypatch)
    scene = Scene()
    drv.wm.update_index(1)
    drv.wm.announce()
    drv.press(scene, BUTTON_A | BUTTON_PLUS)          # empieza a calibrar
    assert drv.pipeline.calibrating and drv.wm.led_anim == []
