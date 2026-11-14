"""Calibrator con pygame en modo headless (SDL dummy), alimentado por el simulador."""

import math
import os

import pytest

pygame = pytest.importorskip("pygame")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from dbar4gun.gui import app as A
from dbar4gun.gui import draw
from dbar4gun.gui.logic import calibration, gallery, hardware, wiimotes
from dbar4gun.gui.screens.diagnostics import DiagnosticsScreen
from dbar4gun.gui.screens.gallery import GalleryScreen
from dbar4gun.gui.screens.hardware import AIM_COUNTDOWN, HardwareScreen
from dbar4gun.gui.screens.install import InstallScreen
from dbar4gun.gui.screens.menu import MenuScreen
from dbar4gun.gui.screens.players import PlayersScreen
from dbar4gun.gui.screens.reach import ReachScreen
from dbar4gun.gui.screens.wizard import WizardScreen

from tests.sim.gui_harness import SimGun, SimSource, SimControl
from tests.sim.scene import Scene, TV


class Rig(object):
    def __init__(self, monkeypatch, n_guns=1, scene=None, store_dir=None, options=None):
        self.scene = scene or Scene(tv=TV(45))
        self.guns = [SimGun(monkeypatch, self.scene, vg, options) for vg in range(1, n_guns + 1)]
        self.control = SimControl(self.guns, store_dir)
        self.app = A.App(1280, 720, fullscreen=False, source=SimSource(self.guns),
                         control=self.control)
        self.t = 0.0

    def frames(self, n=1):
        for _ in range(n):
            self.t += 1 / 60.0
            self.app.step(self.t)

    def press(self, gun, button, frames_down=2):
        gun.buttons |= button
        self.frames(frames_down)
        gun.buttons &= ~button
        self.frames(2)

    def close(self):
        self.app.close()


@pytest.fixture
def rig(monkeypatch):
    r = Rig(monkeypatch)
    yield r
    r.close()


def go_menu_item(rig, gun, item):
    menu = rig.app.screen
    assert isinstance(menu, MenuScreen)
    while MenuScreen.ITEMS[menu.sel] != item:
        rig.press(gun, wiimotes.BTN_DOWN)
    rig.press(gun, wiimotes.BTN_A)


def shoot_gallery(rig, gun, screen):
    """El jugador dispara a cada target que muestra la galeria hasta el final."""
    while screen.summary is None:
        gun.aim = screen.current[1]
        rig.frames(8)
        rig.press(gun, wiimotes.BTN_B)


def capture_all(rig, gun, max_points=12):
    """El jugador apunta al target que muestra la GUI y dispara."""
    for _ in range(max_points):
        screen = rig.app.screen
        p = screen.packet
        if screen.state != "capture" or not (p and p.calibrating):
            break
        gun.aim = p.target
        rig.frames(8)
        rig.press(gun, wiimotes.BTN_B)


def test_wizard_full_flow(rig):
    gun = rig.guns[0]
    rig.frames(3)
    go_menu_item(rig, gun, "menu.wizard")
    wiz = rig.app.screen
    assert isinstance(wiz, WizardScreen) and wiz.state == "intro"

    rig.press(gun, wiimotes.BTN_A)
    assert wiz.state == "capture"
    assert any(l.startswith("calibrate 1 full targets=") for l in rig.control.lines)
    capture_all(rig, gun)
    rig.frames(2)
    assert gun.drv.saved, "la calibracion no se guardo"
    assert wiz.state == "verify", wiz.state

    gun.aim = wiz.center()
    rig.frames(10)
    rig.press(gun, wiimotes.BTN_B)
    assert wiz.state == "done" and wiz.error_px <= calibration.VERIFY_MAX_PX

    rig.press(gun, wiimotes.BTN_HOME)
    assert isinstance(rig.app.screen, MenuScreen)


def test_wizard_shows_capture_error(rig):
    gun = rig.guns[0]
    rig.frames(3)
    go_menu_item(rig, gun, "menu.wizard")
    wiz = rig.app.screen
    rig.press(gun, wiimotes.BTN_A)
    # disparar sin ver la barra
    gun.aim = (0.5, 3.0)
    rig.frames(5)
    rig.press(gun, wiimotes.BTN_B)
    assert wiz.message is not None and "No IR" in wiz.message[0]
    rig.press(gun, wiimotes.BTN_HOME)
    assert isinstance(rig.app.screen, MenuScreen)
    assert not gun.drv.pipeline.calibrating


