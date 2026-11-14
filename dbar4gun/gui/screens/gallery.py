"""
Shooting gallery: disparar a targets y ver el error en un mapa.
"""

import pygame

from dbar4gun.gui.draw import DARK, GREEN, GREY, RED, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.gallery import (
    aggregate_shots, gallery_analysis, gallery_done, gallery_margin, gallery_order,
    gallery_presets, gallery_targets, jitter_target, MAX_SHOT_SPREAD, preset_area,
    preset_game_size, RING_NAMES, shot_error, shot_spread, summarize, target_level,
)
from dbar4gun.gui.logic.wiimotes import BTN_A, BTN_B, BTN_DOWN, BTN_HOME, BTN_ONE, BTN_UP
from dbar4gun.gui.screens.base import GunScreen


# margen (fraccion del alto) que algunas TV recortan arriba y abajo (overscan)
SAFE_MARGIN = 0.03

# marcas del mapa de la shooting gallery (y de su leyenda)
MARK_R = 9


def draw_aim_mark(surf, pos, color):
    """El objetivo: la misma mira (circulo con cruz) a la que se dispara."""
    x, y = pos
    pygame.draw.circle(surf, color, pos, MARK_R, 2)
    pygame.draw.line(surf, color, (x - int(MARK_R * 1.6), y), (x + int(MARK_R * 1.6), y), 1)
    pygame.draw.line(surf, color, (x, y - int(MARK_R * 1.6)), (x, y + int(MARK_R * 1.6)), 1)


def draw_hit_mark(surf, pos, color):
    """Donde cayo el disparo (media): punto relleno con borde blanco."""
    pygame.draw.circle(surf, color, pos, MARK_R - 2)
    pygame.draw.circle(surf, WHITE, pos, MARK_R - 2, 1)


