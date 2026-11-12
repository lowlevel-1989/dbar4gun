"""
Calibrator (pygame, pantalla completa, se maneja solo con el Wiimote).

D1/D2 bucle a 60 fps que vacia el socket; D3/D4 paneles de camara y pantalla;
D9 diagnostico IR; D10 instalacion; D11 alcance; D12 wizard.
"""

import json
import math
import time

import pygame

from dbar4gun.control import send_command, SOCKET_PATH
from dbar4gun.core.hardware import HardwareConfig, next_ir_sensitivity
from dbar4gun.gui import logic as L
from dbar4gun.gui.i18n import t
from dbar4gun.protocol import DOT_VALID, DOT_RECONSTRUCTED, RAW_ABSENT, FLAG_CALIBRATED

BLACK = (0, 0, 0)
WHITE = (240, 240, 240)
GREY = (110, 110, 110)
DARK = (40, 40, 48)
GREEN = (80, 220, 120)
YELLOW = (240, 210, 70)
RED = (235, 80, 70)
CYAN = (90, 200, 220)
MAGENTA = (210, 110, 220)

# el calibrator dibuja a como mucho 720 lineas con el aspecto de la pantalla, y
# la GPU lo escala a pantalla completa (pygame SCALED): en una Pi 5 dibujar a 4K
# cuesta 16-28 ms por frame (no llega a 60 fps), a 720p 2-4 ms, y lo que se sube
# a la pantalla en cada frame es la imagen pequena. Mismo aspecto que la TV: los
# targets salen donde el driver los espera (un 640x480 con bandas en una TV 16:9
# los desplazaria)
MAX_NATIVE_HEIGHT = 720


def native_size(info):
    """
    (ancho, alto) en que dibuja el calibrator: el de la pantalla, o reducido a
    MAX_NATIVE_HEIGHT con su aspecto (una TV 4K: 1280x720, escalado por la GPU).
    (0, 0) si SDL no la sabe: entonces elige SDL.
    """
    w, h = getattr(info, "current_w", 0) or 0, getattr(info, "current_h", 0) or 0
    if w <= 0 or h <= 0:
        return 0, 0
    if h <= MAX_NATIVE_HEIGHT:
        return w, h
    return int(round(w * MAX_NATIVE_HEIGHT / float(h))), MAX_NATIVE_HEIGHT


# s que se espera a la camara IR tras cambiar su sensibilidad
IR_SETTLE = 1.5

GUN_COLORS = [(228, 116, 89), (96, 205, 131), (96, 198, 205), (197, 96, 205)]


class Control(object):
    """Cliente P1 (inyectable en los tests)."""

    def __init__(self, path=SOCKET_PATH):
        self.path = path

    def send(self, line):
        try:
            return send_command(line, self.path, timeout=1.5)
        except (OSError, ValueError) as e:
            return {"ok": False, "error": str(e)}


# ----------------------------------------------------------------------
class Screen(object):
    def __init__(self, app):
        self.app = app

    def update(self, now):
        pass

    def draw(self, surf):
        pass


