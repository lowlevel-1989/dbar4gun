"""Dobles de prueba compartidos (sin hardware)."""

from dbar4gun import wiimote as wiimote_module


class FakeHidraw(object):
    """hidraw falso: guarda lo que se escribe y entrega reports encolados."""

    def __init__(self, reports=None):
        self.written = []
        self.reports = list(reports or [])

    def write(self, data):
        self.written.append(bytes(data))
        return len(data)

    def readinto(self, buf):
        if not self.reports:
            raise IOError("no more reports")
        report = self.reports.pop(0)
        n = min(len(buf), len(report))
        buf[:n] = report[:n]
        return n

    def close(self):
        pass


def make_wiimote(monkeypatch, io=None, pipeline=None):
    """WiiMoteDevice real sobre un FakeHidraw, sin los sleep de enable_ir."""
    monkeypatch.setattr(wiimote_module.time, "sleep", lambda s: None)
    io = io or FakeHidraw()
    wm = wiimote_module.WiiMoteDevice(io, pipeline)
    io.written.clear()
    return wm, io
