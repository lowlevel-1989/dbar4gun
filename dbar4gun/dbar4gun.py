import json
import logging
import os
import socket
import signal
import struct
import time

from pathlib import Path

from typing import Dict, Any

from io import FileIO

from collections import deque

import multiprocessing
import threading

from dbar4gun import info
from dbar4gun.control import ControlServer, SOCKET_PATH, parse_command
from dbar4gun.core.area import AreaProfile
from dbar4gun.core.calibration import MODE_3PT
from dbar4gun.core.gun import GunOptions, GunPipeline, DEFAULT_USEFUL_ZONE, parse_targets
from dbar4gun.core.hardware import HardwareConfig
from dbar4gun.store import HardwareStore, device_key
from dbar4gun.protocol import build_packet
from dbar4gun.wiimote import READ_TIMEOUT

# fork explicito: los workers heredan el hidraw abierto y el estado del daemon
# (python 3.14 cambia el metodo por defecto a forkserver)
_MP = multiprocessing.get_context("fork")
Process = _MP.Process
Queue   = _MP.Queue
Pipe    = _MP.Pipe

# tiempo maximo de espera de la respuesta de un worker (s)
# cuanto espera el daemon la respuesta de cada worker: cubre `irmode`, que
# reconfigura la camara dentro del propio comando (~0.8 s)
WORKER_REPLY_TIMEOUT = 1.0
# el worker mira su pipe al menos cada WORKER_POLL s aunque no lleguen reports
# (Wiimote apagado en la DolphinBar durante los 10 s antes de darlo por perdido)
WORKER_POLL = 0.1
# espera entre intentos de emparejar un slot vacio (DolphinBar)
WAIT_PAIR_INTERVAL = 0.2
WAIT_PAIR_MAX = 2.0
# cada cuanto se recalcula el mouse index de cada pistola (LED y teclas)
INDEX_REFRESH = 3.0
# espera maxima al terminar un proceso (s)
JOIN_TIMEOUT = 1.0


class LocalConn(object):
    """extremo de un pipe entre hilos con la interfaz de multiprocessing.Connection."""

    def __init__(self, inbox, outbox, cond):
        self.inbox = inbox
        self.outbox = outbox
        self.cond = cond

    def send(self, obj):
        with self.cond:
            self.outbox.append(obj)
            self.cond.notify_all()

    def poll(self, timeout=0.0):
        with self.cond:
            if self.inbox:
                return True
            if timeout:
                self.cond.wait(timeout)
            return bool(self.inbox)

    def recv(self):
        with self.cond:
            while not self.inbox:
                self.cond.wait()
            return self.inbox.popleft()

    def close(self):
        pass


def local_pipe():
    a, b = deque(), deque()
    cond = threading.Condition()
    return LocalConn(a, b, cond), LocalConn(b, a, cond)

log = logging.getLogger("dbar4gun")

PID_FILE = "/var/run/dbar4gun.pid"


# entrada de un worker esperando a su Wiimote (en workers/processes/files)
DETACHED = "detached:"


def keeps_virtualgun(key):
    """
    Wiimotes cuya VirtualGun sobrevive a la desconexion: los de Bluetooth (su
    hidraw desaparece y vuelve con la misma MAC). En la DolphinBar el hidraw
    del slot no desaparece al apagar el Wiimote.
    """
    return bool(key) and key.startswith("bt:")


# subcomandos que no son el daemon (el calibrator, los clientes del socket...)
CLIENT_COMMANDS = ("gui", "status", "area", "calibrate", "cancel", "reload", "hw",
                   "profile", "hooks", "version", "stop")

# espera a que el daemon anterior termine antes de crear el pid file y el socket
KILL_WAIT = 5.0


def preferred_port(key):
    """
    Puerto (VirtualGun - 1) que le toca a un dispositivo: en la DolphinBar el
    slot N (interfaz N - 1 de la clave "usb:...inputN") es siempre la
    VirtualGun N, aunque udev avise de los slots desordenados (al reconectar
    la barra llegan en cualquier orden). Por Bluetooth, None (el primero libre).
    """
    if not key or not key.startswith("usb:"):
        return None
    tail = key.rsplit("input", 1)
    if len(tail) == 2 and tail[1].isdigit():
        return int(tail[1])
    return None


