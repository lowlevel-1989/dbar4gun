"""
Bloqueo del mando de botones que crea el kernel para un Wiimote por Bluetooth.

Por Bluetooth se carga hid-wiimote, que ademas del hidraw que usa dbar4gun crea
dispositivos de entrada: "Nintendo Wii Remote" (botones, el sistema lo ve como
un mando), "... Accelerometer", "... IR", "... Motion Plus" y los de las
extensiones. EmulationStation, RetroArch o el escritorio reciben entonces cada
boton dos veces: del mando del kernel y como tecla de la VirtualGun.

dbar4gun agarra (EVIOCGRAB) el de botones y el del Nunchuk mientras usa el
Wiimote: nadie mas recibe sus eventos. Los de IR, acelerometro y Motion Plus no
se abren nunca: al abrirlos y cerrarlos hid-wiimote cambia el modo de datos y
apaga la camara IR. Medido con un RVL-CNT-01-TR por Bluetooth:
- agarrar y soltar el de botones no cambia el modo ni apaga la camara;
- agarrar el del Nunchuk hace que hid-wiimote pase a 0x34 (sin IR) durante
  menos de medio segundo, hasta que dbar4gun vuelve a 0x37; al soltarlo, un
  reporte. Solo pasa al conectar o desconectar el Nunchuk.
Otras extensiones (mando clasico...) no se tocan: sin medir.

Por la DolphinBar no hay nada que agarrar: el kernel usa hid-generic, que no
crea dispositivos de entrada ("No inputs registered").
"""

import glob
import logging
import os

log = logging.getLogger("dbar4gun")

# nombres de los dispositivos de hid-wiimote que se agarran
GRAB_NAMES = ("Nintendo Wii Remote", "Nintendo Wii Remote Nunchuk")
# cada cuanto se buscan (hid-wiimote los crea un poco despues que el hidraw)
GRAB_REFRESH = 2.0


def hid_input_events(hidraw_path, sysfs="/sys"):
    """
    [(nombre, /dev/input/eventN)] de los dispositivos de entrada del mismo
    dispositivo HID que `hidraw_path` (el mismo Wiimote).
    """
    hidraw = os.path.basename(hidraw_path or "")
    if not hidraw:
        return []
    hid = os.path.realpath(os.path.join(sysfs, "class", "hidraw", hidraw, "device"))
    out = []
    for event in sorted(glob.glob(os.path.join(hid, "input", "input*", "event*"))):
        try:
            with open(os.path.join(os.path.dirname(event), "name")) as f:
                name = f.read().strip()
        except (OSError, IOError):
            continue
        out.append((name, "/dev/input/" + os.path.basename(event)))
    return out


def _open_evdev(path):
    import evdev
    return evdev.InputDevice(path)


class InputGrab(object):
    """Agarra el mando de botones del Wiimote mientras dbar4gun lo usa."""

    def __init__(self, hidraw_path, enabled=True, sysfs="/sys", open_device=None):
        self.hidraw_path = hidraw_path
        self.enabled = enabled
        self.sysfs = sysfs
        self._open = open_device or _open_evdev
        self.grabbed = {}       # /dev/input/eventN -> dispositivo abierto
        self.next_check = 0.0

    def update(self, now, hidraw_path=None):
        """Busca y agarra (cada GRAB_REFRESH s); suelta los que ya no existen."""
        if not self.enabled:
            return
        if hidraw_path:
            self.hidraw_path = hidraw_path
        if now < self.next_check:
            return
        self.next_check = now + GRAB_REFRESH
        want = {node: name for name, node in hid_input_events(self.hidraw_path, self.sysfs)
                if name in GRAB_NAMES}
        for node in list(self.grabbed):
            if node not in want:
                self._release(node)
        for node, name in want.items():
            if node in self.grabbed:
                continue
            try:
                device = self._open(node)
                device.grab()
            except (OSError, IOError) as e:
                log.debug("input grab %s: %s", node, e)
                continue
            self.grabbed[node] = device
            log.info("input grab: %s (%s)", node, name)

    def release(self):
        for node in list(self.grabbed):
            self._release(node)

    def _release(self, node):
        device = self.grabbed.pop(node)
        try:
            device.ungrab()
        except (OSError, IOError):
            pass
        try:
            device.close()
        except (OSError, IOError):
            pass
        log.info("input grab released: %s", node)
