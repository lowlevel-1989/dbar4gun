"""Simulador -> pipeline real -> paquetes v2 -> calibrator (sin socket ni daemon)."""

from dbar4gun.protocol import Packet, build_packet

from tests.sim.driver import NewDriver


class SimGun(object):
    """Un Wiimote simulado: el 'jugador' apunta a (x, y) con unos botones."""

    def __init__(self, monkeypatch, scene, virtualgun=1, options=None):
        self.scene = scene
        self.vg = virtualgun
        self.drv = NewDriver(monkeypatch, options)
        self.aim = (0.5, 0.5)
        self.buttons = 0
        self.roll = 0.0
        # LEDs de la barra que no se ven (0 izquierda, 1 derecha): LED debil
        self.drop = ()

    def packets(self, n=2):
        """n reports (la GUI va a 60 fps y el Wiimote a ~100 Hz)."""
        out = []
        for _ in range(n):
            self.drv.feed(self.scene.report(self.aim[0], self.aim[1], self.roll, self.buttons,
                                            self.drop))
            out.append(Packet.unpack(build_packet(self.drv.wm, self.vg, self.vg).pack()))
        return out


class SimSource(object):
    def __init__(self, guns):
        self.guns = guns

    def drain(self):
        out = []
        for g in self.guns:
            out += g.packets()
        return out

    def close(self):
        pass


class SimControl(object):
    """Comandos de control ejecutados directamente sobre los pipelines simulados."""

    def __init__(self, guns, store_dir=None):
        self.guns = {g.vg: g for g in guns}
        self.lines = []
        self.store = None
        if store_dir:
            from dbar4gun.store import CalibrationStore
            self.store = CalibrationStore(str(store_dir))
            for g in guns:
                def on_save(data, add_history=True, g=g):
                    g.drv.saved.append(data)
                    self.store.save("sim:{}".format(g.vg), data, add_history)
                g.drv.wm.on_save = on_save

    def _pipelines(self):
        return [g.drv.pipeline for g in self.guns.values()]

    def send(self, line):
        self.lines.append(line)
        parts = line.split()
        cmd = parts[0]
        if cmd == "status":
            out = []
            for vg, g in sorted(self.guns.items()):
                st = g.drv.wm.status()
                st["virtualgun"] = vg
                out.append(st)
            reply = {"ok": True, "wiimotes": out}
            if hasattr(self, "hardware"):
                reply["hardware"] = self.hardware.to_dict()
            return reply
        if cmd == "calibrate":
            vg = int(parts[1])
            targets = None
            for a in parts[2:]:
                if a.startswith("targets="):
                    v = [float(t) for t in a[8:].split(",")]
                    targets = [(v[i], v[i + 1]) for i in range(0, len(v), 2)]
            ok = self.guns[vg].drv.pipeline.start_calibration("full", targets)
            return {"ok": True, "started": [vg] if ok else []}
        if cmd == "cancel":
            for g in self.guns.values():
                g.drv.pipeline.cancel_calibration()
            return {"ok": True}
        if cmd == "area":
            try:
                for p in self._pipelines():
                    p.set_area(parts[1])
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            return {"ok": True}
        if cmd == "usefulzone":
            for p in self._pipelines():
                p.options.useful_zone = float(parts[1])
            return {"ok": True}
        if cmd == "save":
            return {"ok": True, "path": "/tmp/profiles.cfg"}
        if cmd == "filter":
            pipe = self.guns[int(parts[1])].drv.pipeline
            pipe.set_filter(float(parts[2]), float(parts[3]))
            return {"ok": True, "filter": pipe.filter_params()}
        if cmd == "hw":
            from dbar4gun.core.hardware import HardwareConfig
            hw = self.hardware.copy() if hasattr(self, "hardware") else HardwareConfig()
            try:
                for i in range(1, len(parts) - 1, 2):
                    hw.set(parts[i], parts[i + 1])
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            self.hardware = hw
            for g in self.guns.values():
                g.drv.pipeline.set_hardware(hw.copy())
                g.drv.wm.set_ir_sensitivity(hw.ir_sensitivity or "marcan")
            return {"ok": True, "hardware": hw.to_dict()}
        if cmd == "hwreport":
            import json
            self.report = json.loads(line.split(None, 1)[1])
            return {"ok": True, "path": "/tmp/hardware_report.json"}
        if self.store is None:
            return {"ok": False, "error": "no store"}
        key = "sim:{}".format(parts[1])
        if cmd == "accuracy":
            game = [x[5:] for x in parts[2:] if x.startswith("game=")]
            v = [float(x) for x in parts[2:] if "=" not in x]
            acc = {"mean_tv": v[0], "max_tv": v[1], "mean_game": v[2], "max_game": v[3]}
            if game:
                acc["game"] = game[0]
            extra = dict(x.split("=", 1) for x in parts[2:] if "=" in x and not x.startswith("game="))
            if extra:
                acc["analysis"] = extra
            return {"ok": self.store.set_accuracy(key, acc)}
        if cmd == "history":
            out = []
            for i, h in enumerate(self.store.history(key)):
                out.append({"index": i, "timestamp": h["timestamp"], "accuracy": h["accuracy"],
                            "sep_ref": h["calibration"].get("sep_ref"), "mode": h["calibration"]["mode"]})
            return {"ok": True, "history": out}
        if cmd == "restore":
            data = self.store.restore(key, int(parts[2]))
            if data is None:
                return {"ok": False, "error": "no such entry"}
            self.guns[int(parts[1])].drv.pipeline.set_calibration(data)
            return {"ok": True}
        return {"ok": False, "error": "unknown"}
