"""
Menu principal: lista de pantallas y resumen de los Wiimotes conectados.
"""

from dbar4gun.gui.draw import CYAN, GREY, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.wiimotes import BTN_A, BTN_DOWN, BTN_HOME, BTN_UP
from dbar4gun.gui.screens.base import Screen
from dbar4gun.gui.screens.diagnostics import DiagnosticsScreen
from dbar4gun.gui.screens.gallery import GalleryScreen
from dbar4gun.gui.screens.hardware import HardwareScreen
from dbar4gun.gui.screens.history import HistoryScreen
from dbar4gun.gui.screens.install import InstallScreen
from dbar4gun.gui.screens.players import PlayersScreen
from dbar4gun.gui.screens.profiles import ProfilesScreen
from dbar4gun.gui.screens.reach import ReachScreen
from dbar4gun.gui.screens.tune import TuneScreen
from dbar4gun.gui.screens.wizard import WizardScreen


class MenuScreen(Screen):
    # primero el hardware check: antes de calibrar, que la barra, el IR y el
    # FOV esten bien
    ITEMS = ["menu.hardware", "menu.wizard", "menu.gallery", "menu.tune", "menu.reach",
             "menu.install", "menu.diag", "menu.players", "menu.profiles", "menu.history",
             "menu.exit"]
    # la pantalla que abre cada opcion (Exit cierra el calibrator)
    SCREENS = {"menu.hardware": HardwareScreen, "menu.wizard": WizardScreen,
               "menu.gallery": GalleryScreen, "menu.tune": TuneScreen,
               "menu.reach": ReachScreen, "menu.install": InstallScreen,
               "menu.diag": DiagnosticsScreen, "menu.players": PlayersScreen,
               "menu.profiles": ProfilesScreen, "menu.history": HistoryScreen}

    def __init__(self, app):
        super(MenuScreen, self).__init__(app)
        self.sel = 0

    def update(self, now):
        hub = self.app.hub
        if hub.any_pressed(BTN_DOWN, now):
            self.sel = (self.sel + 1) % len(self.ITEMS)
        if hub.any_pressed(BTN_UP, now):
            self.sel = (self.sel - 1) % len(self.ITEMS)
        if hub.any_pressed(BTN_HOME, now):
            self.app.running = False
            return
        gun = hub.first_pressed(BTN_A, now)
        if gun is None:
            return
        item = self.ITEMS[self.sel]
        if item == "menu.exit":
            self.app.running = False
        else:
            self.app.go(self.SCREENS[item](self.app, gun.virtualgun))

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        app.text(surf, t("title"), (w // 2, h // 10), app.font_big, WHITE, center=True)
        # la opcion la hace el Wiimote que pulsa A
        app.text(surf, t("menu.who"),
                 (w // 2, h // 10 + app.font_big.get_height() // 2 + app.font_small.get_height() // 2 + 4),
                 app.font_small, CYAN, center=True)
        guns = app.hub.active(app.now)
        if not guns:
            app.text(surf, t("waiting"), (w // 2, h // 4), app.font, YELLOW, center=True)
        y = h // 5
        for i, key in enumerate(self.ITEMS):
            color = YELLOW if i == self.sel else WHITE
            prefix = "> " if i == self.sel else "  "
            app.text(surf, prefix + t(key), (w // 4, y), app.font, color)
            y += app.font.get_height() + 6
        app.draw_gun_summary(surf, guns)
        app.text(surf, t("hint_menu"), (w // 2, h - app.font.get_height() * 2), app.font, GREY, center=True)
