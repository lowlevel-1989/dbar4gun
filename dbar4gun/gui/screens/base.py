"""
Clases base de las pantallas.

- Screen: una pantalla (update y draw).
- GunScreen: pantalla de un Wiimote; Home vuelve al menu.
"""

from dbar4gun.gui.logic.wiimotes import BTN_HOME


class Screen(object):
    def __init__(self, app):
        self.app = app

    def update(self, now):
        pass

    def draw(self, surf):
        pass


class GunScreen(Screen):
    """Pantalla asociada a un Wiimote; Home vuelve al menu."""

    def __init__(self, app, virtualgun):
        super(GunScreen, self).__init__(app)
        self.vg = virtualgun

    @property
    def gun(self):
        return self.app.hub.guns.get(self.vg)

    @property
    def packet(self):
        g = self.gun
        return g.packet if g else None

    def back_on_home(self, now):
        g = self.gun
        if g is not None and g.was_pressed(BTN_HOME):
            self.app.go_menu()
            return True
        return False
