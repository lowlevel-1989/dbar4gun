"""
El worker: el proceso de un Wiimote. Espera a que el Wiimote se empareje,
crea su VirtualGun, y en cada report lee el Wiimote, mueve la VirtualGun y
manda el paquete al calibrator. Tambien responde a los comandos del daemon.
"""

import logging
import os
import time

from io import FileIO

from dbar4gun.core.gun import GunPipeline
from dbar4gun.core.hardware import HardwareConfig
from dbar4gun.daemon.ports import keeps_virtualgun
from dbar4gun.protocol import build_packet
from dbar4gun.wiimote import READ_TIMEOUT


log = logging.getLogger("dbar4gun")

# el worker mira su pipe al menos cada WORKER_POLL s aunque no lleguen reports
# (Wiimote apagado en la DolphinBar durante los 10 s antes de darlo por perdido)
WORKER_POLL = 0.1
# espera entre intentos de emparejar un slot vacio (DolphinBar)
WAIT_PAIR_INTERVAL = 0.2
WAIT_PAIR_MAX = 2.0
# cada cuanto se recalcula el mouse index de cada pistola (LED y teclas)
INDEX_REFRESH = 3.0


class Worker(object):
    """Lo que hace el proceso de cada Wiimote."""

    def _worker_monitor(self):
        self._set_worker_mode()

        try:
            self.monitor.run()
        except Exception as e:
            log.error("monitor: %s", e)

    def _set_worker_mode(self):
        self.is_worker = True

        # free memory
        self.processes = {}
        self.files     = {}
        self.workers   = {}
        self.control   = None


    def _worker_create_virtualgun(self, hidraw_io, port, key=None, conn=None, hidraw_path=None):
        self._set_worker_mode()
        self._create_virtualgun(hidraw_io, port, key, conn, hidraw_path)

    def make_pipeline(self, key):
        """Pipeline del Wiimote con la calibracion guardada si existe."""
        options = self.gun_options()
        data = None
        if key:
            try:
                data = self.store().load(key)
            except Exception as e:
                log.warning("calibration load %s: %s", key, e)
        if data is not None:
            log.info("calibration loaded: %s", key)
        return GunPipeline(options, data)

    def _create_virtualgun(self, hidraw_io, port, key=None, conn=None, hidraw_path=None):
        pipeline = self.make_pipeline(key)
        wiimote = self.class_wiimotedevice(hidraw_io, pipeline,
                                           self.ir_sensitivity(pipeline.options.hardware))
        # la comprobacion periodica de la camara IR solo por Bluetooth
        wiimote.ir_check = not (key or "").startswith("usb:")

        store = self.store()

        def on_save(data, add_history=True):
            if key:
                store.save(key, data, add_history)
                log.info("calibration saved: %s (%s)", key, store.path)

        wiimote.on_save = on_save

        # virtualgun -> mouse / key
        virtualgun = self.class_virtualgundevice(
                        self.config.width,
                        self.config.height,
                        port)
        self._virtualgun = virtualgun

        index = 0
        wait = WAIT_PAIR_INTERVAL
        next_try = 0.0
        while 1:
            # test conexion con wiimote; los intentos se espacian de 0.2 s a
            # 2 s: en un slot vacio de la DolphinBar cada uno es una escritura
            # rechazada, y el servicio puede estar dias encendido
            now = time.monotonic()
            if now >= next_try:
                if wiimote.update_index(0xf):
                    index = virtualgun.create_virtual_device()
                    wiimote.update_index(index)
                    wiimote.announce()
                    break
                next_try = now + wait
                wait = min(wait * 2.0, WAIT_PAIR_MAX)
            # la DolphinBar expone siempre sus 4 slots: mientras no haya un
            # Wiimote en este, el worker sigue respondiendo a los comandos (paired: false)
            timeout = max(0.01, min(WAIT_PAIR_INTERVAL, next_try - time.monotonic()))
            if conn is not None and conn.poll(timeout):
                self._worker_command(conn, wiimote, port, key, hidraw_path, store)
            elif conn is None:
                time.sleep(timeout)

        try:
            wiimote.request_status()
        except Exception:
            pass

        grab = self.input_grab(key, hidraw_path)

        try:

            while 1:
                try:
                    grab.update(time.monotonic(), hidraw_path)
                    index = self._refresh_index(wiimote, virtualgun, index)
                    self._gun_step(wiimote, virtualgun, index, port, WORKER_POLL)
                except (OSError, IOError) as e:
                    # Bluetooth: el hidraw desaparece al desconectarse. La
                    # VirtualGun se conserva (mismo raton, mismo mouse index
                    # para el emulador) hasta que vuelva el mismo Wiimote
                    if conn is None or not keeps_virtualgun(key):
                        raise
                    log.info("VirtualGun %02d: %s disconnected (%s), waiting for it", port + 1, key, e)
                    grab.release()
                    hidraw_io, hidraw_path = self._wait_attach(conn, wiimote, port, key, hidraw_path, store)
                    grab.next_check = 0.0
                    wiimote.io = hidraw_io
                    wiimote.is_pair = False
                    wiimote.next_reset = -1e9
                    log.info("VirtualGun %02d: %s back on %s", port + 1, key, hidraw_path)
                    continue

                if conn is not None and conn.poll():
                    self._worker_command(conn, wiimote, port, key, hidraw_path, store)

        except Exception as e:
            log.warning("VirtualGun %02d: %s", port + 1, e)
        finally:
            grab.release()
            log.info("bye VirtualGun %02d", port + 1)

    def _wait_attach(self, conn, wiimote, port, key, hidraw_path, store):
        """
        Worker sin Wiimote (desconectado por Bluetooth): responde a los comandos
        (paired: false) hasta que el daemon le pasa el hidraw nuevo del mismo
        Wiimote ("attach"). Devuelve (io, ruta).
        """
        wiimote.is_pair = False
        try:
            wiimote.io.close()
        except Exception:
            pass
        self._attach_path = None
        while self._attach_path is None:
            if conn.poll(0.5) and \
                    self._worker_command(conn, wiimote, port, key, hidraw_path, store) is False:
                # el daemon ya no esta: sin esto, poll() devolveria True sin parar
                raise EOFError("daemon gone")
        path = self._attach_path
        self._attach_path = None
        _, io = self.open_device(path)
        return io, path

    def _refresh_index(self, wiimote, virtualgun, index):
        """
        Mouse index actual (cada INDEX_REFRESH s): si cambia (se conecta un
        raton, otra pistola se recrea...), el LED y las teclas lo siguen.
        """
        now = time.monotonic()
        if now < getattr(virtualgun, "next_index_check", 0.0):
            return index
        virtualgun.next_index_check = now + INDEX_REFRESH
        refresh = getattr(virtualgun, "refresh_index", None)
        new = refresh() if refresh else index
        if new and new != index:
            log.info("VirtualGun %02d: mouse index %s -> %s", virtualgun.index + 1, index, new)
            virtualgun.set_index(new)
            wiimote.update_index(new)
            return new
        return index

    def _gun_step(self, wiimote, virtualgun, index, port, timeout=READ_TIMEOUT):
        """Un report: leer, mover la VirtualGun y enviar el paquete UDP."""
        wiimote.check_is_alive()

        buttons,           \
        ir_raw,            \
        ir,                \
        acc,               \
        nunchuck_buttons,  \
        nunchuck_joy = wiimote.read(timeout)

        # el suavizado (One Euro) ya va en el pipeline
        cursor = wiimote.get_cursor()

        virtualgun.set_buttons(buttons, nunchuck_buttons, nunchuck_joy)
        virtualgun.set_cursor(cursor)
        virtualgun.sync()

        self.send_debug_data(wiimote, index, port)

    # tambien lo usa el modo de un solo proceso
    def open_device(self, hidraw_path):
        fd = os.open(hidraw_path, os.O_RDWR)
        return fd, FileIO(fd, "rb+", closefd=False)

    def _worker_command(self, conn, wiimote, port, key, hidraw_path, store):
        """Atiende un comando del daemon. False si el canal se ha cerrado."""
        try:
            rid, cmd, args = conn.recv()
        except (EOFError, OSError, ValueError):
            return False

        reply = {"ok": True}
        try:
            pipeline = wiimote.pipeline
            if cmd == "attach":
                # el mismo Wiimote ha vuelto en este hidraw (ver _wait_attach)
                self._attach_path = args[0]
            elif cmd == "status":
                reply = wiimote.status()
                reply.update({"virtualgun": port + 1, "key": key, "hidraw": hidraw_path})
                # bateria para la proxima consulta (falla si el slot esta vacio)
                if wiimote.is_pair:
                    try:
                        wiimote.request_status()
                    except OSError as e:
                        log.debug("status request: %s", e)
            elif cmd == "recreate":
                # el daemon corrige el orden de RetroArch (ver check_gun_order)
                vg = getattr(self, "_virtualgun", None)
                if vg is not None and getattr(vg, "virtualgun", None) is not None:
                    vg.virtualgun.close()
                    index = vg.create_virtual_device()
                    wiimote.update_index(index)
                    reply["index"] = index
            elif cmd == "area":
                pipeline.set_area(args[0])
            elif cmd == "calibrate":
                kind = args[0] if args else "full"
                targets = args[1] if len(args) > 1 else None
                reply["started"] = pipeline.start_calibration(kind, targets)
            elif cmd == "cancel":
                pipeline.cancel_calibration()
            elif cmd == "filter":
                pipeline.set_filter(*args)
                reply["filter"] = pipeline.filter_params()
            elif cmd == "usefulzone":
                pipeline.options.useful_zone = float(args[0])
            elif cmd == "irmode":
                wiimote.set_ir_extended(args[0] == "extended")
            elif cmd == "hw":
                hw = HardwareConfig.from_dict(args[0])
                pipeline.set_hardware(hw)
                wiimote.set_ir_sensitivity(self.ir_sensitivity(hw))
            elif cmd == "reload":
                hw = self.load_hardware(refresh=True)
                pipeline.set_hardware(hw)
                wiimote.set_ir_sensitivity(self.ir_sensitivity(hw))
                data = store.load(key) if key else None
                if data is not None:
                    pipeline.set_calibration(data)
                reply["loaded"] = data is not None
            else:
                reply = {"ok": False, "error": "unknown"}
        except Exception as e:
            reply = {"ok": False, "error": str(e)}

        try:
            conn.send((rid, reply))
        except (OSError, ValueError):
            pass

    def send_debug_data(self, wiimote, index, port):
        """paquete UDP v2 para el calibrator (docs/PROTOCOL.md)."""
        try:
            data = build_packet(wiimote, index, port + 1).pack()
            self.sock.sendto(data, ("127.0.0.1", self.config.port))
        except OSError:
            pass
