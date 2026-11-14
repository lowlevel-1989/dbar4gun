"""
Comandos del socket de control (lado daemon): status, area, calibrate,
history, hw... Los que afectan a un Wiimote se mandan a su worker.
"""

import json
import logging
import time

from dbar4gun import info
from dbar4gun.control import ControlServer, parse_command, SOCKET_PATH
from dbar4gun.core.area import AreaProfile


log = logging.getLogger("dbar4gun")

# cuanto espera el daemon la respuesta de cada worker: cubre `irmode`, que
# reconfigura la camara dentro del propio comando (~0.8 s)
WORKER_REPLY_TIMEOUT = 1.0


class Commands(object):
    """Atiende el socket de control y pregunta a los workers."""

    def start_control(self):
        path = self._cfg("socket", SOCKET_PATH)
        try:
            self.control = ControlServer(self.handle_command, path)
            self.control.bind()
            self.control.start()
            log.info("control socket %s", path)
        except Exception as e:
            log.error("control socket %s: %s", path, e)
            self.control = None

    def _ask_workers(self, cmd, args=(), ports=None, timeout=None):
        """Envia un comando a los workers y devuelve [(port, respuesta o None)]."""
        if timeout is None:
            timeout = WORKER_REPLY_TIMEOUT
        with self.ask_lock:
            return self._ask_workers_locked(cmd, args, ports, timeout)

    def _ask_workers_locked(self, cmd, args, ports, timeout):
        with self.lock:
            self.request_id += 1
            rid = self.request_id
            workers = [(w[0], w[1]) for w in self.workers.values()
                       if ports is None or w[1] in ports]

        sent = []
        for conn, port in workers:
            try:
                conn.send((rid, cmd, list(args)))
                sent.append((conn, port))
            except (OSError, ValueError):
                pass

        deadline = time.monotonic() + timeout
        out = []
        for conn, port in sent:
            reply = None
            while True:
                left = deadline - time.monotonic()
                try:
                    if left <= 0 or not conn.poll(left):
                        break
                    got_rid, data = conn.recv()
                except (EOFError, OSError, ValueError):
                    break
                # se descartan respuestas atrasadas de peticiones anteriores
                if got_rid == rid:
                    reply = data
                    break
            out.append((port, reply))
        out.sort(key=lambda r: r[0])
        return out

    def _key_of(self, vg):
        with self.lock:
            for conn, port, key in self.workers.values():
                if port == vg - 1:
                    return key
        return None

    def _history_command(self, cmd, args):
        """history de calibraciones (lo gestiona el daemon en el store)."""
        try:
            vg = int(args[0])
        except (ValueError, IndexError):
            return {"ok": False, "error": "usage: {} <virtualgun> ...".format(cmd)}
        key = self._key_of(vg)
        if not key:
            return {"ok": False, "error": "unknown virtualgun {}".format(vg)}
        store = self.store()

        if cmd == "history":
            out = []
            for i, h in enumerate(store.history(key)):
                c = h.get("calibration", {})
                out.append({"index": i, "timestamp": h.get("timestamp"),
                            "accuracy": h.get("accuracy"), "mode": c.get("mode"),
                            "sep_ref": c.get("sep_ref")})
            return {"ok": True, "key": key, "history": out}

        if cmd == "restore":
            try:
                data = store.restore(key, int(args[1]))
            except (ValueError, IndexError):
                return {"ok": False, "error": "usage: restore <virtualgun> <index>"}
            if data is None:
                return {"ok": False, "error": "no such entry"}
            self._ask_workers("reload", (), [vg - 1])
            return {"ok": True}

        # accuracy <vg> <mean_tv> <max_tv> [mean_game max_game] [game=<que se simulo>]
        game = None
        nums = []
        analysis = {}
        for a in args[1:]:
            if a.startswith("game="):
                game = a[5:]
            elif "=" in a:
                # analisis de la shooting gallery: kind=scale offset=1.2,0.3 ...
                k, v = a.split("=", 1)
                try:
                    vals = [None if x == "-" else float(x) for x in v.split(",")]
                    analysis[k] = vals[0] if len(vals) == 1 else vals
                except ValueError:
                    analysis[k] = v
            else:
                nums.append(a)
        try:
            v = [float(a) for a in nums]
        except ValueError:
            v = []
        if len(v) not in (2, 4):
            return {"ok": False, "error": "usage: accuracy <virtualgun> <mean_tv> <max_tv> [mean_game max_game] [game=<name>]"}
        acc = {"mean_tv": v[0], "max_tv": v[1]}
        if len(v) == 4:
            acc.update({"mean_game": v[2], "max_game": v[3]})
        if game:
            acc["game"] = game
        if analysis:
            acc["analysis"] = analysis
        acc["timestamp"] = time.time()
        return {"ok": store.set_accuracy(key, acc)}

    def handle_command(self, line):
        cmd, args = parse_command(line)

        if cmd == "status":
            guns = []
            for port, reply in self._ask_workers("status"):
                if reply is None:
                    reply = {"virtualgun": port + 1, "ok": False, "error": "no response"}
                guns.append(reply)
            return {
                "ok": True,
                "version": info.__version__,
                "area": self.area,
                "useful_zone": self.useful_zone,
                "wiimotes": guns,
                "hardware": self.load_hardware().to_dict(),
                # para `dbar4gun profile` (hooks de runcommand)
                "profiles": self.profiles_path(),
            }

        if cmd == "area":
            if len(args) != 1:
                return {"ok": False, "error": "usage: area <default|full|4:3|custom:x0,y0,w,h>"}
            if args[0] == "default":
                args = [self.default_area]
            try:
                AreaProfile.parse(args[0], self.screen_aspect())
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            # los workers nuevos heredan el area actual al hacer fork
            self.area = args[0]
            self._ask_workers("area", [args[0]])
            return {"ok": True, "area": self.area}

        if cmd == "calibrate":
            ports = None
            kind = "full"
            targets = None
            usage = "usage: calibrate [virtualgun] [full|quick] [targets=x1,y1,...]"
            for a in args:
                if a.isdigit():
                    ports = [int(a) - 1]
                elif a in ("full", "quick"):
                    kind = a
                elif a.startswith("targets="):
                    try:
                        v = [float(t) for t in a[8:].split(",")]
                    except ValueError:
                        return {"ok": False, "error": usage}
                    if len(v) % 2 or not all(-0.5 <= t <= 1.5 for t in v):
                        return {"ok": False, "error": usage}
                    targets = [(v[i], v[i + 1]) for i in range(0, len(v), 2)]
                else:
                    return {"ok": False, "error": usage}
            replies = self._ask_workers("calibrate", [kind, targets], ports)
            return {"ok": bool(replies), "started": [p + 1 for p, r in replies if r and r.get("started")]}

        if cmd == "cancel":
            self._ask_workers("cancel")
            return {"ok": True}

        if cmd == "irmode":
            # modo IR extendido (tamano de los dots) hasta verificarlo con hardware
            if not self._cfg("experimental_ir_extended", False):
                return {"ok": False, "error": "irmode needs --experimental-ir-extended"}
            if len(args) != 1 or args[0] not in ("basic", "extended"):
                return {"ok": False, "error": "usage: irmode <basic|extended>"}
            self._ask_workers("irmode", [args[0]])
            return {"ok": True, "irmode": args[0]}

        if cmd == "usefulzone":
            try:
                v = float(args[0])
                if not 0.3 <= v <= 1.0:
                    raise ValueError
            except (ValueError, IndexError):
                return {"ok": False, "error": "usage: usefulzone <0.3..1.0>"}
            self.useful_zone = v
            self._ask_workers("usefulzone", [v])
            return {"ok": True, "useful_zone": v}

        if cmd == "save":
            # el area y la useful zone actuales pasan a profiles.cfg
            from dbar4gun import profiles
            path = self.profiles_path()
            try:
                profiles.set_entry(path, "default", self.area)
                profiles.set_entry(path, "useful_zone", "{:.3f}".format(self.useful_zone))
            except OSError as e:
                return {"ok": False, "error": str(e)}
            self.default_area = self.area
            return {"ok": True, "path": path, "default": self.area, "useful_zone": self.useful_zone}

        if cmd == "filter":
            usage = "usage: filter <virtualgun> <fc_min> <beta> [d_cutoff]"
            try:
                vg = int(args[0])
                values = [float(a) for a in args[1:]]
                if len(values) not in (2, 3) or values[0] <= 0 or values[1] < 0:
                    raise ValueError
            except (ValueError, IndexError):
                return {"ok": False, "error": usage}
            replies = self._ask_workers("filter", values, [vg - 1])
            if not replies or not replies[0][1]:
                return {"ok": False, "error": "no response"}
            return {"ok": replies[0][1].get("ok", False), "filter": replies[0][1].get("filter")}

        if cmd in ("history", "restore", "accuracy"):
            return self._history_command(cmd, args)

        if cmd == "hw":
            return self._hw_command(args)

        if cmd == "hwreport":
            # el resto de la linea es JSON (puede llevar espacios)
            parts = line.split(None, 1)
            try:
                report = json.loads(parts[1]) if len(parts) > 1 else None
                if not isinstance(report, dict):
                    raise ValueError
            except ValueError:
                return {"ok": False, "error": "usage: hwreport <json object>"}
            report["saved"] = time.time()
            try:
                path = self.store().save_report(report)
            except OSError as e:
                return {"ok": False, "error": str(e)}
            log.info("hardware report saved: %s", path)
            return {"ok": True, "path": path}

        if cmd == "reload":
            self.load_hardware(refresh=True)
            replies = self._ask_workers("reload")
            return {"ok": True, "loaded": [p + 1 for p, r in replies if r and r.get("loaded")]}

        return {"ok": False, "error": "unknown command '{}' (status, area, calibrate, cancel, reload, irmode, usefulzone, save, filter, history, restore, accuracy, hw, hwreport)".format(cmd)}

    def _hw_command(self, args):
        """
        `hw` muestra los valores; `hw <clave> <valor> [...]` los cambia,
        los guarda en hardware.json y los aplica a todos los Wiimotes.
        """
        store = self.store()
        hw = self.load_hardware(refresh=True)
        if not args:
            return {"ok": True, "hardware": hw.to_dict(), "path": store.hw_path}
        if len(args) % 2:
            return {"ok": False, "error": "usage: hw [fov <deg>] [acc_x_sign <1|-1>] [bar_width <m>] [ir_sensitivity <1..5|marcan|cliff|default>]"}
        try:
            for i in range(0, len(args), 2):
                hw.set(args[i].lower(), args[i + 1])
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        try:
            store.save_hardware(hw)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        self._hardware = hw.copy()
        self._ask_workers("hw", [hw.to_dict()])
        log.info("hardware: %s", hw.to_dict())
        return {"ok": True, "hardware": hw.to_dict(), "path": store.hw_path}
