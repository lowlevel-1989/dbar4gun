"""
Experimental (--single-process): todos los Wiimotes en un solo proceso, con
select en vez de un worker por Wiimote.
"""

import logging
import os
import threading
import time

from dbar4gun.daemon.pipes import local_pipe
from dbar4gun.daemon.ports import DETACHED, keeps_virtualgun, take_port
from dbar4gun.daemon.worker import WAIT_PAIR_INTERVAL, WAIT_PAIR_MAX
from dbar4gun.store import device_key


log = logging.getLogger("dbar4gun")


class SingleProcess(object):
    """Modo de un solo proceso (experimental)."""

    def run_single(self, stop_event=None):
        """
        Lee todos los hidraw con select en un solo proceso (un uinput por gun).
        Los comandos de control usan el mismo codigo que los workers, con un pipe entre
        hilos. Crear un Wiimote bloquea el bucle ~0.8 s (enable_ir).
        """
        import queue as queue_module
        import select as select_module

        self.guns = {}
        self.events = queue_module.Queue()
        if self.class_monitor is not None:
            monitor = self.class_monitor(queue=self.events)
            t = threading.Thread(target=monitor.run, name="dbar4gun-monitor")
            t.daemon = True
            t.start()

        while stop_event is None or not stop_event.is_set():
            while True:
                try:
                    action, path = self.events.get_nowait()
                except queue_module.Empty:
                    break
                try:
                    self.handle_event_single(action, path)
                except Exception as e:
                    log.warning("event %s %s: %s", action, path, e)

            ready_guns = [g for g in self.guns.values() if g["index"] and g["fd"] is not None]
            fds = [g["fd"] for g in ready_guns]
            ready = []
            if fds:
                try:
                    ready, _, _ = select_module.select(fds, [], [], 0.05)
                except (OSError, ValueError) as e:
                    log.debug("select: %s", e)
            elif stop_event is not None:
                stop_event.wait(0.05)
            else:
                time.sleep(0.05)

            for g in list(self.guns.values()):
                try:
                    if g["fd"] is None:
                        pass        # Bluetooth desconectado: solo responde a los comandos
                    elif not g["index"]:
                        # sin Wiimote (slot vacio de la DolphinBar): sigue
                        # respondiendo a los comandos con paired: false
                        self._single_connect(g)
                    elif g["fd"] in ready:
                        g["grab"].update(time.monotonic(), g["path"])
                        g["index"] = self._refresh_index(g["wiimote"], g["virtualgun"], g["index"])
                        self._gun_step(g["wiimote"], g["virtualgun"], g["index"], g["port"], None)
                    else:
                        g["wiimote"].check_is_alive()
                        g["wiimote"].idle()
                    while g["conn"].poll():
                        self._worker_command(g["conn"], g["wiimote"], g["port"], g["key"],
                                             g["path"], g["store"])
                except Exception as e:
                    log.warning("VirtualGun %02d: %s", g["port"] + 1, e)
                    self.remove_single(g["path"])

    def _single_connect(self, g):
        now = time.monotonic()
        if now < g["retry"]:
            return
        g["retry"] = now + g.get("wait", WAIT_PAIR_INTERVAL)
        g["wait"] = min(g.get("wait", WAIT_PAIR_INTERVAL) * 2.0, WAIT_PAIR_MAX)
        if g["wiimote"].update_index(0xf):
            g["index"] = g["virtualgun"].create_virtual_device()
            g["wiimote"].update_index(g["index"])
            g["wiimote"].announce()
            try:
                g["wiimote"].request_status()
            except OSError:
                pass

    def handle_event_single(self, action, hidraw_path):
        if action == "remove":
            self.remove_single(hidraw_path)
            return
        if action != "add" or hidraw_path in self.guns:
            return

        key = device_key(hidraw_path)
        slot = DETACHED + (key or "")
        if slot in self.guns:
            # vuelve un Wiimote de Bluetooth: la misma VirtualGun
            g = self.guns.pop(slot)
            fd, hidraw_io = self.open_device(hidraw_path)
            g.update({"path": hidraw_path, "fd": fd, "io": hidraw_io})
            g["wiimote"].io = hidraw_io
            g["wiimote"].is_pair = False
            g["wiimote"].next_reset = -1e9
            self.guns[hidraw_path] = g
            self.files[hidraw_path] = [fd, hidraw_io, g["port"]]
            with self.lock:
                self.workers[hidraw_path] = self.workers.pop(slot)
            log.info("REATTACHED: VirtualGun %02d (%s, %s, single process)", g["port"] + 1, hidraw_path, key)
            return

        port = take_port(self.port, key)
        if port < 0:
            log.warning("no free VirtualGun port for %s", hidraw_path)
            return

        fd, hidraw_io = self.open_device(hidraw_path)
        store = self.store()
        pipeline = self.make_pipeline(key)
        wiimote = self.class_wiimotedevice(hidraw_io, pipeline,
                                           self.ir_sensitivity(pipeline.options.hardware))
        # la comprobacion periodica de la camara IR solo por Bluetooth
        wiimote.ir_check = not (key or "").startswith("usb:")

        def on_save(data, add_history=True):
            if key:
                store.save(key, data, add_history)
                log.info("calibration saved: %s (%s)", key, store.path)

        wiimote.on_save = on_save
        parent, child = local_pipe()
        self.guns[hidraw_path] = {
            "path": hidraw_path, "fd": fd, "io": hidraw_io, "port": port, "key": key,
            "store": store, "wiimote": wiimote, "conn": child, "index": 0, "retry": 0.0,
            "grab": self.input_grab(key, hidraw_path),
            "virtualgun": self.class_virtualgundevice(self.config.width, self.config.height, port),
        }
        self.files[hidraw_path] = [fd, hidraw_io, port]
        with self.lock:
            self.workers[hidraw_path] = [parent, port, key]
        log.info("CREATED: VirtualGun %02d (%s, %s, single process)", port + 1, hidraw_path, key)

    def remove_single(self, hidraw_path):
        g = self.guns.get(hidraw_path)
        if g is not None and g["index"] and keeps_virtualgun(g["key"]):
            # Bluetooth: la VirtualGun se conserva hasta que vuelva el Wiimote
            self.guns.pop(hidraw_path)
            self.files.pop(hidraw_path, None)
            try:
                g["io"].close()
                os.close(g["fd"])
            except OSError as e:
                log.debug("close %s: %s", hidraw_path, e)
            g["fd"] = g["io"] = None
            g["wiimote"].is_pair = False
            g["grab"].release()
            g["grab"].next_check = 0.0
            slot = DETACHED + g["key"]
            self.guns[slot] = g
            with self.lock:
                if hidraw_path in self.workers:
                    self.workers[slot] = self.workers.pop(hidraw_path)
            log.info("DETACHED: VirtualGun %02d (%s), kept until it comes back", g["port"] + 1, g["key"])
            return
        g = self.guns.pop(hidraw_path, None)
        with self.lock:
            self.workers.pop(hidraw_path, None)
        files = self.files.pop(hidraw_path, None)
        if g is None:
            return
        g["grab"].release()
        try:
            vg = g["virtualgun"].virtualgun
            vg.close()
        except Exception as e:
            log.debug("uinput close: %s", e)
        if files is not None:
            try:
                g["io"].close()
                os.close(g["fd"])
            except OSError as e:
                log.debug("close %s: %s", hidraw_path, e)
        self.port[g["port"]] = 1
        log.info("DELETED: VirtualGun %02d", g["port"] + 1)
