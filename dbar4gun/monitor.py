"""
Avisa con udev cuando se conecta o desconecta un Wiimote (dispositivo
hidraw del driver wiimote).
"""

import pyudev

# udevadm info --query=all --name=/dev/hidraw0
# udevadm info -a -n /dev/hidraw0

WIIMOTE_MODEL  = "Wii Remote Controller RVL-003"
WIIMOTE_DRIVER = "wiimote"


def is_wiimote(device):
    if device.get("ID_MODEL_FROM_DATABASE") == WIIMOTE_MODEL:
        return True

    try:
        parent = device.parent
    except Exception:
        parent = None

    # sin parent no podemos descartarlo (comportamiento historico)
    if not parent:
        return True

    return parent.driver == WIIMOTE_DRIVER


def classify_event(action, device):
    """
    Devuelve ["add", hidraw_path], ["remove", hidraw_path] o None.

    - solo se atienden add/remove (change/move/bind/... se ignoran).
    - remove se reenvia siempre que tenga DEVNAME: al desconectarse
      el parent puede no existir ya; el daemon ignora rutas desconocidas.
    """
    if action not in ("add", "remove"):
        return None

    hidraw_path = device.get("DEVNAME")
    if not hidraw_path:
        return None

    if action == "add" and not is_wiimote(device):
        return None

    return [action, hidraw_path]


class Monitor(object):
    def __init__(self, queue):
        self.queue = queue

        self.__context = pyudev.Context()
        self.__monitor = pyudev.Monitor.from_netlink(self.__context, source="udev")

    def __first_scan(self):
        devices = self.__context.list_devices(subsystem="hidraw")
        for device in devices:
            event = classify_event("add", device)
            if event:
                self.queue.put(event)

    def run(self):
        # escuchar antes del first scan para no perder eventos en ese hueco;
        # un add duplicado (scan + evento) lo descarta el daemon.
        self.__monitor.filter_by(subsystem="hidraw")
        self.__monitor.start()

        self.__first_scan()

        for device in iter(self.__monitor.poll, None):
            event = classify_event(device.action, device)
            if event:
                self.queue.put(event)
