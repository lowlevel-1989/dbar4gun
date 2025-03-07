import os
import socket
import signal
import struct
import time

from pathlib import Path

from typing import Dict, Any

from io import FileIO

from collections import deque

from multiprocessing import Process
from multiprocessing import Queue

class Dbar4Gun(object):
    def __init__(self,
                 config,
                 Monitor,
                 WiiMoteDevice,
                 VirtualGunDevice,
                 Calibration,
                 IRSetup):

        self.config                 = config
        self.class_calibration      = Calibration
        self.class_irsetup          = IRSetup
        self.class_wiimotedevice    = WiiMoteDevice
        self.class_virtualgundevice = VirtualGunDevice
        self.class_monitor          = Monitor

        self.STRUCT_DATA            = "!BH12e12e2e"
        self.STRUCT_DATA_SIZE       = struct.calcsize(self.STRUCT_DATA)

        self.queue  = Queue()

        # soportaremos 16 puertos
        self.port                       = [1] * 16
        self.files = {}
        self.processes  :Dict[str, Any] = {}
        self.is_worker  = False

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def stop(self):
        if not self.is_worker and Path("/var/run/dbar4gun.pid").exists():
            Path("/var/run/dbar4gun.pid").unlink()

        try:
            self.sock.close()
        except:
            pass

        for _, o in self.files.items():
            fd, hid = o
            try:
                hid.close()
                os.close(fd)

                print("stop: {:04d} {}".format(fd, hid))
            except:
                pass

        for _, proc in self.processes.items():
            try:
                proc.kill()
            except:
                pass

    def read_events(self):
        while not self.is_worker:
            try:
                event = self.queue.get()

                hidraw_path = event[1]
                if event[0] == "remove":
                    self.remove_virtualgun(hidraw_path)
                else:
                    self.create_virtualgun(hidraw_path)
            except Exception as e:
                print(e)

    def kill(self):
        if Path("/var/run/dbar4gun.pid").exists():
            with open("/var/run/dbar4gun.pid", "r") as f:
                try:
                    pid = int(f.readline())
                    os.kill(pid, signal.SIGTERM)
                except Exception as e:
                    print("/var/run/dbar4gun.pid", e)
                    return 1
        return 0

    def run(self):
        self.kill()

        main_pid = os.getpid()

        Path("/var/run/dbar4gun.pid").write_text(str(main_pid))

        self.monitor  = self.class_monitor(queue = self.queue)

        print("\t\tSCREEN {}x{}".format(self.config.width, self.config.height))
        print("\t\tmonitor started, ctrl+c to exit or sudo kill -SIGTERM {}".format(main_pid))

        monitor_proc = Process(target=self._worker_monitor)
        monitor_proc.start()

        self.processes["monitor"] = monitor_proc

        self.read_events()
        self.stop()

    def _worker_monitor(self):
        self._set_worker_mode()

        try:
            self.monitor.run()
        except:
            pass

    def remove_virtualgun(self, hidraw_path):
        try:
            self.processes[hidraw_path].kill()

            fd, hid, port = self.files[hidraw_path]

            hid.close()
            os.close(fd)

            self.port[port] = 1

            del self.processes[hidraw_path]
            del self.files[hidraw_path]
        except:
            pass

    def create_virtualgun(self, hidraw_path, attach=False):
        fd        = os.open(hidraw_path, os.O_RDWR)
        hidraw_io = FileIO(fd, "rb+", closefd=False)

        # buscamos un puerto disponible
        port = -1
        for i in range(len(self.port)):
            if self.port[i] > 0:
                port = i
                self.port[i]
                break

        if not attach and port >= 0:
            virtualgun_proc = Process(
                    target=self._worker_create_virtualgun, args=(hidraw_io, port,))

            virtualgun_proc.start()

            self.processes[hidraw_path] = virtualgun_proc

        else:
            self.kill()
            pid = os.getpid()

            print("\t\tSCREEN {}x{}".format(self.config.width, self.config.height))
            print("\t\tmonitor started, ctrl+c to exit or sudo kill -SIGTERM {}".format(pid))

            # solo creamos el virtualgun si tenemos un puerto disponible
            if port >= 0:
                self._create_virtualgun(hidraw_io, port)

        if port >= 0:
            self.files[hidraw_path] = [fd, hidraw_io, port]

    def _set_worker_mode(self):
        self.is_worker = True

        # free memory
        self.processes = {}
        self.files     = {}


    def _worker_create_virtualgun(self, hidraw_io, port):
        self._set_worker_mode()
        self._create_virtualgun(hidraw_io, port)

    def _create_virtualgun(self, hidraw_io, port):
        wiimote = self.class_wiimotedevice(
                        hidraw_io,
                        self.class_calibration,
                        self.class_irsetup,
                        port)

        wiimote.set_tilt_correction(
                        not self.config.disable_tilt_correction)

        # virtualgun -> mouse / key
        virtualgun = self.class_virtualgundevice(
                        self.config.width,
                        self.config.height)

        index = 0
        while 1:
            # test conexion con wiimote
            if wiimote.update_index(0xf):
                index = virtualgun.create_virtual_device()
                wiimote.update_index(index)
                break
            time.sleep(0.2)
        try:

            history_x = deque(maxlen=self.config.smoothing_level)
            history_y = deque(maxlen=self.config.smoothing_level)

            while 1:
                wiimote.check_is_alive()

                buttons,           \
                ir_raw,            \
                ir,                \
                acc,               \
                nunchuck_buttons,  \
                nunchuck_joy = wiimote.read()

                cursor_raw = wiimote.get_cursor()

                history_x.append(cursor_raw[0])
                history_y.append(cursor_raw[1])

                cursor = [0.5, 0.5]

                cursor[0] = sum(history_x) / self.config.smoothing_level
                cursor[1] = sum(history_y) / self.config.smoothing_level

                virtualgun.set_buttons(buttons, nunchuck_buttons, nunchuck_joy)
                virtualgun.set_cursor(cursor)
                virtualgun.sync()

                self.send_debug_data(
                        index, buttons, ir_raw, ir, cursor)

        except Exception as e:
            print(e)
        finally:
            print("\nbye VirtualGun {:03X}".format(wiimote.player))

    def send_debug_data(self, index, buttons, ir_raw, ir, cursor):
        data = struct.pack(self.STRUCT_DATA,
                    index, buttons,
                    ir_raw[0][0], ir_raw[0][1], ir_raw[0][2],
                    ir_raw[1][0], ir_raw[1][1], ir_raw[1][2],
                    ir_raw[2][0], ir_raw[2][1], ir_raw[2][2],
                    ir_raw[3][0], ir_raw[3][1], ir_raw[3][2],
                    ir[0][0],     ir[0][1],     ir[0][2],
                    ir[1][0],     ir[1][1],     ir[1][2],
                    ir[2][0],     ir[2][1],     ir[2][2],
                    ir[3][0],     ir[3][1],     ir[3][2],
                    cursor[0], cursor[1])

        self.sock.sendto(data, ("127.0.0.1", self.config.port))