def test_wizard_two_players(monkeypatch):
    rig = Rig(monkeypatch, n_guns=2)
    try:
        g1, g2 = rig.guns
        rig.frames(3)
        for gun in (g1, g2):
            # cada jugador entra en Calibrar desde el menu con su Wiimote
            go_menu_item(rig, gun, "menu.wizard")
            wiz = rig.app.screen
            assert wiz.vg == gun.vg
            rig.press(gun, wiimotes.BTN_A)
            capture_all(rig, gun)
            rig.frames(2)
            gun.aim = wiz.center()
            rig.frames(10)
            rig.press(gun, wiimotes.BTN_B)
            assert wiz.state == "done"
            other = g2 if gun is g1 else g1
            rig.press(other, wiimotes.BTN_A)       # el otro Wiimote no cambia de jugador
            assert rig.app.screen is wiz
            rig.press(gun, wiimotes.BTN_A)         # vuelve al menu
            assert isinstance(rig.app.screen, MenuScreen)
        assert g1.drv.saved and g2.drv.saved
    finally:
        rig.close()


def test_reach_screen(monkeypatch):
    rig = Rig(monkeypatch, scene=Scene(tv=TV(45), player=(0, 0, 1.8)))
    try:
        gun = rig.guns[0]
        rig.frames(3)
        go_menu_item(rig, gun, "menu.reach")
        screen = rig.app.screen
        y = 0.0
        while y < 1.2:
            gun.aim = (0.5, y)
            rig.frames(1)
            y += 0.02
        rig.press(gun, wiimotes.BTN_A)
        reach, uz, factor, dist = screen.result
        assert reach is not None and factor > 1 and dist > 1.8
        assert gun.drv.wm.pipeline is not None
        assert rig.app.hub.guns[1].reach == reach
        rig.press(gun, wiimotes.BTN_A)
        assert isinstance(rig.app.screen, MenuScreen)
    finally:
        rig.close()


@pytest.mark.parametrize("item,cls", [("menu.install", InstallScreen),
                                      ("menu.diag", DiagnosticsScreen)])
def test_other_screens_draw(rig, item, cls):
    gun = rig.guns[0]
    gun.drv.calibrate(rig.scene)
    rig.frames(3)
    go_menu_item(rig, gun, item)
    assert isinstance(rig.app.screen, cls)
    gun.aim = (0.3, 0.4)
    rig.frames(30)
    # perder un dot: la vista de camara dibuja el reconstruido
    gun.scene = Scene(tv=TV(45))
    rig.frames(5)
    rig.press(gun, wiimotes.BTN_HOME)
    assert isinstance(rig.app.screen, MenuScreen)


def test_menu_exit(rig):
    gun = rig.guns[0]
    rig.frames(2)
    rig.press(gun, wiimotes.BTN_HOME)
    assert not rig.app.running


def test_waiting_without_wiimotes(monkeypatch):
    app = A.App(800, 600, fullscreen=False, source=SimSource([]), control=SimControl([]))
    try:
        for i in range(3):
            app.step(i / 60.0)
        assert app.running
    finally:
        app.close()


def test_diagnostics_irmode_toggle(rig):
    gun = rig.guns[0]
    rig.frames(3)
    go_menu_item(rig, gun, "menu.diag")
    screen = rig.app.screen
    rig.press(gun, wiimotes.BTN_ONE)
    # el control simulado no conoce irmode: se muestra el error y no cambia
    assert rig.control.lines[-1] == "irmode extended"
    assert not screen.extended and screen.message
    rig.press(gun, wiimotes.BTN_HOME)


# ----------------------------------------------------------------------
@pytest.fixture
def rig_store(monkeypatch, tmp_path):
    r = Rig(monkeypatch, store_dir=tmp_path)
    yield r
    r.close()


