"""
Dbar4Gun: el servicio. Arranca (run), para (stop) y cierra el daemon anterior
(kill). El resto lo hereda de las demas partes de esta carpeta.
"""

import logging
import os
import signal
import socket
import threading
import time

from pathlib import Path

from dbar4gun.core.gun import DEFAULT_USEFUL_ZONE
from dbar4gun.daemon.commands import Commands
from dbar4gun.daemon.devices import Devices, JOIN_TIMEOUT
from dbar4gun.daemon.options import Options
from dbar4gun.daemon.order import GunOrder
from dbar4gun.daemon.pidfile import is_dbar4gun_process, KILL_WAIT, PID_FILE
from dbar4gun.daemon.pipes import Process, Queue
from dbar4gun.daemon.single import SingleProcess
from dbar4gun.daemon.worker import Worker


log = logging.getLogger("dbar4gun")


class Dbar4Gun(Options, Devices, Worker, SingleProcess, GunOrder, Commands):
    """El servicio: junta las partes de esta carpeta (todas comparten self)."""

    def __init__(self,
                 config,
                 Monitor,
                 WiiMoteDevice,
                 VirtualGunDevice):

        self.config                 = config
        self.class_wiimotedevice    = WiiMoteDevice
        self.class_virtualgundevice = VirtualGunDevice
        self.class_monitor          = Monitor


        self.queue  = Queue()

        # soportaremos 16 puertos
        self.port                       = [1] * 16
        self.files = {}
        self.processes  = {}
        self.is_worker  = False
        self.pid_file   = PID_FILE

        # canal de control por worker: hidraw_path -> [conn, port, key]
        self.workers    = {}
        self.lock       = threading.Lock()
        # una sola peticion a los workers a la vez (control socket y orden)
        self.ask_lock   = threading.Lock()
        self.request_id = 0
        # orden de encendido de las VirtualGun: [port] y su inputN visto
        self.gun_order  = []
        self.gun_seen   = {}
        self.control    = None
        # hardware.json en memoria: se relee con `hw` y `reload`
        self._hardware  = None
        self.area       = getattr(config, "area", "full") or "full"
        self.useful_zone = getattr(config, "useful_zone", None) or DEFAULT_USEFUL_ZONE
        # perfil por defecto del servicio: "area default" vuelve a el
        self.default_area = self.area

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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
        if self._cfg("bar", "top") == "bottom":
            log.warning("--bar is no longer used: the calibration works with the bar on top of the TV (or below a small TV)")

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
        self.start_order_check()

        self.read_events()
        self.stop()
