"""
Calibrator de dbar4gun (necesita pygame: pip install dbar4gun[gui]).

La logica esta en dbar4gun.gui.logic (sin pygame) y el dibujo en dbar4gun.gui.app.
"""


class GUI(object):
    def __init__(self, width=0, height=0, port=35460, fullscreen=True,
                 socket_path=None, lang="en"):
        from dbar4gun.gui.app import App
        from dbar4gun.gui.i18n import set_lang
        from dbar4gun.control import SOCKET_PATH

        set_lang(lang)

        self.app = App(width, height, port, fullscreen, socket_path or SOCKET_PATH)

    def open(self):
        pass

    def loop(self):
        self.app.loop()

    def close(self):
        self.app.close()