def test_gallery_saves_accuracy(rig_store):
    rig = rig_store
    gun = rig.guns[0]
    gun.drv.calibrate(rig.scene)
    rig.frames(3)
    go_menu_item(rig, gun, "menu.gallery")
    screen = rig.app.screen
    assert screen.preset is None                    # primero se elige que simular
    rig.press(gun, wiimotes.BTN_A)                         # el area profile del servicio
    shoot_gallery(rig, gun, screen)
    s = screen.summary
    assert s is not None and s["mean_tv"] < 15 and s["mean_game"] < 4
    hist = rig.control.store.history("sim:1")
    assert hist[-1]["accuracy"]["mean_tv"] == pytest.approx(s["mean_tv"], abs=0.01)
    assert hist[-1]["accuracy"]["games"]["profile"]["mean_game"] == pytest.approx(s["mean_game"], abs=0.01)
    rig.press(gun, wiimotes.BTN_A)                         # otra prueba: vuelve a la lista
    assert screen.preset is None
    rig.press(gun, wiimotes.BTN_HOME)
    assert isinstance(rig.app.screen, MenuScreen)


def test_tune_applies_filter(monkeypatch):
    from dbar4gun.core.gun import GunOptions
    rig = Rig(monkeypatch, scene=Scene(tv=TV(45), noise_px=0.5, seed=3),
              options=GunOptions(smoothing_level=3))
    try:
        gun = rig.guns[0]
        gun.drv.calibrate(Scene(tv=TV(45)))
        rig.frames(3)
        go_menu_item(rig, gun, "menu.tune")
        screen = rig.app.screen
        rig.press(gun, wiimotes.BTN_A)
        assert screen.state == "still"
        rig.frames(int(3.2 * 60))
        assert screen.state == "move_intro" and screen.fc is not None
        rig.press(gun, wiimotes.BTN_A)
        i = 0
        while screen.state == "move":
            gun.aim = (0.5 + 0.3 * math.sin(i / 10.0), 0.5)
            rig.frames(1)
            i += 1
        assert screen.state == "result", screen.state
        rig.press(gun, wiimotes.BTN_A)
        assert screen.state == "applied"
        f = gun.drv.pipeline.filter_params()
        assert f["fc_min"] == pytest.approx(screen.fc, abs=1e-3)
        assert f["beta"] == pytest.approx(screen.beta, abs=1e-2)
    finally:
        rig.close()


def test_tune_rejects_no_motion(monkeypatch):
    rig = Rig(monkeypatch)
    try:
        gun = rig.guns[0]
        rig.frames(3)
        go_menu_item(rig, gun, "menu.tune")
        screen = rig.app.screen
        rig.press(gun, wiimotes.BTN_A)
        rig.frames(200)
        rig.press(gun, wiimotes.BTN_A)
        rig.frames(200)
        assert screen.state == "move_again"
    finally:
        rig.close()


def test_players_screen_hold_home(rig):
    gun = rig.guns[0]
    rig.frames(3)
    go_menu_item(rig, gun, "menu.players")
    assert isinstance(rig.app.screen, PlayersScreen)
    gun.buttons = wiimotes.BTN_B | wiimotes.BTN_PLUS
    rig.frames(5)
    gun.buttons = wiimotes.BTN_HOME
    rig.frames(20)
    assert isinstance(rig.app.screen, PlayersScreen)    # un toque de Home no sale
    rig.frames(60)
    assert isinstance(rig.app.screen, MenuScreen)
    gun.buttons = 0


def test_profiles_edit_and_apply(rig):
    gun = rig.guns[0]
    rig.frames(3)
    go_menu_item(rig, gun, "menu.profiles")
    screen = rig.app.screen
    rig.press(gun, wiimotes.BTN_RIGHT)          # preset: full -> 4:3
    assert screen.profile() == "4:3"
    rig.press(gun, wiimotes.BTN_DOWN)           # x0
    gun.buttons = wiimotes.BTN_RIGHT
    rig.frames(4)
    gun.buttons = 0
    rig.frames(2)
    assert screen.profile().startswith("custom:0.14")
    rig.press(gun, wiimotes.BTN_A)
    assert any(l.startswith("area custom:0.14") for l in rig.control.lines)
    assert any(l.startswith("usefulzone 0.850") for l in rig.control.lines)
    assert gun.drv.pipeline.options.area.name.startswith("custom:0.14")
    rig.press(gun, wiimotes.BTN_B)
    assert rig.control.lines[-1] == "save"
    rig.press(gun, wiimotes.BTN_HOME)


