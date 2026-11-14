"""
Orden de las VirtualGun en RetroArch: RetroArch numera los ratones por su
ruta en /sys como texto (input100 antes que input99), y una pistola nueva
podria quitarle el jugador 1 a otra. Si pasa, se recrean en orden de
encendido.
"""

import logging
import threading
import time

from dbar4gun import mouseindex


log = logging.getLogger("dbar4gun")

# cada cuanto se comprueba que RetroArch numera las VirtualGun en el orden en
# que se encendieron los Wiimotes, y vueltas maximas para corregirlo
ORDER_CHECK = 3.0
ORDER_ROUNDS = 3
# un worker tarda en recrear su VirtualGun lo que udev en clasificarla (~1 s)
RECREATE_TIMEOUT = 3.0


class GunOrder(object):
    """Mantiene el orden de encendido de las pistolas en RetroArch."""

    def start_order_check(self):
        t = threading.Thread(target=self._order_loop, name="dbar4gun-order", daemon=True)
        t.start()

    def _order_loop(self):
        while True:
            time.sleep(ORDER_CHECK)
            try:
                self.check_gun_order()
            except Exception as e:
                log.debug("VirtualGun order: %s", e)

    def update_gun_order(self, guns):
        """
        Orden de encendido: las que ya estaban conservan su puesto y las nuevas
        (o recreadas por su worker) van detras, por orden de creacion.
        """
        order = [p for p in self.gun_order
                 if p in guns and self.gun_seen.get(p) == guns[p][0]]
        new = sorted((p for p in guns if p not in order), key=lambda p: guns[p][0])
        self.gun_order = order + new
        self.gun_seen = {p: guns[p][0] for p in self.gun_order}
        return self.gun_order

    def check_gun_order(self, sysfs="/sys", pointer_order=None):
        """
        RetroArch numera los ratones por su ruta en /sys como texto: una
        VirtualGun nueva con input100 va antes que otra con input99 y le
        quita el jugador. Si pasa, se recrean todas en orden de encendido
        (los numeros solo crecen: quedan con las mismas cifras). True si el
        orden es correcto.
        """
        pointer_order = pointer_order or mouseindex.pointer_order
        for _ in range(ORDER_ROUNDS):
            guns = mouseindex.virtualguns(sysfs)
            order = self.update_gun_order(guns)
            if len(order) < 2 or mouseindex.in_order(order, guns, pointer_order()):
                return True
            log.info("VirtualGun order: RetroArch would not follow the power-on order %s, "
                     "recreating them", [p + 1 for p in order])
            for p in order:
                self._ask_workers("recreate", ports=[p], timeout=RECREATE_TIMEOUT)
            # las recreadas conservan su puesto en el orden de encendido
            guns = mouseindex.virtualguns(sysfs)
            self.gun_seen = {p: guns[p][0] for p in self.gun_order if p in guns}
        log.warning("VirtualGun order: could not be fixed")
        return False
