"""
Driver nuevo para el simulador: WiiMoteDevice real sobre FakeHidraw (parser,
tracker, camera point, calibracion y perfil de area), calibrando con botones.
"""

from dbar4gun import wiimote as wiimote_module
from dbar4gun.core.gun import GunOptions, GunPipeline, BUTTON_A, BUTTON_B, BUTTON_PLUS

from tests.fakes import FakeHidraw


class NewDriver(object):
    """
    Sin options, el filter va desactivado: los tests de precision miden la
    calibracion; el filter se testea aparte.
    """

    def __init__(self, monkeypatch, options=None, calibration=None):
        monkeypatch.setattr(wiimote_module.time, "sleep", lambda s: None)
        self.io = FakeHidraw()
        self.pipeline = GunPipeline(options or GunOptions(smoothing_level=0), calibration)
        self.wm = wiimote_module.WiiMoteDevice(self.io, self.pipeline)
        # reports a 100 Hz
        self.t = 0.0
        self.wm.clock = self.tick
        self.wm.update_index(1)
        self.saved = []
        self.wm.on_save = lambda data, add_history=True: self.saved.append(data)
        self.area = self.pipeline.options.area

    def tick(self):
        self.t += 0.01
        return self.t

    def feed(self, report):
        """Cursor en coordenadas de pantalla (TV completa)."""
        self.io.reports.append(report)
        self.wm.read()
        return self.area.to_screen(*self.wm.get_cursor())

    def press(self, scene, buttons, roll_deg=0.0, at=(0.5, 0.5)):
        self.feed(scene.report(at[0], at[1], roll_deg, buttons))
        self.feed(scene.report(at[0], at[1], roll_deg, 0))

    def calibrate(self, scene, roll_deg=0.0, settle=8, start=True):
        """A+plus y una captura con B en cada target que pide la sesion."""
        if start:
            self.press(scene, BUTTON_A | BUTTON_PLUS, roll_deg)
        guard = 0
        while self.pipeline.calibrating:
            session = self.pipeline.session
            sx, sy = session.targets[session.step]
            for _ in range(settle):
                self.feed(scene.report(sx, sy, roll_deg))
            self.feed(scene.report(sx, sy, roll_deg, BUTTON_B))
            self.feed(scene.report(sx, sy, roll_deg))
            guard += 1
            assert guard < 10, "la calibracion no termina"
        assert self.saved, "la calibracion no se guardo"
