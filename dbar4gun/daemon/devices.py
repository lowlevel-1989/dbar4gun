"""
Wiimotes que llegan y se van (lado daemon): por cada Wiimote se crea un
proceso worker con su VirtualGun. Un Wiimote de Bluetooth que se desconecta
conserva su VirtualGun hasta que vuelve.
"""

import logging
import os

from io import FileIO

from dbar4gun.daemon.pipes import Pipe, Process
from dbar4gun.daemon.ports import DETACHED, keeps_virtualgun, take_port
from dbar4gun.store import device_key


log = logging.getLogger("dbar4gun")

# espera maxima al terminar un proceso (s)
JOIN_TIMEOUT = 1.0


class Devices(object):
    """Crear, quitar, separar y volver a unir los workers de los Wiimotes."""

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