def test_history_restore(rig_store):
    rig = rig_store
    gun = rig.guns[0]
    gun.drv.calibrate(rig.scene)
    first_tx = gun.drv.pipeline.calibration.affine.tx
    gun.scene = Scene(tv=TV(45), bar_offset=(0.1, 0.0))
    gun.drv.calibrate(gun.scene)
    assert gun.drv.pipeline.calibration.affine.tx != pytest.approx(first_tx)
    rig.frames(3)
    go_menu_item(rig, gun, "menu.history")
    screen = rig.app.screen
    assert len(screen.entries) == 2 and screen.entries[0]["index"] == 1
    rig.press(gun, wiimotes.BTN_DOWN)            # la mas antigua
    rig.press(gun, wiimotes.BTN_A)
    assert screen.confirm == 1
    rig.press(gun, wiimotes.BTN_A)
    assert gun.drv.pipeline.calibration.affine.tx == pytest.approx(first_tx)
    rig.press(gun, wiimotes.BTN_HOME)



@pytest.mark.parametrize("mode,points", [(1, 2), (3, 4)])
def test_wizard_other_modes(monkeypatch, mode, points):
    from dbar4gun.core.gun import GunOptions
    rig = Rig(monkeypatch, options=GunOptions(calibration_mode=mode, smoothing_level=0))
    try:
        gun = rig.guns[0]
        rig.frames(3)
        go_menu_item(rig, gun, "menu.wizard")
        wiz = rig.app.screen
        rig.press(gun, wiimotes.BTN_A)
        line = [l for l in rig.control.lines if l.startswith("calibrate")][-1]
        assert len(line.split("targets=")[1].split(",")) == 2 * points
        capture_all(rig, gun)
        rig.frames(2)
        assert gun.drv.saved and gun.drv.saved[-1].mode == mode
        assert wiz.state == "verify"
    finally:
        rig.close()


def test_hardware_check_full_flow(monkeypatch):
    """
    El wizard de hardware con un Wiimote con el signo del
    acelerometro invertido: detecta el fallo, aplica la correccion y el FOV, y
    guarda el informe.
    """
    from dbar4gun.core.gun import GunOptions
    from dbar4gun.core.hardware import HardwareConfig
    opts = GunOptions(smoothing_level=0, hardware=HardwareConfig(acc_x_sign=-1.0))
    rig = Rig(monkeypatch, options=opts)
    gun = rig.guns[0]
    pipe = gun.drv.pipeline
    try:
        rig.frames(2)
        go_menu_item(rig, gun, "menu.hardware")
        hs = rig.app.screen
        assert isinstance(hs, HardwareScreen) and hs.step == "intro"

        rig.press(gun, wiimotes.BTN_A)                       # 1: conexion (inmediato)
        assert hs.step == "link" and hs.stage == "result"
        rig.press(gun, wiimotes.BTN_A)                       # 2: calidad IR
        assert hs.step == "ir"
        rig.press(gun, wiimotes.BTN_B)                       # se empieza disparando
        assert hs.stage == "run"
        assert any("3" in line for line, _ in hs.lines())   # cuenta atras
        rig.frames(int(AIM_COUNTDOWN * 60) - 10)
        assert hs.check.n == 0                        # nada medido durante la cuenta
        rig.frames(100)
        assert hs.stage == "result" and hs.results["ir"]["verdict"] == hardware.OK

        rig.press(gun, wiimotes.BTN_A)                       # 3: acelerometro
        assert hs.step == "acc"
        rig.press(gun, wiimotes.BTN_B)                       # tambien se empieza disparando
        assert hs.stage == "run"
        rig.frames(int(AIM_COUNTDOWN * 60))         # cuenta atras
        for i in range(240):
            gun.roll = 45.0 * math.sin(i / 120.0 * 2 * math.pi)
            rig.frames(1)
            if hs.stage == "result":
                break
        gun.roll = 0.0
        assert hs.results["acc"]["verdict"] == hardware.FAIL
        rig.press(gun, wiimotes.BTN_TWO)                     # aplicar
        assert pipe.tracker.acc_x_sign == 1.0, (hs.stage, hs.message, rig.control.lines[-3:])
        assert hs.results["acc"]["applied"]

        rig.press(gun, wiimotes.BTN_A)                       # 4: FOV (el jugador esta a 3.0 m)
        assert hs.step == "fov"
        assert hs.distance == 2.0                     # por defecto, 2 m
        for _ in range(10):                           # arriba: +0.1 m
            rig.press(gun, wiimotes.BTN_UP)
        rig.press(gun, wiimotes.BTN_UP)
        rig.press(gun, wiimotes.BTN_DOWN)
        assert hs.distance == 3.0 and hs.bar_width == 0.20
        gun.aim = (0.5, 0.0)
        rig.press(gun, wiimotes.BTN_B)
        rig.frames(int(AIM_COUNTDOWN * 60) + 60)
        r = hs.results["fov"]
        assert hs.stage == "result" and abs(r["fov_h_deg"] - 33.0) < 0.6, r
        rig.press(gun, wiimotes.BTN_TWO)
        assert abs(pipe.options.hardware.fov_h_deg - r["fov_h_deg"]) < 1e-6
        assert abs(rig.app.hardware.fov_h_deg - r["fov_h_deg"]) < 1e-6

        rig.press(gun, wiimotes.BTN_A)                       # 5: barra (apuntando al centro)
        assert hs.step == "bar"
        gun.aim = (0.5, 0.5)
        rig.press(gun, wiimotes.BTN_A)
        rig.frames(int(AIM_COUNTDOWN * 60) + 30)
        assert hs.results["bar"]["verdict"] == hardware.OK
        assert hs.results["bar"]["measured"] == "top"

        rig.press(gun, wiimotes.BTN_A)                       # 6: desconexion (saltar)
        assert hs.step == "disconnect"
        rig.press(gun, wiimotes.BTN_ONE)
        assert hs.step == "summary"
        rep = rig.control.report
        assert rep["results"]["acc"]["applied"] and rep["results"]["disconnect"]["skipped"]
        assert rep["hardware"]["acc_x_sign"] == 1.0
        assert rep["overall"] == hardware.FAIL               # el acelerometro estaba mal
        assert hs.report_path
        rig.press(gun, wiimotes.BTN_A)
        assert isinstance(rig.app.screen, MenuScreen)
    finally:
        rig.close()


