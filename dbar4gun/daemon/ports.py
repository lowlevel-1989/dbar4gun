"""
Puertos de las VirtualGun (VirtualGun 01 = puerto 0): en la DolphinBar cada
slot tiene siempre su VirtualGun; por Bluetooth, la primera libre.
"""


# entrada de un worker esperando a su Wiimote (en workers/processes/files)
DETACHED = "detached:"


def keeps_virtualgun(key):
    """
    Wiimotes cuya VirtualGun sobrevive a la desconexion: los de Bluetooth (su
    hidraw desaparece y vuelve con la misma MAC). En la DolphinBar el hidraw
    del slot no desaparece al apagar el Wiimote.
    """
    return bool(key) and key.startswith("bt:")


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