def take_port(ports, key):
    """Reserva el puerto de `key` en `ports` (1 = libre); -1 si no hay."""
    want = preferred_port(key)
    if want is not None and 0 <= want < len(ports) and ports[want] > 0:
        ports[want] = 0
        return want
    for i in range(len(ports)):
        if ports[i] > 0:
            ports[i] = 0
            return i
    return -1


def is_daemon_cmdline(args):
    """
    True si los argumentos (de /proc/<pid>/cmdline) son los del daemon:
    el ejecutable `dbar4gun` (o `python -m dbar4gun...`) con `start`, `attach`
    o sin subcomando. `dbar4gun gui`, `dbar4gun status` o `vim dbar4gun.py` no.
    """
    for i, a in enumerate(args):
        if os.path.basename(a) == "dbar4gun" or \
                (a == "-m" and i + 1 < len(args) and args[i + 1].startswith("dbar4gun")):
            rest = args[i + 1:] if a != "-m" else args[i + 2:]
            sub = next((r for r in rest if not r.startswith("-")), None)
            return sub not in CLIENT_COMMANDS
    return False


def is_dbar4gun_process(pid):
    """True si /proc/<pid>/cmdline es el daemon de dbar4gun."""
    try:
        with open("/proc/{}/cmdline".format(int(pid)), "rb") as f:
            args = [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
    except (OSError, ValueError):
        return False
    return is_daemon_cmdline(args)

class Dbar4Gun(object):
    def __init__(self,
                 config,
                 Monitor,
                 WiiMoteDevice,
                 VirtualGunDevice,
                 Calibration=None,
                 IRSetup=None):

        self.config                 = config
        self.class_calibration      = Calibration
        self.class_irsetup          = IRSetup
        self.class_wiimotedevice    = WiiMoteDevice
        self.class_virtualgundevice = VirtualGunDevice
        self.class_monitor          = Monitor


        self.queue  = Queue()

        # soportaremos 16 puertos
        self.port                       = [1] * 16
        self.files = {}
        self.processes  :Dict[str, Any] = {}
        self.is_worker  = False
        self.pid_file   = PID_FILE

        # canal de control por worker: hidraw_path -> [conn, port, key]
        self.workers    = {}
        self.lock       = threading.Lock()
        self.request_id = 0
        self.control    = None
        # hardware.json en memoria: se relee con `hw` y `reload`
        self._hardware  = None
        self.area       = getattr(config, "area", "full") or "full"
        self.useful_zone = getattr(config, "useful_zone", None) or DEFAULT_USEFUL_ZONE
        # perfil por defecto del servicio: "area default" vuelve a el
        self.default_area = self.area

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ------------------------------------------------------------------
    # opciones del pipeline desde la CLI (con valores por defecto si faltan)
    def _cfg(self, name, default):
        value = getattr(self.config, name, default)
        return default if value is None else value

    def screen_aspect(self):
        w = self._cfg("width", 1920)
        h = self._cfg("height", 1080)
        return float(w) / float(h) if h else 16.0 / 9.0

    def gun_options(self):
        targets = self._cfg("calibration_targets", None)
        if isinstance(targets, str):
            targets = parse_targets(targets)
        return GunOptions(
            calibration_mode=self._cfg("calibration", MODE_3PT),
            tilt_correction=not self._cfg("disable_tilt_correction", False),
            distance_compensation=not self._cfg("no_distance_compensation", False),
            area=AreaProfile.parse(self.area, self.screen_aspect()),
            useful_zone=self.useful_zone,
            bar_on_top=self._cfg("bar", "top") != "bottom",
            smoothing_level=self._cfg("smoothing_level", 3),
            targets=targets,
            screen_aspect=self.screen_aspect(),
            hardware=self.load_hardware())

    def ir_sensitivity(self, hardware=None):
        """Nivel de la camara IR: el de hardware.json si esta fijado, si no el del servicio."""
        if hardware is not None and hardware.ir_sensitivity:
            return hardware.ir_sensitivity
        return self._cfg("ir_sensitivity", "marcan")

    def load_hardware(self, refresh=False):
        """
        hardware.json (FOV, signo del acelerometro, ancho de barra, IR
        sensitivity). Se lee una vez; `refresh` lo vuelve a leer del disco.
        Devuelve una copia.
        """
        if refresh or self._hardware is None:
            try:
                self._hardware = self.store().load_hardware()
            except Exception as e:
                log.warning("hardware config: %s", e)
                self._hardware = HardwareConfig()
        return self._hardware.copy()

    def store(self):
        return HardwareStore(self._cfg("config_dir", None))

    def profiles_path(self):
        return os.path.join(self.store().config_dir, "profiles.cfg")

    def load_profile_defaults(self):
        """
        profiles.cfg puede fijar el perfil por defecto ("default") y la zona
        util ("useful_zone"); si no, valen las opciones del servicio.
        """
        from dbar4gun import profiles
        table = profiles.load_profiles(self.profiles_path())
        area = table.get("default")
        if area:
            try:
                AreaProfile.parse(area, self.screen_aspect())
                self.area = self.default_area = area
            except ValueError as e:
                log.warning("profiles.cfg default: %s", e)
        uz = table.get("useful_zone")
        if uz:
            try:
                self.useful_zone = min(1.0, max(0.3, float(uz)))
            except ValueError:
                log.warning("profiles.cfg useful_zone: %s", uz)

    def stop(self):
        if not self.is_worker:
            # solo si el pid file sigue siendo el nuestro
            try:
                if int(Path(self.pid_file).read_text().strip()) == os.getpid():
                    Path(self.pid_file).unlink()
            except (OSError, ValueError):
                pass

        try:
            self.sock.close()
        except OSError as e:
            log.debug("udp socket close: %s", e)

        if self.control is not None:
            self.control.stop()
            self.control = None

        for _, w in self.workers.items():
            try:
                w[0].close()
            except OSError as e:
                log.debug("pipe close: %s", e)

        for _, o in self.files.items():
            fd, hid, port = o
            try:
                if hid is not None:
                    hid.close()
                if fd is not None:
                    os.close(fd)
                log.info("DELETED: VirtualGun %02d", port + 1)
            except OSError as e:
                log.debug("close VirtualGun %02d: %s", port + 1, e)

        for _, proc in self.processes.items():
            try:
                proc.kill()
            except Exception as e:
                log.debug("kill: %s", e)
        # esperar a que terminen (sin bloquear para siempre)
        for _, proc in self.processes.items():
            try:
                proc.join(JOIN_TIMEOUT)
            except Exception as e:
                log.debug("join: %s", e)

    def read_events(self):
        while not self.is_worker:
            try:
                event = self.queue.get()
                self.handle_event(event[0], event[1])
            except Exception as e:
                log.warning("event %s", e)

    def handle_event(self, action, hidraw_path):
        if action == "remove":
            if not self.detach_virtualgun(hidraw_path):
                self.remove_virtualgun(hidraw_path)
            return

        if action != "add":
            return

        if self.reattach_virtualgun(hidraw_path):
            return

        proc = self.processes.get(hidraw_path)
        if proc is not None:
            if proc.is_alive():
                # add duplicado (first scan + evento udev)
                return
            # proceso muerto: liberar y volver a crear
            self.remove_virtualgun(hidraw_path)

        self.create_virtualgun(hidraw_path)

    def kill(self):
        pid_file = Path(self.pid_file)
        if not pid_file.exists():
            return 0

        try:
            pid = int(pid_file.read_text().strip())
        except (OSError, ValueError):
            pid = -1

        # pid file obsoleto: el pid no existe, es el nuestro o es otro programa
        if pid <= 0 or pid == os.getpid() or not is_dbar4gun_process(pid):
            log.info("%s: stale pid file, removed", self.pid_file)
            try:
                pid_file.unlink()
            except OSError as e:
                log.warning("%s: %s", self.pid_file, e)
            return 0

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return 0
        except Exception as e:
            log.error("%s: %s", self.pid_file, e)
            return 1
        # esperar a que termine: al salir borra su pid file y su socket, que
        # si no serian los del daemon nuevo
        deadline = time.monotonic() + KILL_WAIT
        while time.monotonic() < deadline:
            if not is_dbar4gun_process(pid):
                return 0
            time.sleep(0.05)
        log.warning("dbar4gun %d did not exit after %.0f s", pid, KILL_WAIT)
        return 1

    def run(self):
        self.kill()
        self.load_profile_defaults()

        main_pid = os.getpid()

        Path(self.pid_file).write_text(str(main_pid))

        print("\t\tSCREEN {}x{}".format(self.config.width, self.config.height))
        print("\t\tmonitor started, ctrl+c to exit or sudo kill -SIGTERM {}".format(main_pid))

        if self._cfg("single_process", False):
            # experimental: monitor en un hilo y sin procesos por Wiimote
            log.info("single process mode (experimental)")
            self.start_control()
            self.run_single()
            self.stop()
            return

        self.monitor  = self.class_monitor(queue = self.queue)

        monitor_proc = Process(target=self._worker_monitor)
        monitor_proc.start()

        self.processes["monitor"] = monitor_proc

        self.start_control()

        self.read_events()
        self.stop()

    def _worker_monitor(self):
        self._set_worker_mode()

        try:
            self.monitor.run()
        except Exception as e:
            log.error("monitor: %s", e)

    def detach_virtualgun(self, hidraw_path):
        """
        Wiimote de Bluetooth que se desconecta: su worker (y su VirtualGun) se
        queda esperando a que vuelva el mismo Wiimote. True si se hizo.
        """
        with self.lock:
            worker = self.workers.get(hidraw_path)
            if worker is None or not keeps_virtualgun(worker[2]):
                return False
            proc = self.processes.get(hidraw_path)
            if proc is None or not proc.is_alive():
                return False
            slot = DETACHED + worker[2]
            self.workers[slot] = self.workers.pop(hidraw_path)
        self.processes[slot] = self.processes.pop(hidraw_path)
        files = self.files.pop(hidraw_path, None)
        port = worker[1]
        if files is not None:
            fd, hid, port = files
            try:
                if hid is not None:
                    hid.close()
                if fd is not None:
                    os.close(fd)
            except OSError as e:
                log.debug("close %s: %s", hidraw_path, e)
        self.files[slot] = [None, None, port]
        log.info("DETACHED: VirtualGun %02d (%s), kept until it comes back", port + 1, worker[2])
        return True

    def reattach_virtualgun(self, hidraw_path):
        """
        Vuelve un Wiimote cuya VirtualGun se conservo: el mismo worker abre el
        hidraw nuevo. True si se hizo.
        """
        key = device_key(hidraw_path)
        slot = DETACHED + key
        with self.lock:
            worker = self.workers.get(slot)
        proc = self.processes.get(slot)
        if worker is None:
            return False
        if proc is None or not proc.is_alive():
            self.remove_virtualgun(slot)
            return False
        replies = self._ask_workers("attach", [hidraw_path], [worker[1]])
        if not replies or not (replies[0][1] or {}).get("ok"):
            log.warning("VirtualGun %02d: reattach %s failed, starting a new one", worker[1] + 1, key)
            self.remove_virtualgun(slot)
            return False
        with self.lock:
            self.workers[hidraw_path] = self.workers.pop(slot)
        self.processes[hidraw_path] = self.processes.pop(slot)
        self.files[hidraw_path] = self.files.pop(slot)
        log.info("REATTACHED: VirtualGun %02d (%s, %s)", worker[1] + 1, hidraw_path, key)
        return True

    def remove_virtualgun(self, hidraw_path):
        with self.lock:
            worker = self.workers.pop(hidraw_path, None)
        if worker is not None:
            try:
                worker[0].close()
            except OSError as e:
                log.debug("pipe close: %s", e)

        proc = self.processes.pop(hidraw_path, None)
        if proc is not None:
            try:
                proc.kill()
                # recoger el proceso (sin zombies) sin bloquear para siempre
                proc.join(JOIN_TIMEOUT)
            except Exception as e:
                log.debug("kill %s: %s", hidraw_path, e)

        files = self.files.pop(hidraw_path, None)
        if files is not None:
            fd, hid, port = files
            log.info("DELETED: VirtualGun %02d", port + 1)
            self.port[port] = 1
            try:
                if hid is not None:
                    hid.close()
                if fd is not None:
                    os.close(fd)
            except OSError as e:
                log.debug("close %s: %s", hidraw_path, e)

    def create_virtualgun(self, hidraw_path, attach=False):
        fd        = os.open(hidraw_path, os.O_RDWR)
        hidraw_io = FileIO(fd, "rb+", closefd=False)

        key = device_key(hidraw_path)
        # buscamos un puerto disponible (en la DolphinBar, el de su slot)
        port = take_port(self.port, key)

        if port < 0:
            # sin puerto libre se cierra el hidraw (antes quedaba abierto)
            log.warning("no free VirtualGun port for %s", hidraw_path)
            try:
                hidraw_io.close()
                os.close(fd)
            except OSError as e:
                log.debug("close %s: %s", hidraw_path, e)
            return

        if not attach:
            parent_conn, child_conn = Pipe()
            virtualgun_proc = Process(
                    target=self._worker_create_virtualgun,
                    args=(hidraw_io, port, key, child_conn, hidraw_path,))

            virtualgun_proc.start()

            self.processes[hidraw_path] = virtualgun_proc
            with self.lock:
                self.workers[hidraw_path] = [parent_conn, port, key]

        else:
            self.kill()
            pid = os.getpid()

            print("\t\tSCREEN {}x{}".format(self.config.width, self.config.height))
            print("\t\tmonitor started, ctrl+c to exit or sudo kill -SIGTERM {}".format(pid))

            self._create_virtualgun(hidraw_io, port, key, None, hidraw_path)

        self.files[hidraw_path] = [fd, hidraw_io, port]
        log.info("CREATED: VirtualGun %02d (%s, %s)", port + 1, hidraw_path, key)

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

        try:

            while 1:
                try:
                    index = self._refresh_index(wiimote, virtualgun, index)
                    self._gun_step(wiimote, virtualgun, index, port, WORKER_POLL)
                except (OSError, IOError) as e:
                    # Bluetooth: el hidraw desaparece al desconectarse. La
                    # VirtualGun se conserva (mismo raton, mismo mouse index
                    # para el emulador) hasta que vuelva el mismo Wiimote
                    if conn is None or not keeps_virtualgun(key):
                        raise
                    log.info("VirtualGun %02d: %s disconnected (%s), waiting for it", port + 1, key, e)
                    hidraw_io, hidraw_path = self._wait_attach(conn, wiimote, port, key, hidraw_path, store)
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

    # ------------------------------------------------------------------
    # experimental: un solo proceso para todos los Wiimotes
    def open_device(self, hidraw_path):
        fd = os.open(hidraw_path, os.O_RDWR)
        return fd, FileIO(fd, "rb+", closefd=False)

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

    # ------------------------------------------------------------------
    # comandos (lado worker)
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

    # ------------------------------------------------------------------
    # comandos (lado daemon)
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

    def _ask_workers(self, cmd, args=(), ports=None):
        """Envia un comando a los workers y devuelve [(port, respuesta o None)]."""
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

        deadline = time.monotonic() + WORKER_REPLY_TIMEOUT
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

    def send_debug_data(self, wiimote, index, port):
        """paquete UDP v2 para el calibrator (docs/PROTOCOL.md)."""
        try:
            data = build_packet(wiimote, index, port + 1).pack()
            self.sock.sendto(data, ("127.0.0.1", self.config.port))
        except OSError:
            pass