def test_hardware_check_disconnect_step(monkeypatch):
    """El Wiimote se apaga (sin paquetes) y vuelve: el paso termina solo."""
    rig = Rig(monkeypatch)
    gun = rig.guns[0]
    try:
        rig.frames(2)
        go_menu_item(rig, gun, "menu.hardware")
        hs = rig.app.screen
        hs.enter(hs.STEPS.index("disconnect"), rig.t)
        rig.press(gun, wiimotes.BTN_A)
        assert hs.stage == "run"
        source = rig.app.source
        rig.app.source = SimSource([])                # apagado
        rig.frames(120)
        assert hs.check.state == "wait_on"
        rig.app.source = source                       # encendido
        rig.frames(3)
        assert hs.stage == "result"
        r = hs.results["disconnect"]
        assert r["verdict"] == hardware.OK and r["stopped"] == "stopped"
        rig.press(gun, wiimotes.BTN_A)
        assert hs.step == "summary"
    finally:
        rig.close()


def test_hardware_screens_draw(monkeypatch):
    rig = Rig(monkeypatch)
    gun = rig.guns[0]
    try:
        rig.frames(2)
        go_menu_item(rig, gun, "menu.hardware")
        hs = rig.app.screen
        for i in range(len(hs.STEPS)):
            hs.enter(i, rig.t)
            rig.frames(1)
            for stage in ("intro", "result"):
                hs.stage = stage
                rig.frames(1)
            for line, _ in hs.lines():
                assert not line.startswith("hw."), line
    finally:
        rig.close()


def test_wrap_long_text(rig):
    app = rig.app
    font = app.font
    long_path = "Report saved: /opt/retropie/configs/all/dbar4gun/" + "x" * 200 + "/hardware_report.json"
    parts = app.wrap(long_path, font, 400)
    assert len(parts) > 2
    assert all(font.size(p)[0] <= 400 for p in parts)
    assert "".join(parts).replace(" ", "") == long_path.replace(" ", "")
    assert app.wrap("short", font, 400) == ["short"]


