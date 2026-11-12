"""
Mouse index de una VirtualGun tal como lo numera RetroArch (driver udev, el
que usan lr-mame y el resto de cores en RetroPie): los emuladores dan a cada
jugador el raton con su mismo indice, asi que si el indice que muestra el LED
es el correcto la pistola funciona sin configurar nada.

RetroArch (input/drivers/udev_input.c):
- enumera con libudev el subsistema "input" por propiedad: primero
  ID_INPUT_MOUSE=1 y despues ID_INPUT_TOUCHPAD=1 (y ID_INPUT_TOUCHSCREEN);
- solo cuentan los nodos eventN (un /dev/input/mouseN no admite los ioctl);
- el orden es el de la enumeracion de libudev (por ruta en /sys): los ratones
  USB, de plataforma o Bluetooth van antes que las VirtualGun
  (/sys/devices/virtual/input/...), y el touchpad de un portatil despues;
- en cada hotplug vuelve a numerar con los dispositivos que hay.

pyudev usa la misma libudev, asi que el orden es el mismo. No se abre ningun
dispositivo (abrir y cerrar los evdev de hid-wiimote apaga la camara IR).
"""

import logging

log = logging.getLogger("dbar4gun")

POINTER_PROPERTIES = ("ID_INPUT_MOUSE", "ID_INPUT_TOUCHPAD", "ID_INPUT_TOUCHSCREEN")


def _context():
    import pyudev
    return pyudev.Context()


def pointer_order(context=None):
    """Nombres eventN de los punteros, en el orden de RetroArch."""
    ctx = context or _context()
    out = []
    for prop in POINTER_PROPERTIES:
        for dev in ctx.list_devices(subsystem="input", **{prop: "1"}):
            name = dev.sys_name
            if name.startswith("event") and dev.device_node and name not in out:
                out.append(name)
    return out


def mouse_index(event, context=None):
    """
    Mouse index (1 = el primero) del nodo `event` ("event12" o
    "/dev/input/event12"), o None si udev aun no lo ha clasificado.
    """
    event = event.rsplit("/", 1)[-1]
    try:
        order = pointer_order(context)
    except Exception as e:
        log.debug("mouse index: %s", e)
        return None
    if event in order:
        return order.index(event) + 1
    return None