class MenuScreen(Screen):
    ITEMS = ["menu.wizard", "menu.gallery", "menu.tune", "menu.reach", "menu.install",
             "menu.diag", "menu.hardware", "menu.players", "menu.profiles", "menu.history",
             "menu.exit"]

    def __init__(self, app):
        super(MenuScreen, self).__init__(app)
        self.sel = 0

    def update(self, now):
        hub = self.app.hub
        if hub.any_pressed(L.BTN_DOWN, now):
            self.sel = (self.sel + 1) % len(self.ITEMS)
        if hub.any_pressed(L.BTN_UP, now):
            self.sel = (self.sel - 1) % len(self.ITEMS)
        if hub.any_pressed(L.BTN_HOME, now):
            self.app.running = False
            return
        gun = hub.first_pressed(L.BTN_A, now)
        if gun is None:
            return
        item = self.ITEMS[self.sel]
        if item == "menu.exit":
            self.app.running = False
        elif item == "menu.wizard":
            self.app.go(WizardScreen(self.app, gun.virtualgun))
        elif item == "menu.reach":
            self.app.go(ReachScreen(self.app, gun.virtualgun))
        elif item == "menu.install":
            self.app.go(InstallScreen(self.app, gun.virtualgun))
        elif item == "menu.diag":
            self.app.go(DiagnosticsScreen(self.app, gun.virtualgun))
        else:
            screens = {"menu.gallery": GalleryScreen, "menu.tune": TuneScreen,
                       "menu.players": PlayersScreen, "menu.profiles": ProfilesScreen,
                       "menu.history": HistoryScreen, "menu.hardware": HardwareScreen}
            self.app.go(screens[item](self.app, gun.virtualgun))

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        app.text(surf, t("title"), (w // 2, h // 10), app.font_big, WHITE, center=True)
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
        if g is not None and g.was_pressed(L.BTN_HOME):
            self.app.go(MenuScreen(self.app))
            return True
        return False


class DiagnosticsScreen(GunScreen):
    """D9: dots en bruto, TL/TR, fuentes IR extra, bateria y Hz."""

    def __init__(self, app, virtualgun):
        super(DiagnosticsScreen, self).__init__(app, virtualgun)
        self.extended = False
        self.message = None

    def update(self, now):
        g = self.gun
        if g is not None and g.was_pressed(L.BTN_ONE):
            # tamano de los dots: modo IR extendido por P1 (experimental)
            mode = "basic" if self.extended else "extended"
            reply = self.app.control.send("irmode {}".format(mode))
            if reply.get("ok"):
                self.extended = not self.extended
                self.message = None
            else:
                self.message = reply.get("error", "?")
        if g is not None and g.was_pressed(L.BTN_HOME) and self.extended:
            self.app.control.send("irmode basic")
        self.back_on_home(now)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        rect = pygame.Rect(w // 20, h // 8, int(h * 0.7 * 4 / 3), int(h * 0.7))
        app.draw_camera(surf, rect, p, big=True)
        x = rect.right + w // 30
        y = rect.top
        for line, color in app.gun_lines(p, self.vg):
            app.text(surf, line, (x, y), app.font, color)
            y += app.font.get_height() + 6
        app.text(surf, t("diag.size_hint"), (x, y + 10), app.font_small, GREY)
        if self.message:
            app.text(surf, self.message, (x, y + 40), app.font_small, RED)
        app.text(surf, t("hint_back"), (w // 2, h - app.font.get_height() * 2), app.font, GREY, center=True)


class InstallScreen(GunScreen):
    """D10: distancia, barra nivelada y barra centrada."""

    def __init__(self, app, virtualgun):
        super(InstallScreen, self).__init__(app, virtualgun)
        self.next_status = 0.0

    def update(self, now):
        if self.back_on_home(now):
            return
        if now >= self.next_status:
            self.next_status = now + 1.0
            self.app.refresh_status()

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        lines = []

        d = L.distance_m(p, app.hardware)
        ref = L.reference_distance_m(p, app.hardware)
        if d is None:
            lines.append((t("distance_na"), GREY))
        elif ref:
            close = abs(d - ref) <= 0.15 * ref
            lines.append((t("distance_ref", d=d, r=ref), GREEN if close else YELLOW))
        else:
            lines.append((t("distance", d=d), WHITE))

        tilt = L.bar_tilt_deg(p)
        if tilt is None:
            lines.append((t("level_na"), GREY))
        else:
            ok = abs(tilt) <= 2.0
            lines.append((t("level_ok") if ok else t("level", v=tilt), GREEN if ok else YELLOW))
        if p is not None and not math.isnan(p.roll):
            lines.append((t("roll", v=p.roll), GREY))

        status = self.gun.status if self.gun else {}
        pos = L.bar_position(status) if status.get("calibrated") else None
        if pos is None:
            lines.append((t("center_na"), GREY))
        else:
            off = (pos[0] - 0.5) * 100.0
            lines.append((t("center", x=off), GREEN if abs(off) <= 3 else YELLOW))
            # la barra segun la calibracion
            bx, by = int(pos[0] * w), int(max(0.0, min(1.0, pos[1])) * h)
            pygame.draw.line(surf, CYAN, (bx - w // 20, by), (bx + w // 20, by), 6)

        y = h // 5
        for text, color in lines:
            app.text(surf, text, (w // 10, y), app.font_big, color)
            y += app.font_big.get_height() + 12

        # nivel: linea de la barra girada segun la inclinacion medida
        if tilt is not None:
            cx, cy, r = w // 2, int(h * 0.72), w // 6
            a = math.radians(tilt)
            pygame.draw.line(surf, GREY, (cx - r, cy), (cx + r, cy), 2)
            pygame.draw.line(surf, GREEN if abs(tilt) <= 2 else YELLOW,
                             (cx - r * math.cos(a), cy + r * math.sin(a)),
                             (cx + r * math.cos(a), cy - r * math.sin(a)), 6)
        app.draw_camera(surf, app.inset_rect(), p)
        app.text(surf, t("hint_back"), (w // 2, h - app.font.get_height() * 2), app.font, GREY, center=True)


class ReachScreen(GunScreen):
    """D11: rastro verde/amarillo/rojo y distancia recomendada."""

    def __init__(self, app, virtualgun):
        super(ReachScreen, self).__init__(app, virtualgun)
        self.test = L.ReachTest(L.bar_on_top(self.packet))
        self.done = False
        self.result = None
        # al terminar el barrido la barra suele estar fuera de vista
        self.distance = None
        # el rastro se pinta en su propia superficie, solo los puntos nuevos
        # (redibujar miles de circulos por frame costaba ~10 ms en una Pi 5)
        self.trail_surf = None
        self.trail_drawn = 0

    def update(self, now):
        if self.back_on_home(now):
            return
        g = self.gun
        if g is None:
            return
        if not self.done:
            for p in g.frame_packets:
                self.test.add(p)
                d = L.distance_m(p, self.app.hardware)
                if d:
                    self.distance = d
            if g.was_pressed(L.BTN_A):
                self.finish()
        elif g.was_pressed(L.BTN_A):
            self.app.go(MenuScreen(self.app))

    def finish(self):
        self.done = True
        reach = self.test.reach()
        p = self.packet
        g = self.gun
        if g is not None:
            g.reach = reach
        uz = p.useful_zone if p else 0.85
        factor, dist = L.recommend_distance(self.distance, reach, uz)
        self.result = (reach, uz, factor, dist)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        app.draw_screen_overlay(surf, p)
        colors = {2: GREEN, 1: YELLOW, 0: RED}
        trail = self.test.trail
        if self.trail_surf is None or self.trail_surf.get_size() != (w, h) or \
                self.trail_drawn > len(trail):
            self.trail_surf = pygame.Surface((w, h))
            self.trail_surf.set_colorkey(BLACK)
            self.trail_drawn = 0
        for x, y, n in trail[self.trail_drawn:]:
            pygame.draw.circle(self.trail_surf, colors[n], (int(x * w), int(y * h)), 5)
        self.trail_drawn = len(trail)
        surf.blit(self.trail_surf, (0, 0))
        if not self.done:
            app.text(surf, t("reach.help"), (w // 2, h // 12), app.font_big, WHITE, center=True)
        else:
            reach, uz, factor, dist = self.result
            y = h // 12
            if reach is None:
                app.text(surf, t("reach.none"), (w // 2, y), app.font_big, RED, center=True)
            else:
                app.text(surf, t("reach.result", r=reach * 100, u=uz * 100), (w // 2, y),
                         app.font_big, WHITE, center=True)
                y += app.font_big.get_height() + 10
                if factor <= 1.0:
                    msg, color = t("reach.ok"), GREEN
                elif dist:
                    msg, color = t("reach.move", d=dist, f=factor), YELLOW
                else:
                    msg, color = t("reach.move_nod", f=factor), YELLOW
                app.text(surf, msg, (w // 2, y), app.font_big, color, center=True)
        app.draw_camera(surf, app.inset_rect(), p)


class WizardScreen(GunScreen):
    """D12: wizard de calibracion."""

    def __init__(self, app, virtualgun):
        super(WizardScreen, self).__init__(app, virtualgun)
        self.state = "intro"
        self.message = None
        self.seen_calibrating = False
        self.error_px = None
        self.ratio = None

    def start(self):
        p = self.packet
        g = self.gun
        reach = g.reach if g else None
        status = self.app.refresh_status().get(self.vg, {})
        if status.get("mode_option") == 0:
            self.message = (t("wiz.failed", e="calibration disabled (--calibration 0)"), RED)
            return
        points = {1: 2, 3: 4}.get(status.get("mode_option"), 3)
        if points == 2:
            # modo 1: centro y arriba a la izquierda (escala y offset por eje)
            x0, y0, aw, ah = p.area if p else (0, 0, 1, 1)
            targets = [(x0 + 0.5 * aw, y0 + 0.5 * ah), (x0 + 0.1 * aw, y0 + 0.1 * ah)]
        else:
            targets = L.adaptive_targets(p.area if p else (0, 0, 1, 1), p.useful_zone if p else 0.85,
                                         reach, L.bar_on_top(p), points)
        flat = ",".join("{:.4f},{:.4f}".format(x, y) for x, y in targets)
        reply = self.app.control.send("calibrate {} full targets={}".format(self.vg, flat))
        if not reply.get("ok") or self.vg not in reply.get("started", []):
            self.message = (t("wiz.failed", e=reply.get("error", "?")), RED)
            return
        self.state = "capture"
        self.message = None
        self.seen_calibrating = False

    def update(self, now):
        g = self.gun
        if g is None:
            self.back_on_home(now)
            return
        p = g.packet

        if self.state == "intro":
            if self.back_on_home(now):
                return
            if g.was_pressed(L.BTN_A):
                self.start()

        elif self.state == "capture":
            if g.was_pressed(L.BTN_HOME):
                self.app.control.send("cancel")
                self.app.go(MenuScreen(self.app))
                return
            if p is None:
                return
            if p.calibrating:
                self.seen_calibrating = True
                if p.error:
                    self.message = (t("wiz.err." + p.error), RED)
                elif g.was_pressed(L.BTN_B):
                    self.message = None
            elif self.seen_calibrating:
                if p.has(FLAG_CALIBRATED):
                    self.check_geometry()
                else:
                    # cancelada (A+minus en el Wiimote)
                    self.state = "intro"

        elif self.state == "geometry":
            if g.was_pressed(L.BTN_A):
                self.state = "intro"
                self.start()
            elif g.was_pressed(L.BTN_HOME):
                self.state = "verify"

        elif self.state == "verify":
            if g.was_pressed(L.BTN_HOME):
                self.state = "done"
            elif g.was_pressed(L.BTN_B):
                samples = g.samples_before_last_b()
                self.error_px = L.verify_error_px(samples, self.center(), self.app.size)
                if self.error_px is not None and self.error_px <= L.VERIFY_MAX_PX:
                    self.state = "done"
                else:
                    self.state = "verify_bad"

        elif self.state == "verify_bad":
            if g.was_pressed(L.BTN_A):
                self.start()
            elif g.was_pressed(L.BTN_B):
                self.state = "verify"
            elif g.was_pressed(L.BTN_HOME):
                self.state = "done"

        elif self.state == "done":
            if g.was_pressed(L.BTN_HOME):
                self.app.go(MenuScreen(self.app))
                return
            # D12: varios jugadores, uno detras de otro
            other = self.app.hub.first_pressed(L.BTN_A, now)
            if other is not None and other.virtualgun != self.vg:
                self.app.go(WizardScreen(self.app, other.virtualgun))

    def check_geometry(self):
        status = self.app.refresh_status().get(self.vg, {})
        ok, ratio = L.geometry_check(status.get("scale_ratio"), status.get("screen_aspect", 16.0 / 9.0))
        self.ratio = (ratio, status.get("screen_aspect", 16.0 / 9.0))
        self.state = "verify" if ok else "geometry"

    def center(self):
        p = self.packet
        x0, y0, w, h = p.area if p else (0, 0, 1, 1)
        return (x0 + 0.5 * w, y0 + 0.5 * h)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        app.draw_screen_overlay(surf, p)
        cx = w // 2
        y = h // 3

        if self.state == "intro":
            app.text(surf, t("wiz.intro", vg=self.vg), (cx, y), app.font_big, WHITE, center=True)
            app.text(surf, t("wiz.intro2"), (cx, y + app.font_big.get_height() + 10), app.font, GREY, center=True)
        elif self.state == "capture" and p is not None and p.calibrating:
            tx, ty = int(p.target[0] * w), int(p.target[1] * h)
            app.draw_target(surf, (tx, ty), YELLOW)
            stab = L.stability(p.spread)
            color = {"good": GREEN, "ok": YELLOW, "bad": RED}.get(stab, GREY)
            radius = int(max(12, min(h // 4, p.spread * h * 0.6))) if p.spread >= 0 else 12
            pygame.draw.circle(surf, color, (tx, ty), radius, 4)
            app.text(surf, t("wiz.point", i=p.step + 1, n=p.total), (cx, h // 2), app.font_big, WHITE, center=True)
        elif self.state == "geometry":
            r, e = self.ratio
            app.text(surf, t("wiz.geometry_bad", r=r or 0, e=e), (cx, y), app.font, RED, center=True)
        elif self.state in ("verify", "verify_bad"):
            c = self.center()
            app.draw_target(surf, (int(c[0] * w), int(c[1] * h)), CYAN)
            if p is not None:
                pygame.draw.circle(surf, MAGENTA, (int(p.screen[0] * w), int(p.screen[1] * h)), 10, 3)
            if self.state == "verify":
                app.text(surf, t("wiz.verify"), (cx, h // 6), app.font_big, WHITE, center=True)
            else:
                app.text(surf, t("wiz.verify_bad", e=self.error_px or 0, m=L.VERIFY_MAX_PX),
                         (cx, h // 6), app.font, RED, center=True)
        elif self.state == "done":
            y0 = h // 3
            if self.error_px is not None:
                app.text(surf, t("wiz.verify_ok", e=self.error_px), (cx, y0 - app.font_big.get_height() - 10),
                         app.font, GREEN, center=True)
            app.text(surf, t("wiz.done", vg=self.vg), (cx, y0), app.font_big, GREEN, center=True)
            app.text(surf, t("wiz.next"), (cx, y0 + app.font_big.get_height() + 10), app.font, GREY, center=True)

        if self.message:
            app.text(surf, self.message[0], (cx, int(h * 0.8)), app.font, self.message[1], center=True)
        app.draw_camera(surf, app.inset_rect(), p)


class GalleryScreen(GunScreen):
    """
    D5: shooting gallery con mapa de errores; el resultado va al history.
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
        self.presets = L.gallery_presets()
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
        self.area = L.preset_area(self.preset, p.area if p else (0.0, 0.0, 1.0, 1.0), w / float(h))
        self.game = L.preset_game_size(self.preset, self.app.size)
        self.targets = L.gallery_targets(self.area, p.useful_zone if p else 0.85,
                                         bar_on_top=L.bar_on_top(p))
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
        order = L.gallery_order(len(self.targets), 1, self.rng)
        if self.shots and len(order) > 1 and order[0] == self.shots[-1][0]:
            order[0], order[1] = order[1], order[0]
        self.round_order = order
        self.next_target()

    def next_target(self):
        cell = self.round_order[len(self.shots) % len(self.targets)]
        base = self.targets[cell]
        # la primera vuelta en su sitio; despues, un poco movidos
        pos = base if self.rounds == 0 else L.jitter_target(base, self.area, self.rng)
        self.current = (cell, pos)

    def estimate_aim(self):
        """Dispersion de la punteria (px de juego): con varias vueltas, la de los
        disparos al mismo target; con una, lo que el analisis no explica."""
        errors, aim = L.aggregate_shots(self.shots, len(self.targets), self.app.size, self.area, self.game)
        if aim is None:
            a = L.gallery_analysis(self.targets, errors, self.area, self.game)
            aim = a["residual"] if a else None
        return errors, aim

    def finish(self):
        self.errors, self.aim = self.estimate_aim()
        self.summary = L.summarize(self.errors)
        self.analysis = L.gallery_analysis(self.targets, self.errors, self.area, self.game)
        if self.analysis is not None:
            self.analysis["aim"] = round(self.aim, 2) if self.aim is not None else None
            margin = L.gallery_margin(self.aim, self.rounds)
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
                ",".join("{:.2f}".format(rings[n]) if rings.get(n) is not None else "-" for n in L.RING_NAMES),
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
        if shooting and g.was_pressed(L.BTN_HOME) and self.rounds >= 1:
            # cortar: el resultado de lo que haya, con su margen
            self.finish()
            return
        if self.back_on_home(now):
            return
        if self.preset is None:
            if g.was_pressed(L.BTN_DOWN):
                self.sel = (self.sel + 1) % len(self.presets)
            if g.was_pressed(L.BTN_UP):
                self.sel = (self.sel - 1) % len(self.presets)
            if g.was_pressed(L.BTN_A):
                self.start()
            return
        if self.summary is None:
            if g.was_pressed(L.BTN_B):
                cell, target = self.current
                samples = g.samples_before_last_b()
                spread = L.shot_spread(samples)
                if spread is not None and spread > L.MAX_SHOT_SPREAD:
                    # tiron al disparar: no mide la calibracion, se repite
                    self.unsteady = True
                    return
                self.unsteady = False
                err = L.shot_error(samples, target, self.app.size, self.area, self.game)
                if err is None:
                    return
                self.shots.append((cell, err))
                if len(self.shots) % len(self.targets) == 0:
                    self.rounds += 1
                    _, aim = self.estimate_aim()
                    if L.gallery_done(aim, self.rounds):
                        self.finish()
                        return
                    self.new_round()
                else:
                    self.next_target()
        elif g.was_pressed(L.BTN_ONE):
            self.details = not self.details        # mapa <-> analisis
        elif g.was_pressed(L.BTN_A):
            self.preset = None                     # otra prueba
        elif g.was_pressed(L.BTN_B):
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
        p = self.packet
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
        for (tx, ty), e in zip(self.targets, self.errors):
            if e is None:
                continue
            tv, game, d = e
            color = GREEN if game <= 2 else YELLOW if game <= 5 else RED
            a = (int(tx * w), int(ty * h))
            b = (int((tx + d[0]) * w), int((ty + d[1]) * h))
            pygame.draw.circle(surf, GREY, a, 10, 1)
            pygame.draw.line(surf, color, a, b, 2)
            pygame.draw.circle(surf, color, b, 6)
            app.text(surf, "{:.1f}".format(game), (a[0], a[1] + 22), app.font_small, color, center=True)
        # una linea arriba, en el margen (los targets empiezan al 10 % del alto)
        app.text(surf, t("gallery.map_line", mg=s["mean_game"], xg=s["max_game"]), (w // 2, 6),
                 app.font_small, WHITE, center=True)
        app.text(surf, t("gallery.map_hint"), (w // 2, h - app.font_small.get_height() - 6),
                 app.font_small, GREY, center=True)

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
        for name in L.RING_NAMES:
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


class TuneScreen(GunScreen):
    """D13: auto-tune del One Euro (3 s quieto -> fc_min, 3 s moviendo -> beta)."""

    DURATION = 3.0
    MIN_MOTION_GAME = 300.0

    def __init__(self, app, virtualgun):
        super(TuneScreen, self).__init__(app, virtualgun)
        self.state = "still_intro"
        self.samples = []
        self.t0 = 0.0
        self.fc = self.jitter = self.beta = self.lag = None
        p = self.packet
        self.area = p.area if p else (0.0, 0.0, 1.0, 1.0)

    def dt(self):
        p = self.packet
        return 1.0 / p.hz if p is not None and p.hz > 10 else 0.01

    def update(self, now):
        g = self.gun
        if g is None:
            self.back_on_home(now)
            return
        if self.back_on_home(now):
            return
        st = self.state
        if st in ("still_intro", "move_intro", "move_again") and g.was_pressed(L.BTN_A):
            self.samples = []
            self.t0 = now
            self.state = "still" if st == "still_intro" else "move"
        elif st in ("still", "move"):
            self.samples += [p.screen for p in g.frame_packets if p.has(0x20)]
            if now - self.t0 >= self.DURATION and len(self.samples) > 30:
                if st == "still":
                    self.fc, self.jitter = L.choose_fc_min(self.samples, self.area, self.dt())
                    self.state = "move_intro"
                elif L.motion_amount(self.samples, self.area) < self.MIN_MOTION_GAME:
                    self.state = "move_again"
                else:
                    self.beta, self.lag = L.choose_beta(self.samples, self.fc, self.area, self.dt())
                    self.state = "result"
        elif st == "result" and g.was_pressed(L.BTN_A):
            reply = self.app.control.send("filter {} {:.3f} {:.2f}".format(self.vg, self.fc, self.beta))
            self.state = "applied" if reply.get("ok") else "result"

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        st = self.state
        text = {
            "still_intro": t("tune.still"),
            "move_intro": t("tune.move"),
            "move_again": t("tune.move_again"),
            "applied": t("tune.applied"),
        }.get(st)
        if st in ("still", "move"):
            text = t("tune.recording", s=max(0.0, self.DURATION - (app.now - self.t0)))
        if st in ("result", "applied") or (st.startswith("move") and self.fc):
            app.text(surf, t("tune.result", fc=self.fc or 0, j=self.jitter or 0, b=self.beta or 0,
                             l=self.lag or 0), (w // 2, h // 2), app.font, WHITE, center=True)
        if st == "result":
            text = t("tune.apply")
        if text:
            app.text(surf, text, (w // 2, h // 3), app.font_big, YELLOW, center=True)
        app.draw_target(surf, (w // 2, h // 2 - h // 6), GREY)
        p = self.packet
        if p is not None:
            pygame.draw.circle(surf, MAGENTA, (int(p.cursor[0] * w), int(p.cursor[1] * h)), 10, 3)
        app.draw_camera(surf, app.inset_rect(), p)


class PlayersScreen(GunScreen):
    """D14: mapa de jugadores y prueba de botones (teclas y combos emitidos)."""

    HOLD = 1.0

    def __init__(self, app, virtualgun):
        super(PlayersScreen, self).__init__(app, virtualgun)
        self.home_since = None

    def update(self, now):
        g = self.gun
        held = g is not None and g.packet is not None and g.packet.buttons & L.BTN_HOME
        if held:
            if self.home_since is None:
                self.home_since = now
            elif now - self.home_since >= self.HOLD:
                self.app.go(MenuScreen(self.app))
        else:
            self.home_since = None

    def draw(self, surf):
        from dbar4gun.wiimote import player_leds
        from dbar4gun.virtualgun import describe_outputs

        app = self.app
        w, h = surf.get_size()
        app.text(surf, t("players.title"), (w // 2, h // 12), app.font_big, WHITE, center=True)
        y = h // 6
        names = {L.BTN_A: "A", L.BTN_B: "B", L.BTN_ONE: "1", L.BTN_TWO: "2", L.BTN_PLUS: "+",
                 L.BTN_MINUS: "-", L.BTN_HOME: "Home", L.BTN_UP: "Up", L.BTN_DOWN: "Down",
                 L.BTN_LEFT: "Left", L.BTN_RIGHT: "Right"}
        for g in app.hub.active(app.now):
            p = g.packet
            mask = player_leds(p.index)
            leds = "".join("#" if mask & bit else "." for bit in (0x10, 0x20, 0x40, 0x80))
            col = GUN_COLORS[(g.virtualgun - 1) % 4]
            # RetroArch cuenta el mouse index desde 0; el driver, desde 1
            app.text(surf, t("players.row", leds=leds, vg=g.virtualgun, idx=max(0, p.index - 1)), (w // 10, y),
                     app.font, col)
            y += app.font.get_height() + 4
            pressed = [n for b, n in names.items() if p.buttons & b]
            app.text(surf, t("players.buttons", b=" ".join(pressed) or "-"), (w // 8, y), app.font_small, WHITE)
            y += app.font_small.get_height() + 2
            outs = describe_outputs(p.buttons, g.virtualgun - 1)
            app.text(surf, t("players.outputs", o=" ".join(outs) or "-"), (w // 8, y), app.font_small, CYAN)
            y += app.font_small.get_height() + 14
        app.text(surf, t("players.hint"), (w // 2, h - app.font.get_height() * 2), app.font, GREY, center=True)


class ProfilesScreen(GunScreen):
    """D15: previsualizar el area, editar un area custom y la useful zone."""

    PRESETS = ["full", "4:3", "custom"]
    FIELDS = ["preset", "x0", "y0", "w", "h", "useful_zone"]
    STEP = 0.005

    def __init__(self, app, virtualgun):
        super(ProfilesScreen, self).__init__(app, virtualgun)
        p = self.packet
        x0, y0, aw, ah = p.area if p else (0.0, 0.0, 1.0, 1.0)
        self.values = {"x0": x0, "y0": y0, "w": aw, "h": ah,
                       "useful_zone": p.useful_zone if p else 0.85}
        self.preset = "full" if (x0, y0, aw, ah) == (0.0, 0.0, 1.0, 1.0) else "custom"
        self.sel = 0
        self.message = None

    def profile(self):
        if self.preset != "custom":
            return self.preset
        v = self.values
        return "custom:{:.4f},{:.4f},{:.4f},{:.4f}".format(v["x0"], v["y0"], v["w"], v["h"])

    def preview_area(self):
        from dbar4gun.core.area import AreaProfile
        try:
            a = AreaProfile.parse(self.profile(), float(self.app.size[0]) / self.app.size[1])
            return (a.x0, a.y0, a.w, a.h)
        except ValueError:
            return None

    def change(self, d):
        f = self.FIELDS[self.sel]
        if f == "preset":
            i = self.PRESETS.index(self.preset)
            self.preset = self.PRESETS[(i + d) % len(self.PRESETS)]
            if self.preset != "custom":
                a = self.preview_area()
                if a:
                    self.values.update(x0=a[0], y0=a[1], w=a[2], h=a[3])
            return
        lo, hi = (0.3, 1.0) if f == "useful_zone" else (0.0, 1.0)
        self.values[f] = max(lo, min(hi, self.values[f] + d * self.STEP))
        if f != "useful_zone":
            self.preset = "custom"

    def update(self, now):
        g = self.gun
        if g is None or self.back_on_home(now):
            return
        if g.was_pressed(L.BTN_DOWN):
            self.sel = (self.sel + 1) % len(self.FIELDS)
        if g.was_pressed(L.BTN_UP):
            self.sel = (self.sel - 1) % len(self.FIELDS)
        if self.FIELDS[self.sel] == "preset":
            # el preset cambia con cada pulsacion
            if g.was_pressed(L.BTN_RIGHT):
                self.change(1)
            if g.was_pressed(L.BTN_LEFT):
                self.change(-1)
        elif g.packet is not None:
            # los valores cambian mientras se mantiene pulsado (cada frame)
            if g.packet.buttons & L.BTN_RIGHT:
                self.change(1)
            if g.packet.buttons & L.BTN_LEFT:
                self.change(-1)
        if g.was_pressed(L.BTN_A):
            r1 = self.app.control.send("area {}".format(self.profile()))
            r2 = self.app.control.send("usefulzone {:.3f}".format(self.values["useful_zone"]))
            ok = r1.get("ok") and r2.get("ok")
            self.message = (t("profiles.applied"), GREEN) if ok else \
                ((r1.get("error") or r2.get("error") or "?"), RED)
        if g.was_pressed(L.BTN_B):
            r = self.app.control.send("save")
            self.message = (t("profiles.saved", p=r.get("path", "")), GREEN) if r.get("ok") else \
                (r.get("error", "?"), RED)

    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        area = self.preview_area()
        if area:
            x0, y0, aw, ah = area
            rect = pygame.Rect(int(x0 * w), int(y0 * h), int(aw * w), int(ah * h))
            pygame.draw.rect(surf, CYAN, rect, 3)
            uy = int((y0 + self.values["useful_zone"] * ah) * h)
            pygame.draw.line(surf, YELLOW, (rect.left, uy), (rect.right, uy), 2)
        y = h // 6
        for i, f in enumerate(self.FIELDS):
            color = YELLOW if i == self.sel else WHITE
            if f == "preset":
                text = t("profiles.preset", v=self.profile())
            else:
                text = t("profiles.field", k=f, v=self.values[f])
            app.text(surf, ("> " if i == self.sel else "  ") + text, (w // 6, y), app.font, color)
            y += app.font.get_height() + 6
        if self.message:
            app.text(surf, self.message[0], (w // 6, y + 10), app.font, self.message[1])
        app.text(surf, t("profiles.hint"), (w // 2, h - app.font.get_height() * 2), app.font_small, GREY,
                 center=True)


class HistoryScreen(GunScreen):
    """D16: history de calibraciones con fecha y precision; restaurar."""

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
        if g.was_pressed(L.BTN_DOWN):
            self.sel = (self.sel + 1) % len(self.entries)
            self.confirm = None
        if g.was_pressed(L.BTN_UP):
            self.sel = (self.sel - 1) % len(self.entries)
            self.confirm = None
        if g.was_pressed(L.BTN_A):
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


class HardwareScreen(GunScreen):
    """
    Autodiagnostico del hardware, paso a paso. Cada paso mide algo,
    da un veredicto (verde/amarillo/rojo) y, si hace falta, ofrece aplicar el
    valor medido (`hw` por P1). Al final guarda el informe (`hwreport`).
    """

    STEPS = ["link", "ir", "acc", "fov", "bar", "disconnect", "summary"]
    COLORS = {L.OK: GREEN, L.WARN: YELLOW, L.FAIL: RED, L.NA: GREY}

    def __init__(self, app, virtualgun):
        super(HardwareScreen, self).__init__(app, virtualgun)
        self.results = {}
        self.index = -1          # -1 = intro
        self.message = None
        self.report_path = None
        self.status = {}
        self.fov_runs = []
        self.distance = 3.0
        self.bar_width = app.hardware.bar_width_m
        # niveles de IR sensitivity probados en el paso de calidad IR
        self.ir_tried = []
        # tras cambiar la IR sensitivity la camara se reconfigura (~1 s)
        self.settle_until = 0.0
        self.enter(-1, app.now)

    # ------------------------------------------------------------------
    @property
    def step(self):
        return self.STEPS[self.index] if 0 <= self.index < len(self.STEPS) else "intro"

    def enter(self, index, now):
        self.index = index
        self.stage = "intro"
        self.check = None
        self.message = None
        step = self.step
        if step == "link":
            self.status = self.app.refresh_status().get(self.vg, {})
            self.results["link"] = L.link_check(self.status, self.packet)
            self.stage = "result"
        elif step == "summary":
            self.save_report()

    def next(self, now):
        self.enter(self.index + 1, now)

    def gun_status(self):
        return self.app.refresh_status().get(self.vg, {})

    def gun_hardware(self):
        """Valores que usa ahora el pipeline de este Wiimote (status por P1)."""
        st = self.gun_status()
        if st.get("hardware"):
            return HardwareConfig.from_dict(st["hardware"])
        return self.app.hardware

    def apply(self, line):
        reply = self.app.control.send(line)
        if reply.get("ok"):
            self.app.refresh_status()
            self.message = (t("hw.applied"), GREEN)
        else:
            self.message = (reply.get("error", "?"), RED)
        return reply.get("ok", False)

    def save_report(self):
        status = self.app.status_reply or {}
        report = {
            "version": status.get("version"),
            "virtualgun": self.vg,
            "hardware": self.gun_hardware().to_dict(),
            "results": self.results,
            "overall": L.overall(self.results),
        }
        reply = self.app.control.send("hwreport " + json.dumps(report, sort_keys=True))
        self.report_path = reply.get("path") if reply.get("ok") else None
        if not reply.get("ok"):
            self.message = (reply.get("error", "?"), RED)

    # ------------------------------------------------------------------
    def update(self, now):
        g = self.gun
        step = self.step
        # en el paso de desconexion el Wiimote esta apagado: no hay botones
        if step == "disconnect" and self.stage == "run":
            self.check.update(g.frame_packets if g else [], now)
            if self.check.state in ("done", "timeout"):
                self.results["disconnect"] = self.check.result()
                self.stage = "result"
            return
        if g is None:
            return
        if g.was_pressed(L.BTN_HOME):
            self.app.go(MenuScreen(self.app))
            return

        if step == "intro":
            if g.was_pressed(L.BTN_A):
                self.next(now)
            return
        if step == "summary":
            if g.was_pressed(L.BTN_A):
                self.app.go(MenuScreen(self.app))
            return
        if self.stage == "result":
            self.update_result(g, now)
            return
        if step == "fov" and self.stage == "intro":
            if g.was_pressed(L.BTN_UP):
                self.distance = min(8.0, round(self.distance + 0.1, 2))
            if g.was_pressed(L.BTN_DOWN):
                self.distance = max(0.5, round(self.distance - 0.1, 2))
            if g.was_pressed(L.BTN_RIGHT):
                self.bar_width = min(0.6, round(self.bar_width + 0.01, 3))
            if g.was_pressed(L.BTN_LEFT):
                self.bar_width = max(0.05, round(self.bar_width - 0.01, 3))
        if self.stage == "intro":
            if g.was_pressed(L.BTN_ONE):
                self.results[step] = {"verdict": L.NA, "skipped": True}
                self.next(now)
            elif g.was_pressed(L.BTN_A):
                self.start_run(now)
            return
        # stage == "run"
        if now < self.settle_until:
            return
        for p in g.frame_packets:
            self.check.add(p)
        if self.check.ready():
            self.finish_run()

    def start_run(self, now, settle=0.0):
        step = self.step
        self.stage = "run"
        self.settle_until = now + settle
        if step == "ir":
            self.check = L.IRQuality()
        elif step == "acc":
            self.check = L.AccSignCheck()
        elif step == "fov":
            self.check = L.FovMeasure(self.distance, self.bar_width)
        elif step == "bar":
            self.check = L.BarSideCheck()
        elif step == "disconnect":
            self.check = L.DisconnectCheck(now)

    def finish_run(self):
        step = self.step
        if step == "acc":
            self.results["acc"] = self.check.result(self.gun_hardware().acc_x_sign)
        elif step == "fov":
            r = self.check.result()
            self.fov_runs.append(r)
            r = dict(r)
            r["runs"] = len(self.fov_runs)
            combined = L.combine_fov(self.fov_runs)
            if combined is not None:
                r["fov_h_deg"] = round(combined, 2)
            self.results["fov"] = r
        elif step == "ir":
            r = self.check.result()
            current = self.gun_status().get("ir_sensitivity")
            r["ir_sensitivity"] = current
            r["tried"] = list(self.ir_tried)
            if r.get("sensitivity"):
                r["suggest"] = next_ir_sensitivity(current, r["sensitivity"])
            self.results["ir"] = r
        else:
            self.results[step] = self.check.result()
        self.stage = "result"

    def update_result(self, g, now):
        step = self.step
        r = self.results.get(step, {})
        if step == "acc" and r.get("verdict") == L.FAIL and g.was_pressed(L.BTN_TWO):
            if self.apply("hw acc_x_sign {:g}".format(r["acc_x_sign"])):
                r["applied"] = True
        elif step == "fov" and r.get("fov_h_deg") and g.was_pressed(L.BTN_TWO):
            if self.apply("hw fov {:.2f} bar_width {:.3f}".format(r["fov_h_deg"], self.bar_width)):
                r["applied"] = True
        elif step == "ir" and r.get("suggest") and g.was_pressed(L.BTN_TWO):
            # C15: probar el nivel siguiente y volver a medir
            if self.apply("hw ir_sensitivity {}".format(r["suggest"])):
                self.ir_tried.append(r["suggest"])
                self.start_run(now, settle=IR_SETTLE)
        elif step == "fov" and g.was_pressed(L.BTN_B):
            # otra medida a otra distancia (se promedian)
            self.stage = "intro"
            self.message = None
        elif step in ("ir", "acc", "bar") and g.was_pressed(L.BTN_B):
            self.start_run(now)
        elif g.was_pressed(L.BTN_A):
            self.next(now)

    # ------------------------------------------------------------------
    def lines(self):
        """Texto de la pantalla actual: [(texto, color)]."""
        step = self.step
        out = []
        if step == "intro":
            out.append((t("hw.intro"), WHITE))
            for i, s_ in enumerate(self.STEPS[:-1]):
                out.append(("{}. {}".format(i + 1, t("hw.step." + s_)), GREY))
            out.append((t("hw.intro_hint"), YELLOW))
            return out
        if step == "summary":
            for s_ in self.STEPS[:-1]:
                r = self.results.get(s_, {"verdict": L.NA})
                out.append((u"{}: {}".format(t("hw.step." + s_), self.describe(s_, r)),
                            self.COLORS.get(r.get("verdict"), GREY)))
            if self.report_path:
                out.append((t("hw.saved", p=self.report_path), CYAN))
            out.append((t("hw.summary_hint"), GREY))
            return out

        title = "{}/{}  {}".format(self.index + 1, len(self.STEPS) - 1, t("hw.step." + step))
        out.append((title, WHITE))
        if self.stage == "intro":
            out.append((t("hw.{}.help".format(step)), WHITE))
            if step == "fov":
                out.append((t("hw.fov.values", d=self.distance, b=self.bar_width * 100), YELLOW))
            out.append((t("hw.start_hint"), GREY))
        elif self.stage == "run":
            out.append((t("hw.{}.run".format(step)), YELLOW))
            out.append((self.progress(), GREY))
        else:
            r = self.results.get(step, {})
            out.append((self.describe(step, r), self.COLORS.get(r.get("verdict"), GREY)))
            for line in self.advice(step, r):
                out.append((line, WHITE))
            out.append((self.result_hint(step, r), GREY))
        if self.message:
            out.append(self.message)
        return out

    def progress(self):
        c = self.check
        step = self.step
        if step == "ir":
            return t("hw.progress", n=c.n, m=c.MIN_PACKETS)
        if step == "acc":
            return t("hw.acc.progress", r=c.roll_range(), m=c.MIN_RANGE)
        if step == "fov":
            return t("hw.progress", n=len(c.focals), m=c.MIN_SAMPLES)
        if step == "bar":
            return t("hw.progress", n=len(c.ys), m=c.MIN_SAMPLES)
        if step == "disconnect":
            return t("hw.disconnect." + c.state)
        return ""

    def describe(self, step, r):
        v = r.get("verdict", L.NA)
        if r.get("skipped"):
            return t("hw.skipped")
        if v == L.NA and step != "link":
            return t("hw.na")
        if step == "link":
            kind = t("hw.link." + r.get("link", "unknown"))
            if r.get("slot"):
                kind += " " + t("hw.link.slot", n=r["slot"])
            bat = "{}%".format(r["battery"]) if r.get("battery") is not None else "--"
            return t("hw.link.result", k=kind, hz=r.get("hz", 0), b=bat)
        if step == "ir":
            j = r.get("jitter_px")
            if j is None:
                return t("hw.ir.result_nojitter", both=r.get("both", 0) * 100)
            return t("hw.ir.result", both=r.get("both", 0) * 100, j=j)
        if step == "acc":
            return t("hw.acc." + v, k=r.get("slope") or 0)
        if step == "fov":
            return t("hw.fov.result", f=r.get("fov_h_deg", 0), n=r.get("runs", 1),
                     s=r.get("spread_deg", 0))
        if step == "bar":
            m = r.get("measured")
            if m is None:
                return t("hw.bar.unclear")
            return t("hw.bar." + v, m=t("hw.bar." + m), c=t("hw.bar." + r.get("configured", "top")))
        if step == "disconnect":
            if v == L.OK:
                return t("hw.disconnect.ok", s=t("hw.disconnect." + (r.get("stopped") or "stopped")),
                         r=r.get("reconnect_s") or 0)
            return t("hw.disconnect.fail")
        return v

    def advice(self, step, r):
        out = []
        for note in r.get("notes", []):
            out.append(t("hw.note." + note))
        if step == "ir" and r.get("sensitivity"):
            out.append(t("hw.ir.sens_" + r["sensitivity"]))
        if step == "ir" and r.get("tried"):
            out.append(t("hw.ir.now", l=r.get("ir_sensitivity")))
        if step == "bar" and r.get("verdict") == L.FAIL:
            out.append(t("hw.bar.fix", m=r.get("measured")))
        if step == "fov" and r.get("applied") or step == "acc" and r.get("applied"):
            out.append(t("hw.applied"))
        return out

    def result_hint(self, step, r):
        if step == "ir" and r.get("suggest"):
            return t("hw.hint_apply_ir", l=r["suggest"], c=r.get("ir_sensitivity") or "?")
        if step == "acc" and r.get("verdict") == L.FAIL and not r.get("applied"):
            return t("hw.hint_apply_acc")
        if step == "fov" and not r.get("applied"):
            return t("hw.hint_fov")
        if step in ("ir", "acc", "bar"):
            return t("hw.hint_retry")
        return t("hw.hint_next")

    # ------------------------------------------------------------------
    def draw(self, surf):
        app = self.app
        w, h = surf.get_size()
        p = self.packet
        if self.step == "bar":
            # target en el centro de la TV
            app.draw_target(surf, (w // 2, h // 2), YELLOW)
        y = h // 10
        # el texto no debe tapar la vista de la camara (abajo a la derecha)
        max_w = w - w // 12 - w // 20
        for i, (text, color) in enumerate(self.lines()):
            font = app.font_big if i == 0 and self.step not in ("intro", "summary") else app.font
            for part in app.wrap(text, font, max_w):
                app.text(surf, part, (w // 12, y), font, color)
                y += font.get_height() + 4
            y += 6
        app.draw_camera(surf, app.inset_rect(), p)
        if self.step == "acc" and p is not None and not math.isnan(p.roll):
            app.text(surf, t("roll", v=p.roll), (w // 12, h - h // 6), app.font, GREY)


# ----------------------------------------------------------------------
class App(object):
    def __init__(self, width=0, height=0, port=35460, fullscreen=True, socket_path=SOCKET_PATH,
                 source=None, control=None, display=True):
        # solo pantalla y fuentes: pygame.init() abriria los joysticks, y por
        # Bluetooth el Wiimote es uno (hid-wiimote); al cerrarlos, el kernel
        # apaga la camara IR del Wiimote
        pygame.display.init()
        pygame.font.init()
        if display and not width and not height:
            width, height = native_size(pygame.display.Info())
        flags = pygame.FULLSCREEN if fullscreen else 0
        if display:
            self.surface = None
            if fullscreen and width and height:
                # sin cambiar el modo de video: la GPU escala la imagen pequena
                try:
                    self.surface = pygame.display.set_mode((width, height), flags | pygame.SCALED)
                except (pygame.error, AttributeError):
                    self.surface = None
            if self.surface is None:
                self.surface = pygame.display.set_mode((width, height), flags)
            pygame.display.set_caption(t("title"))
            pygame.mouse.set_visible(False)
        else:
            self.surface = pygame.Surface((width or 1280, height or 720))
        self.size = self.surface.get_size()
        h = self.size[1]
        self.font_small = pygame.font.Font(None, max(18, h // 36))
        self.font = pygame.font.Font(None, max(24, h // 24))
        self.font_big = pygame.font.Font(None, max(32, h // 14))

        self.source = source if source is not None else L.PacketSource(port)
        self.control = control if control is not None else Control(socket_path)
        self.hub = L.Hub()
        # FOV, signo del acelerometro y ancho de barra del daemon
        self.hardware = HardwareConfig()
        self.status_reply = {}
        self.screen = MenuScreen(self)
        self.running = True
        self.now = time.monotonic()
        self.clock = pygame.time.Clock()

    def go(self, screen):
        self.screen = screen
        # los flancos de este frame no deben pasar a la pantalla nueva
        for g in self.hub.guns.values():
            g.pressed = 0

    def refresh_status(self):
        reply = self.control.send("status")
        if reply.get("ok"):
            self.status_reply = reply
            if reply.get("hardware"):
                self.hardware = HardwareConfig.from_dict(reply["hardware"])
        out = {}
        for gun in reply.get("wiimotes", []) if reply.get("ok") else []:
            vg = gun.get("virtualgun")
            out[vg] = gun
            if vg in self.hub.guns:
                self.hub.guns[vg].status = gun
        return out

    # ------------------------------------------------------------------
    def step(self, now=None):
        """Un frame: vaciar el socket, actualizar y dibujar."""
        self.now = time.monotonic() if now is None else now
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
        self.hub.update(self.source.drain(), self.now)
        self.screen.update(self.now)
        self.surface.fill(BLACK)
        self.screen.draw(self.surface)

    def loop(self):
        while self.running:
            self.step()
            pygame.display.flip()
            self.clock.tick(60)

    def close(self):
        try:
            self.source.close()
        except Exception:
            pass
        pygame.quit()

    # ------------------------------------------------------------------
    # dibujo
    def text(self, surf, text, pos, font, color, center=False):
        img = font.render(text, True, color)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        surf.blit(img, r)

    def wrap(self, text, font, max_w):
        """Parte un texto en lineas que caben en max_w px (las palabras largas, por /)."""
        out = []
        line = ""
        for word in text.split(" "):
            cand = word if not line else line + " " + word
            if font.size(cand)[0] <= max_w:
                line = cand
                continue
            if line:
                out.append(line)
            line = word
            # una palabra que no cabe (una ruta): se corta por caracteres
            while font.size(line)[0] > max_w and len(line) > 1:
                cut = len(line)
                while cut > 1 and font.size(line[:cut])[0] > max_w:
                    cut -= 1
                out.append(line[:cut])
                line = line[cut:]
        if line:
            out.append(line)
        return out or [""]

    def inset_rect(self):
        w, h = self.size
        ih = h // 4
        iw = ih * 4 // 3
        return pygame.Rect(w - iw - 16, h - ih - 16, iw, ih)

    def draw_target(self, surf, pos, color):
        x, y = pos
        r = max(14, self.size[1] // 40)
        pygame.draw.circle(surf, color, pos, r, 3)
        pygame.draw.line(surf, color, (x - 2 * r, y), (x + 2 * r, y), 2)
        pygame.draw.line(surf, color, (x, y - 2 * r), (x, y + 2 * r), 2)

    def draw_screen_overlay(self, surf, p):
        """D4: area del perfil y useful zone."""
        if p is None:
            return
        w, h = surf.get_size()
        x0, y0, aw, ah = p.area
        rect = pygame.Rect(int(x0 * w), int(y0 * h), int(aw * w), int(ah * h))
        pygame.draw.rect(surf, DARK, rect, 2)
        if L.bar_on_top(p):
            uy = y0 + p.useful_zone * ah
        else:
            uy = y0 + (1 - p.useful_zone) * ah
        yy = int(uy * h)
        for x in range(rect.left, rect.right, 24):
            pygame.draw.line(surf, GREY, (x, yy), (x + 12, yy), 1)

    def draw_camera(self, surf, rect, p, big=False):
        """D3: vista de la camara 4:3 (dots en bruto, TL/TR, reconstruidos, extra)."""
        pygame.draw.rect(surf, DARK, rect)
        pygame.draw.rect(surf, GREY, rect, 1)
        if p is None:
            return
        rad = max(4, rect.height // 40)

        def to_px(u, v):
            return (int(rect.left + u / 1023.0 * rect.width), int(rect.top + v / 767.0 * rect.height))

        tracked = []
        for k, d in enumerate(p.dots):
            if d[2] & DOT_VALID:
                u = (1.0 - d[0]) * 1023.0
                v = 767.0 - d[1] * 767.0
                # el TL del espacio normalizado es el LED derecho (x invertida):
                # se etiqueta por el lado fisico, como lo ve el jugador
                tracked.append((to_px(u, v), bool(d[2] & DOT_RECONSTRUCTED), "R" if k == 0 else "L"))

        raw_seen = []
        for r in p.raw:
            if r[1] == RAW_ABSENT:
                continue
            pos = to_px(r[0], 767 - r[1])
            raw_seen.append((pos, r[2]))

        tracked_pos = [t_[0] for t_ in tracked if not t_[1]]
        for pos, size in raw_seen:
            extra = all(abs(pos[0] - q[0]) > 2 or abs(pos[1] - q[1]) > 2 for q in tracked_pos)
            pygame.draw.circle(surf, RED if extra else WHITE, pos, rad if not extra else rad + 2,
                               0 if not extra else 2)
            if big and size != 0xFF:
                # tamano del dot (IR extendido): un LED debil se ve mas pequeno
                self.text(surf, str(size), (pos[0], pos[1] + rad + 14), self.font_small, GREY,
                          center=True)

        if len(tracked) == 2:
            a, b = tracked[0][0], tracked[1][0]
            dashed = tracked[0][1] or tracked[1][1]
            self.line(surf, CYAN, a, b, dashed)
        font = self.font if big else self.font_small
        for pos, rec, label in tracked:
            if rec:
                pygame.draw.circle(surf, YELLOW, pos, rad + 3, 2)
            self.text(surf, label, (pos[0], pos[1] - rad - font.get_height() // 2 - 4), font, CYAN,
                      center=True)

    def line(self, surf, color, a, b, dashed=False):
        if not dashed:
            pygame.draw.line(surf, color, a, b, 2)
            return
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) // 10))
        for i in range(0, n, 2):
            p0 = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            p1 = (a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n)
            pygame.draw.line(surf, color, p0, p1, 2)

    def gun_lines(self, p, vg):
        if p is None:
            return [(t("player", vg=vg), GREY)]
        lines = [(t("player", vg=vg), GUN_COLORS[(vg - 1) % 4])]
        lines.append((t("battery", v=p.battery) if p.battery is not None else t("battery_na"),
                      RED if p.battery is not None and p.battery < 20 else WHITE))
        lines.append((t("hz", v=p.hz), WHITE if p.hz >= 80 or p.hz == 0 else YELLOW))
        n = p.n_dots
        lines.append((t("dots", n=n), GREEN if n == 2 else YELLOW if n == 1 else RED))
        if n > 2:
            lines.append((t("extra_ir", n=n - 2), RED))
        d = L.distance_m(p, self.hardware)
        lines.append((t("distance", d=d) if d else t("distance_na"), WHITE))
        if not math.isnan(p.roll):
            lines.append((t("roll", v=p.roll), GREY))
        return lines

    def draw_gun_summary(self, surf, guns):
        w, h = surf.get_size()
        x = w // 20
        y = h - h // 5
        for g in guns:
            p = g.packet
            col = GUN_COLORS[(g.virtualgun - 1) % 4]
            parts = [t("player", vg=g.virtualgun),
                     t("battery", v=p.battery) if p.battery is not None else t("battery_na"),
                     t("dots", n=p.n_dots)]
            self.text(surf, "   ".join(parts), (x, y), self.font, col)
            y += self.font.get_height() + 4
            # cursor de cada Wiimote
            pygame.draw.circle(surf, col, (int(p.screen[0] * w), int(p.screen[1] * h)), 10, 3)