def test_hardware_check_tries_ir_sensitivity(monkeypatch):
    """Un LED debil: el paso de calidad IR propone mas sensibilidad y la prueba."""
    rig = Rig(monkeypatch)
    gun = rig.guns[0]
    try:
        rig.frames(2)
        go_menu_item(rig, gun, "menu.hardware")
        hs = rig.app.screen
        hs.enter(hs.STEPS.index("ir"), rig.t)
        gun.drop = (1,)                                # el LED derecho no se ve
        rig.press(gun, wiimotes.BTN_A)
        rig.frames(int(AIM_COUNTDOWN * 60) + 90)
        r = hs.results["ir"]
        assert hs.stage == "result" and r["sensitivity"] == "higher", r
        assert r["ir_sensitivity"] == "marcan" and r["suggest"] == "4"
        assert "2:" in hs.result_hint("ir", r)
        rig.press(gun, wiimotes.BTN_TWO)
        assert gun.drv.wm.ir_sensitivity == "4"
        assert hs.stage == "run" and hs.ir_tried == ["4"]
        rig.frames(int(AIM_COUNTDOWN * 60) + 120)   # cuenta atras (y settle) + la medida
        r = hs.results["ir"]
        assert hs.stage == "result" and r["ir_sensitivity"] == "4" and r["tried"] == ["4"]
        assert any("hardware.json" in line for line, _ in hs.lines())
    finally:
        rig.close()


def test_reach_trail_is_drawn_incrementally(rig):
    rig.frames(2)
    rig.app.go(ReachScreen(rig.app, 1))
    rs = rig.app.screen
    rs.test.trail = [(0.25, 0.5, 2), (0.75, 0.5, 0)]
    rig.frames(1)
    surf = rig.app.surface
    w, h = surf.get_size()
    assert tuple(surf.get_at((int(0.25 * w), int(0.5 * h))))[:3] == draw.GREEN
    assert tuple(surf.get_at((int(0.75 * w), int(0.5 * h))))[:3] == draw.RED
    assert rs.trail_drawn == len(rs.test.trail) >= 2
    # puntos nuevos: solo se pintan esos
    rs.test.trail.append((0.5, 0.25, 1))
    rig.frames(1)
    assert tuple(surf.get_at((int(0.5 * w), int(0.25 * h))))[:3] == draw.YELLOW
    assert tuple(surf.get_at((int(0.25 * w), int(0.5 * h))))[:3] == draw.GREEN


@pytest.mark.parametrize("cur,expected", [
    ((3840, 2160), (1280, 720)),        # TV 4K: dibuja a 720p, la GPU escala
    ((1920, 1080), (1280, 720)),
    ((1280, 720), (1280, 720)),
    ((1024, 600), (1024, 600)),         # pantalla pequena: tal cual
    ((2560, 1600), (1152, 720)),        # otro aspecto: se conserva
    ((-1, -1), (0, 0)),                 # SDL no la sabe
])
def test_native_size_is_capped_at_720p(cur, expected):
    import types
    info = types.SimpleNamespace(current_w=cur[0], current_h=cur[1])
    assert A.native_size(info) == expected


def test_gallery_4_3_presets(rig_store):
    """
    Un juego 4:3 en la TV 16:9: los targets caen dentro del area 4:3 y el error
    se da en px de ese juego; varias pruebas se guardan por juego.
    """
    rig = rig_store
    gun = rig.guns[0]
    gun.drv.calibrate(rig.scene)
    rig.frames(3)
    go_menu_item(rig, gun, "menu.gallery")
    screen = rig.app.screen
    keys = [p[0] for p in screen.presets]
    results = {}
    for key in ("4:3-320x240", "4:3-640x480"):
        while screen.presets[screen.sel][0] != key:
            rig.press(gun, wiimotes.BTN_DOWN)
        rig.press(gun, wiimotes.BTN_A)
        x0, y0, w, h = screen.area
        assert abs(w - 0.75) < 1e-6 and abs(x0 - 0.125) < 1e-6      # 4:3 dentro de 16:9
        assert all(x0 <= tx <= x0 + w for tx, ty in screen.targets)
        shoot_gallery(rig, gun, screen)
        results[key] = screen.summary
        rig.press(gun, wiimotes.BTN_A)
    # el mismo error en TV son el doble de px en un juego de 640x480 que en uno de 320x240
    ratio = results["4:3-640x480"]["mean_game"] / results["4:3-320x240"]["mean_game"]
    assert 1.5 < ratio < 2.6, results
    games = rig.control.store.history("sim:1")[-1]["accuracy"]["games"]
    assert set(games) >= {"4:3-320x240", "4:3-640x480"}
    assert "full" in keys and "profile" in keys


def test_shot_error_uses_the_game_resolution():
    area = (0.125, 0.0, 0.75, 1.0)
    samples = [(0.5 + 0.75 / 320.0, 0.5)]            # 1 px de un juego de 320 de ancho
    tv, game, d = gallery.shot_error(samples, (0.5, 0.5), (1920, 1080), area, (320, 240))
    assert abs(game - 1.0) < 1e-6
    tv, game, d = gallery.shot_error(samples, (0.5, 0.5), (1920, 1080), area, (640, 480))
    assert abs(game - 2.0) < 1e-6


