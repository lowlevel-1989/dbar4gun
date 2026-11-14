"""
Hardware check, paso a paso (la medida esta en logic/hardware.py).

Cada paso da un veredicto y, si hace falta, ofrece aplicar el valor medido.
Al final guarda el informe.
"""

import json
import math

from dbar4gun.core.hardware import HardwareConfig, next_ir_sensitivity
from dbar4gun.gui.draw import CYAN, GREEN, GREY, RED, WHITE, YELLOW
from dbar4gun.gui.i18n import t
from dbar4gun.gui.logic.hardware import (
    AccSignCheck, BarSideCheck, combine_fov, DisconnectCheck, FAIL, FovMeasure, IRQuality,
    link_check, NA, OK, overall, WARN,
)
from dbar4gun.gui.logic.wiimotes import (
    BTN_A, BTN_B, BTN_DOWN, BTN_HOME, BTN_LEFT, BTN_ONE, BTN_RIGHT, BTN_TWO, BTN_UP,
)
from dbar4gun.gui.screens.base import GunScreen


# s que se espera a la camara IR tras cambiar su sensibilidad
IR_SETTLE = 1.5
# pasos en los que hay que apuntar: se empiezan con A o con el gatillo (B) y la
# medida empieza tras una cuenta atras, para que el movimiento de la mano al
# pulsar no cuente
AIM_STEPS = ("ir", "acc", "fov", "bar")
AIM_COUNTDOWN = 3.0


class HardwareScreen(GunScreen):
    """
    Autodiagnostico del hardware, paso a paso. Cada paso mide algo,
    da un veredicto (verde/amarillo/rojo) y, si hace falta, ofrece aplicar el
    valor medido (`hw` por el socket de control). Al final guarda el informe (`hwreport`).
    """

    STEPS = ["link", "ir", "acc", "fov", "bar", "disconnect", "summary"]
    COLORS = {OK: GREEN, WARN: YELLOW, FAIL: RED, NA: GREY}

    def __init__(self, app, virtualgun):
        super(HardwareScreen, self).__init__(app, virtualgun)
        self.results = {}
        self.index = -1          # -1 = intro
        self.message = None
        self.report_path = None
        self.status = {}
        self.fov_runs = []
        # a 2 m se juega en un salon normal; se ajusta con arriba/abajo
        self.distance = 2.0
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
            self.results["link"] = link_check(self.status, self.packet)
            self.stage = "result"
        elif step == "summary":
            self.save_report()

    def next(self, now):
        self.enter(self.index + 1, now)

    def gun_status(self):
        return self.app.refresh_status().get(self.vg, {})

    def gun_hardware(self):
        """Valores que usa ahora el pipeline de este Wiimote (status por el socket de control)."""
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
            "overall": overall(self.results),
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
        if g.was_pressed(BTN_HOME):
            self.app.go_menu()
            return

        if step == "intro":
            if g.was_pressed(BTN_A):
                self.next(now)
            return
        if step == "summary":
            if g.was_pressed(BTN_A):
                self.app.go_menu()
            return
        if self.stage == "result":
            self.update_result(g, now)
            return
        if step == "fov" and self.stage == "intro":
            if g.was_pressed(BTN_UP):
                self.distance = min(8.0, round(self.distance + 0.1, 2))
            if g.was_pressed(BTN_DOWN):
                self.distance = max(0.5, round(self.distance - 0.1, 2))
            if g.was_pressed(BTN_RIGHT):
                self.bar_width = min(0.6, round(self.bar_width + 0.01, 3))
            if g.was_pressed(BTN_LEFT):
                self.bar_width = max(0.05, round(self.bar_width - 0.01, 3))
        if self.stage == "intro":
            if g.was_pressed(BTN_ONE):
                self.results[step] = {"verdict": NA, "skipped": True}
                self.next(now)
            elif g.was_pressed(BTN_A) or (step in AIM_STEPS and g.was_pressed(BTN_B)):
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
        if step in AIM_STEPS:
            settle = max(settle, AIM_COUNTDOWN)
        self.settle_until = now + settle
        if step == "ir":
            self.check = IRQuality()
        elif step == "acc":
            self.check = AccSignCheck()
        elif step == "fov":
            self.check = FovMeasure(self.distance, self.bar_width)
        elif step == "bar":
            self.check = BarSideCheck()
        elif step == "disconnect":
            self.check = DisconnectCheck(now)

    def finish_run(self):
        step = self.step
        if step == "acc":
            self.results["acc"] = self.check.result(self.gun_hardware().acc_x_sign)
        elif step == "fov":
            r = self.check.result()
            self.fov_runs.append(r)
            r = dict(r)
            r["runs"] = len(self.fov_runs)
            combined = combine_fov(self.fov_runs)
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
        if step == "acc" and r.get("verdict") == FAIL and g.was_pressed(BTN_TWO):
            if self.apply("hw acc_x_sign {:g}".format(r["acc_x_sign"])):
                r["applied"] = True
        elif step == "fov" and r.get("fov_h_deg") and g.was_pressed(BTN_TWO):
            if self.apply("hw fov {:.2f} bar_width {:.3f}".format(r["fov_h_deg"], self.bar_width)):
                r["applied"] = True
        elif step == "ir" and r.get("suggest") and g.was_pressed(BTN_TWO):
            # probar el nivel siguiente y volver a medir
            if self.apply("hw ir_sensitivity {}".format(r["suggest"])):
                self.ir_tried.append(r["suggest"])
                self.start_run(now, settle=IR_SETTLE)
        elif step == "fov" and g.was_pressed(BTN_B):
            # otra medida a otra distancia (se promedian)
            self.stage = "intro"
            self.message = None
        elif step in ("ir", "acc", "bar") and g.was_pressed(BTN_B):
            self.start_run(now)
        elif g.was_pressed(BTN_A):
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
                r = self.results.get(s_, {"verdict": NA})
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
            out.append((t("hw.start_hint_aim" if step in AIM_STEPS else "hw.start_hint"), GREY))
        elif self.stage == "run" and self.app.now < self.settle_until and step in AIM_STEPS:
            left = int(math.ceil(self.settle_until - self.app.now))
            out.append((t("hw.countdown_acc" if step == "acc" else "hw.countdown", s=left), YELLOW))
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
        v = r.get("verdict", NA)
        if r.get("skipped"):
            return t("hw.skipped")
        if v == NA and step != "link":
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
            return t("hw.bar." + v)
        if step == "disconnect":
            if v == OK:
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
        if step == "bar" and r.get("measured") == "bottom":
            out.append(t("hw.bar.fix"))
        if step == "fov" and r.get("applied") or step == "acc" and r.get("applied"):
            out.append(t("hw.applied"))
        return out

    def result_hint(self, step, r):
        if step == "ir" and r.get("suggest"):
            return t("hw.hint_apply_ir", l=r["suggest"], c=r.get("ir_sensitivity") or "?")
        if step == "acc" and r.get("verdict") == FAIL and not r.get("applied"):
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