class GalleryScreen(GunScreen):
    """
    shooting gallery con mapa de errores; el resultado va al history.
    Antes de empezar se elige que simular: el area profile del servicio, un
    juego a pantalla completa o uno 4:3 con su resolucion (o un juego de la
    lista), para ver el error en los pixeles de ese juego.

    Se dispara por vueltas (todos los targets, en otro orden y un poco movidos)
    hasta que el resultado es fiable segun la punteria, como mucho MAX_ROUNDS.
    Home tras la primera vuelta termina con lo que haya.
    """

    def __init__(self, app, virtualgun):
        super(GalleryScreen, self).__init__(app, virtualgun)
        import random
        self.rng = random.Random()
        self.presets = gallery_presets()
        self.sel = 0
        self.preset = None
        self.targets = []
        self.errors = []
        self.summary = None
        self.analysis = None
        self.saved = None
        self.details = False        # pagina del analisis (boton 1)
        self.unsteady = False       # el ultimo disparo se repite

    def start(self):
        p = self.packet
        w, h = self.app.size
        self.preset = self.presets[self.sel]
        self.area = preset_area(self.preset, p.area if p else (0.0, 0.0, 1.0, 1.0), w / float(h))
        self.game = preset_game_size(self.preset, self.app.size)
        self.targets = gallery_targets(self.area, p.useful_zone if p else 0.85)
        self.shots = []
        self.rounds = 0
        self.aim = None
        self.errors = []
        self.summary = None
        self.analysis = None
        self.saved = None
        self.details = False
        self.unsteady = False
        self.new_round()

    def new_round(self):
        """Todos los targets en otro orden; el primero no repite el ultimo."""
        order = gallery_order(len(self.targets), 1, self.rng)
        if self.shots and len(order) > 1 and order[0] == self.shots[-1][0]:
            order[0], order[1] = order[1], order[0]
        self.round_order = order
        self.next_target()

    def next_target(self):
        cell = self.round_order[len(self.shots) % len(self.targets)]
        base = self.targets[cell]
        # la primera vuelta en su sitio; despues, un poco movidos
        pos = base if self.rounds == 0 else jitter_target(base, self.area, self.rng)
        self.current = (cell, pos)

    def estimate_aim(self):
        """Dispersion de la punteria (px de juego): con varias vueltas, la de los
        disparos al mismo target; con una, lo que el analisis no explica."""
        errors, aim = aggregate_shots(self.shots, len(self.targets), self.app.size, self.area, self.game)
        if aim is None:
            a = gallery_analysis(self.targets, errors, self.area, self.game)
            aim = a["residual"] if a else None
        return errors, aim

    def finish(self):
        self.errors, self.aim = self.estimate_aim()
        self.summary = summarize(self.errors)
        self.analysis = gallery_analysis(self.targets, self.errors, self.area, self.game)
        if self.analysis is not None:
            self.analysis["aim"] = round(self.aim, 2) if self.aim is not None else None
            margin = gallery_margin(self.aim, self.rounds)
            self.analysis["margin"] = round(margin, 2) if margin is not None else None
            self.analysis["rounds"] = self.rounds
            # si el error no supera claramente el margen, no se puede saber si
            # la calibracion falla: no se recomienda nada
            if margin is not None and self.analysis["kind"] != "good" and \
                    self.summary["mean_game"] <= 2.0 * margin:
                self.analysis["kind"] = "unknown"
                self.analysis["also"] = []
            # la dispersion de la punteria ya tiene su linea
            self.analysis["also"] = [k for k in self.analysis.get("also", []) if k != "random"]
        s = self.summary
        a = self.analysis or {}
        rings = a.get("rings", {})
        extra = ""
        if a:
            extra = " kind={} offset={:.2f},{:.2f} scale={:.1f},{:.1f} residual={:.2f} rings={} shots={}".format(
                a.get("kind"), a["offset"][0], a["offset"][1], a["scale"][0], a["scale"][1], a["residual"],
                ",".join("{:.2f}".format(rings[n]) if rings.get(n) is not None else "-" for n in RING_NAMES),
                len(self.shots))
            if a.get("aim") is not None:
                extra += " aim={:.2f}".format(a["aim"])
            if a.get("margin") is not None:
                extra += " margin={:.2f}".format(a["margin"])
        self.saved = self.app.control.send("accuracy {} {:.2f} {:.2f} {:.2f} {:.2f} game={}{}".format(
            self.vg, s["mean_tv"], s["max_tv"], s["mean_game"], s["max_game"], self.preset[0], extra))

    def update(self, now):
        g = self.gun
        if g is None:
            return
        shooting = self.preset is not None and self.summary is None
        if shooting and g.was_pressed(BTN_HOME) and self.rounds >= 1:
            # cortar: el resultado de lo que haya, con su margen
            self.finish()
            return
        if self.back_on_home(now):
            return
        if self.preset is None:
            if g.was_pressed(BTN_DOWN):
                self.sel = (self.sel + 1) % len(self.presets)
            if g.was_pressed(BTN_UP):
                self.sel = (self.sel - 1) % len(self.presets)
            if g.was_pressed(BTN_A):
                self.start()
            return
        if self.summary is None:
            if g.was_pressed(BTN_B):
                cell, target = self.current
                samples = g.samples_before_last_b()
                spread = shot_spread(samples)
                if spread is not None and spread > MAX_SHOT_SPREAD:
                    # tiron al disparar: no mide la calibracion, se repite
                    self.unsteady = True
                    return
                self.unsteady = False
                err = shot_error(samples, target, self.app.size, self.area, self.game)
                if err is None:
                    return
                self.shots.append((cell, err))
                if len(self.shots) % len(self.targets) == 0:
                    self.rounds += 1
                    _, aim = self.estimate_aim()
                    if gallery_done(aim, self.rounds):
                        self.finish()
                        return
                    self.new_round()
                else:
                    self.next_target()
        elif g.was_pressed(BTN_ONE):
            self.details = not self.details        # mapa <-> analisis
        elif g.was_pressed(BTN_A):
            self.preset = None                     # otra prueba
        elif g.was_pressed(BTN_B):
            self.start()                           # repetir la misma

    def preset_label(self, preset):
        key, area, gw, gh = preset[:4]
        if key == "profile":
            return t("gallery.preset.profile")
        if key == "full":
            return t("gallery.preset.full")
        name = preset[4] if len(preset) > 4 else None
        res = "{} {}x{}".format(area, gw, gh)
        return "{}  ({})".format(name, res) if name else res

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        if self.preset is None:
            app.text(surf, t("gallery.choose"), (w // 2, h // 12), app.font_big, WHITE, center=True)
            y = h // 6
            # ventana de la lista alrededor de la seleccion
            per_page = max(1, (h - y - h // 6) // (app.font.get_height() + 6))
            first = max(0, min(self.sel - per_page // 2, len(self.presets) - per_page))
            for i in range(first, min(len(self.presets), first + per_page)):
                color = YELLOW if i == self.sel else WHITE
                prefix = "> " if i == self.sel else "  "
                app.text(surf, prefix + self.preset_label(self.presets[i]), (w // 8, y), app.font, color)
                y += app.font.get_height() + 6
            app.text(surf, t("gallery.choose_hint"), (w // 2, h - app.font.get_height() * 2), app.font,
                     GREY, center=True)
            return
        # el area del juego simulado
        x0, y0, aw, ah = self.area
        pygame.draw.rect(surf, DARK, pygame.Rect(int(x0 * w), int(y0 * h), int(aw * w), int(ah * h)), 2)
        if self.summary is None:
            tx, ty = self.current[1]
            app.draw_target(surf, (int(tx * w), int(ty * h)), YELLOW)
            app.text(surf, t("gallery.target", i=len(self.shots) % len(self.targets) + 1,
                             n=len(self.targets), r=self.rounds + 1), (w // 2, h // 12),
                     app.font_big, WHITE, center=True)
            app.text(surf, self.preset_label(self.preset), (w // 2, h // 12 + app.font_big.get_height()),
                     app.font, GREY, center=True)
            if self.unsteady:
                app.text(surf, t("gallery.unsteady"),
                         (w // 2, h // 12 + app.font_big.get_height() + app.font.get_height() + 8),
                         app.font, YELLOW, center=True)
            app.text(surf, t("gallery.help_stop" if self.rounds >= 1 else "gallery.help"),
                     (w // 2, h - app.font.get_height() * 2), app.font, GREY, center=True)
            return
        s = self.summary
        if self.details:
            self.draw_details(surf)
            return
        # mapa de errores: target, impacto y color segun el error en px de juego
        # frente a lo que explica la punteria (target_level)
        margin = (self.analysis or {}).get("margin")
        colors = {"good": GREEN, "ok": YELLOW, "bad": RED}
        for (tx, ty), e in zip(self.targets, self.errors):
            if e is None:
                continue
            tv, game, d = e
            color = colors[target_level(game, margin)]
            a = (int(tx * w), int(ty * h))
            b = (int((tx + d[0]) * w), int((ty + d[1]) * h))
            pygame.draw.line(surf, color, a, b, 2)
            draw_aim_mark(surf, a, WHITE)
            draw_hit_mark(surf, b, color)
            app.text(surf, "{:.1f}".format(game), (a[0], a[1] + 24), app.font_small, color, center=True)
        # una linea arriba, en el margen (los targets empiezan al 10 % del alto)
        # textos dentro de la zona segura: hay TV que recortan los bordes (overscan)
        safe = int(h * SAFE_MARGIN)
        fs = app.font_small.get_height()
        app.text(surf, t("gallery.map_line", mg=s["mean_game"], xg=s["max_game"]), (w // 2, safe),
                 app.font_small, WHITE, center=True)
        self.draw_legend(surf, h - safe - fs - fs // 2 - 6)
        app.text(surf, t("gallery.map_hint"), (w // 2, h - safe),
                 app.font_small, GREY, center=True)

    def draw_legend(self, surf, y):
        """Leyenda del mapa en una linea: las dos marcas dibujadas y los colores."""
        app = self.app
        font = app.font_small
        icon = 2 * int(MARK_R * 1.6) + 10     # la cruz de la mira mas un hueco
        # (marca o None, texto, color)
        parts = [(draw_aim_mark, t("gallery.legend.target"), WHITE),
                 (draw_hit_mark, t("gallery.legend.hit"), WHITE),
                 (None, t("gallery.legend.number"), GREY),
                 (None, t("gallery.legend.good"), GREEN),
                 (None, t("gallery.legend.ok"), YELLOW),
                 (None, t("gallery.legend.bad"), RED)]
        gap = font.size("    ")[0]
        total = sum(font.size(s)[0] + (icon if m else 0) for m, s, _ in parts) + gap * (len(parts) - 1)
        x = (surf.get_width() - total) // 2
        cy = y + font.get_height() // 2
        for mark, s, color in parts:
            if mark is not None:
                mark(surf, (x + int(MARK_R * 1.6) + 2, cy), GREEN if mark is draw_hit_mark else color)
                x += icon
            app.text(surf, s, (x, y), font, color)
            x += font.size(s)[0] + gap

    def draw_details(self, surf):
        app = self.app
        w, h = surf.get_size()
        s = self.summary
        y = h // 12
        app.text(surf, self.preset_label(self.preset), (w // 2, y), app.font_big, WHITE, center=True)
        y += app.font_big.get_height() + 8
        a = self.analysis or {}
        if a.get("margin") is not None:
            app.text(surf, t("gallery.estimate", mg=s["mean_game"], m=a["margin"], xg=s["max_game"]),
                     (w // 2, y), app.font, WHITE, center=True)
        else:
            app.text(surf, t("gallery.result", m=s["mean_tv"], mg=s["mean_game"], x=s["max_tv"],
                             xg=s["max_game"]), (w // 2, y), app.font, WHITE, center=True)
        y += app.font.get_height() + 4
        app.text(surf, t("gallery.shots", n=len(self.shots), r=self.rounds), (w // 2, y), app.font_small,
                 GREY, center=True)
        y += app.font_small.get_height() + 12
        app.text(surf, t("gallery.by_distance"), (w // 2, y), app.font, GREY, center=True)
        y += app.font.get_height() + 6
        self.draw_analysis(surf, y)
        ok = self.saved and self.saved.get("ok")
        msg = t("gallery.saved") if ok else t("gallery.notsaved", e=(self.saved or {}).get("error", "?"))
        app.text(surf, msg, (w // 2, h - app.font.get_height() * 2), app.font, GREEN if ok else YELLOW,
                 center=True)

    def draw_analysis(self, surf, y):
        """Error segun la distancia al centro (barras) y que tipo de error domina."""
        a = self.analysis
        if not a:
            return
        app = self.app
        w, h = surf.get_size()
        font = app.font
        x = w // 2 - w // 8
        bar_max = w // 4
        top = max([v for v in a["rings"].values() if v is not None] or [1.0])
        scale = bar_max / max(top, 5.0)
        for name in RING_NAMES:
            v = a["rings"].get(name)
            label = t("gallery.ring." + name)
            app.text(surf, label, (x - font.size(label)[0] - 14, y), font, GREY)
            if v is not None:
                color = GREEN if v <= 2 else YELLOW if v <= 5 else RED
                pygame.draw.rect(surf, color, pygame.Rect(x, y + 4, max(2, int(v * scale)),
                                                          font.get_height() - 8))
                app.text(surf, "{:.1f} px".format(v), (x + int(v * scale) + 10, y), font, color)
            else:
                app.text(surf, "-", (x, y), font, GREY)
            y += font.get_height() + 8
        y += font.get_height()
        kind = a["kind"]
        color = GREEN if kind == "good" else YELLOW
        values = dict(o=(a["offset"][0] ** 2 + a["offset"][1] ** 2) ** 0.5,
                      sx=a["scale"][0], sy=a["scale"][1], r=a["residual"])
        lines = [t("gallery.kind." + kind, **values)]
        for other in a.get("also", []):
            lines.append(t("gallery.also." + other, **values))
        if a.get("aim") is not None:
            lines.append(t("gallery.aim", a=a["aim"]))
        if a.get("corners") and kind != "good":
            lines.append(t("gallery.corners"))
        for line in lines:
            for part in app.wrap(line, app.font, w - w // 6):
                app.text(surf, part, (w // 2, y), app.font, color, center=True)
                y += app.font.get_height() + 2