def _gallery_run(rig, gun, scene_after, key="4:3-320x240"):
    gun.drv.calibrate(rig.scene)
    gun.scene = scene_after
    rig.frames(3)
    go_menu_item(rig, gun, "menu.gallery")
    screen = rig.app.screen
    while screen.presets[screen.sel][0] != key:
        rig.press(gun, wiimotes.BTN_DOWN)
    rig.press(gun, wiimotes.BTN_A)
    shoot_gallery(rig, gun, screen)
    return screen


def test_gallery_diagnoses_a_moved_bar(monkeypatch, tmp_path):
    """Calibrar y mover la barra 10 cm: la galeria dice desplazamiento."""
    rig = Rig(monkeypatch, store_dir=tmp_path)
    try:
        screen = _gallery_run(rig, rig.guns[0], Scene(tv=TV(45), bar_offset=(0.10, 0.0)))
        a = screen.analysis
        assert a["kind"] == "offset", a
        hist = rig.control.store.history("sim:1")[-1]["accuracy"]["games"]["4:3-320x240"]
        assert hist["analysis"]["kind"] == "offset"
    finally:
        rig.close()


def test_gallery_diagnoses_scale_without_distance_compensation(monkeypatch, tmp_path):
    """Sin distance compensation, calibrar a 3 m y jugar a 2.5 m: error de escala."""
    from dbar4gun.core.gun import GunOptions
    rig = Rig(monkeypatch, store_dir=tmp_path,
              options=GunOptions(smoothing_level=0, distance_compensation=False))
    try:
        screen = _gallery_run(rig, rig.guns[0], Scene(tv=TV(45), player=(0.0, 0.0, 2.5)))
        a = screen.analysis
        assert a["kind"] == "scale", a
        assert a["rings"]["center"] < a["rings"]["edge"]
    finally:
        rig.close()


def test_gallery_separates_bad_aim_from_the_calibration(rig_store):
    """
    Una persona con mala punteria (cada disparo desviado al azar) y una buena
    calibracion: la galeria sigue hasta 3 vueltas, con los targets movidos,
    mide la punteria y no culpa a la calibracion.
    """
    import random
    rng = random.Random(7)
    rig = rig_store
    gun = rig.guns[0]
    gun.drv.calibrate(rig.scene)
    rig.frames(3)
    go_menu_item(rig, gun, "menu.gallery")
    screen = rig.app.screen
    while screen.presets[screen.sel][0] != "4:3-320x240":
        rig.press(gun, wiimotes.BTN_DOWN)
    rig.press(gun, wiimotes.BTN_A)
    px, py = 0.75 / 320, 1.0 / 240                 # 1 px de juego
    positions = set()
    while screen.summary is None:
        tx, ty = screen.current[1]
        positions.add((round(tx, 4), round(ty, 4)))
        gun.aim = (tx + rng.gauss(0, 6 * px), ty + rng.gauss(0, 6 * py))
        rig.frames(8)
        rig.press(gun, wiimotes.BTN_B)
    a = screen.analysis
    assert screen.rounds == 3 and len(screen.shots) == 45
    assert len(positions) > 30                     # los targets no salen en el mismo sitio
    # no culpa a la calibracion: "no se puede saber" (o bien), nunca recalibrar
    assert a["kind"] in ("unknown", "random", "good"), a
    assert 3.0 < a["aim"] < 10.0, a                # la dispersion de la punteria, medida
    assert a["margin"] == pytest.approx(a["aim"] / 3 ** 0.5, abs=0.01)


def test_gallery_stops_early_with_steady_aim(rig_store):
    """Con buen pulso bastan 2 vueltas (30 disparos), el minimo para medir la punteria."""
    rig = rig_store
    gun = rig.guns[0]
    gun.drv.calibrate(rig.scene)
    rig.frames(3)
    go_menu_item(rig, gun, "menu.gallery")
    screen = rig.app.screen
    rig.press(gun, wiimotes.BTN_A)
    shoot_gallery(rig, gun, screen)
    assert screen.rounds == 2 and len(screen.shots) == 30
    assert screen.analysis["margin"] is not None and screen.analysis["margin"] < 1.0


