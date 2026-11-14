"""
History: calibraciones anteriores con fecha y precision; restaurar una.
"""

from dbar4gun.gui.draw import GREEN, GREY, RED, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.wiimotes import BTN_A, BTN_DOWN, BTN_UP
from dbar4gun.gui.screens.base import GunScreen


class HistoryScreen(GunScreen):
    """history de calibraciones con fecha y precision; restaurar."""

    def __init__(self, app, virtualgun):
        super(HistoryScreen, self).__init__(app, virtualgun)
        reply = app.control.send("history {}".format(virtualgun))
        self.entries = list(reversed(reply.get("history", []))) if reply.get("ok") else []
        self.error = None if reply.get("ok") else reply.get("error")
        self.sel = 0
        self.confirm = None
        self.message = None

    def update(self, now):
        g = self.gun
        if g is None or self.back_on_home(now) or not self.entries:
            return
        if g.was_pressed(BTN_DOWN):
            self.sel = (self.sel + 1) % len(self.entries)
            self.confirm = None
        if g.was_pressed(BTN_UP):
            self.sel = (self.sel - 1) % len(self.entries)
            self.confirm = None
        if g.was_pressed(BTN_A):
            entry = self.entries[self.sel]
            if self.confirm == self.sel:
                r = self.app.control.send("restore {} {}".format(self.vg, entry["index"]))
                self.message = (t("history.restored", i=entry["index"]), GREEN) if r.get("ok") else \
                    (r.get("error", "?"), RED)
                self.confirm = None
            else:
                self.confirm = self.sel
                self.message = (t("history.confirm", i=entry["index"]), YELLOW)

    def draw(self, surf):
        import datetime
        from dbar4gun.core.pointer import distance_from_separation

        app = self.app
        w, h = surf.get_size()
        app.text(surf, t("history.title", vg=self.vg), (w // 2, h // 12), app.font_big, WHITE, center=True)
        if not self.entries:
            app.text(surf, self.error or t("history.none"), (w // 2, h // 3), app.font, GREY, center=True)
        y = h // 6
        for i, e in enumerate(self.entries[:12]):
            ts = e.get("timestamp") or 0
            date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "?"
            sep = e.get("sep_ref") or 0
            dist = "{:.1f} m".format(distance_from_separation(sep)) if sep else "-"
            acc = e.get("accuracy")
            acc = "{:.1f} px ({:.1f} game)".format(acc["mean_tv"], acc.get("mean_game", 0)) if acc else "-"
            color = YELLOW if i == self.sel else WHITE
            app.text(surf, ("> " if i == self.sel else "  ") +
                     t("history.row", i=e["index"], date=date, dist=dist, acc=acc), (w // 10, y), app.font, color)
            y += app.font.get_height() + 6
        if self.message:
            app.text(surf, self.message[0], (w // 10, y + 10), app.font, self.message[1])
        app.text(surf, t("history.hint"), (w // 2, h - app.font.get_height() * 2), app.font_small, GREY,
                 center=True)