def test_gallery_home_finishes_after_the_first_round(rig_store):
    import random
    rng = random.Random(3)
    rig = rig_store
    gun = rig.guns[0]
    gun.drv.calibrate(rig.scene)
    rig.frames(3)
    go_menu_item(rig, gun, "menu.gallery")
    screen = rig.app.screen
    rig.press(gun, wiimotes.BTN_A)
    px = 0.75 / 320
    while screen.rounds < 1 or len(screen.shots) < 20:
        tx, ty = screen.current[1]
        gun.aim = (tx + rng.gauss(0, 8 * px), ty)
        rig.frames(8)
        rig.press(gun, wiimotes.BTN_B)
        assert screen.summary is None
    rig.press(gun, wiimotes.BTN_HOME)                     # cortar en la segunda vuelta
    assert screen.summary is not None and isinstance(rig.app.screen, GalleryScreen)
    assert len(screen.shots) == 20


def test_players_screen_only_the_opener_exits(monkeypatch):
    """En Jugadores y botones solo sale el Wiimote que abrio la pantalla."""
    rig = Rig(monkeypatch, n_guns=2)
    try:
        g1, g2 = rig.guns
        rig.frames(3)
        go_menu_item(rig, g1, "menu.players")
        screen = rig.app.screen
        assert isinstance(screen, PlayersScreen) and screen.vg == g1.vg
        g2.buttons |= wiimotes.BTN_HOME                  # el otro jugador prueba Home
        rig.frames(90)
        g2.buttons &= ~wiimotes.BTN_HOME
        rig.frames(2)
        assert rig.app.screen is screen
        g1.buttons |= wiimotes.BTN_HOME                  # el que la abrio, 1 s
        rig.frames(90)
        g1.buttons &= ~wiimotes.BTN_HOME
        assert isinstance(rig.app.screen, MenuScreen)
    finally:
        rig.close()


def test_camera_inset_does_not_cover_the_target(rig):
    """Con 4 puntos el target de abajo a la derecha cae donde va el recuadro de la camara."""
    w, h = rig.app.size
    default = rig.app.inset_rect()
    target = (int(0.9 * w), int(0.85 * h))
    assert default.collidepoint(target)                  # sin evitarlo, lo tapaba
    moved = rig.app.inset_rect(avoid=target)
    assert not moved.inflate(40, 40).collidepoint(target) and moved.x < w // 2
    assert rig.app.inset_rect(avoid=(w // 2, h // 2)) == default


def test_wizard_4_points_skips_the_ratio_check(monkeypatch):
    """
    Modo 3: la proporcion del mapa cambia por la pantalla (perspectiva) y daba
    avisos falsos; se pasa directo a la comprobacion del centro.
    """
    from dbar4gun.core.gun import GunOptions
    from tests.sim.scene import Scene, TV
    scene = Scene(tv=TV(45), player=(1.0, -0.6, 2.0))     # de lado y mas bajo: proporcion 1.11
    rig = Rig(monkeypatch, scene=scene, options=GunOptions(calibration_mode=3, smoothing_level=0))
    try:
        gun = rig.guns[0]
        rig.frames(3)
        go_menu_item(rig, gun, "menu.wizard")
        wiz = rig.app.screen
        rig.press(gun, wiimotes.BTN_A)
        capture_all(rig, gun)
        rig.frames(2)
        assert gun.drv.saved and gun.drv.saved[-1].mode == 3
        assert wiz.state == "verify"
    finally:
        rig.close()



def test_wizard_can_calibrate_again(rig):
    """Con el 1 se repite la calibracion en la comprobacion del centro y al terminar."""
    gun = rig.guns[0]
    rig.frames(3)
    go_menu_item(rig, gun, "menu.wizard")
    wiz = rig.app.screen
    rig.press(gun, wiimotes.BTN_A)
    capture_all(rig, gun)
    rig.frames(2)
    assert wiz.state == "verify"
    rig.press(gun, wiimotes.BTN_ONE)                     # repetir desde la comprobacion
    assert wiz.state == "capture"
    capture_all(rig, gun)
    rig.frames(2)
    gun.aim = wiz.center()
    rig.frames(10)
    rig.press(gun, wiimotes.BTN_B)
    assert wiz.state == "done"
    rig.press(gun, wiimotes.BTN_ONE)                     # repetir desde el final
    assert wiz.state == "capture"
    rig.press(gun, wiimotes.BTN_HOME)
