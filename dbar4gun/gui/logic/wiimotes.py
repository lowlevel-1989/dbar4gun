"""
Paquetes del daemon y estado de cada Wiimote.

- PacketSource: lee del socket UDP los paquetes que manda el daemon.
- WiimoteState: ultimo paquete y botones de un Wiimote.
- Hub: todos los Wiimotes; dice cual ha pulsado un boton.
- BTN_*: bits de los botones (los mismos que el Wiimote).
"""

import socket

from dbar4gun.protocol import Packet, SIZE


# botones (mismos bits que el Wiimote)
BTN_TWO = 1 << 0x0
BTN_ONE = 1 << 0x1
BTN_B = 1 << 0x2
BTN_A = 1 << 0x3
BTN_MINUS = 1 << 0x4
BTN_HOME = 1 << 0x7
BTN_LEFT = 1 << 0x8
BTN_RIGHT = 1 << 0x9
BTN_DOWN = 1 << 0xa
BTN_UP = 1 << 0xb
BTN_PLUS = 1 << 0xc

HISTORY = 64


class PacketSource(object):
    """Socket UDP no bloqueante; drain() devuelve todos los paquetes pendientes."""

    def __init__(self, port, host="127.0.0.1"):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.setblocking(False)

    def drain(self, limit=2000):
        out = []
        for _ in range(limit):
            try:
                data = self.sock.recv(SIZE + 16)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            p = Packet.unpack(data)
            if p is not None:
                out.append(p)
        return out

    def close(self):
        self.sock.close()


class WiimoteState(object):
    """Estado de un Wiimote en la GUI: ultimo paquete, history y flancos."""

    def __init__(self, virtualgun):
        self.virtualgun = virtualgun
        self.packet = None
        self.history = []
        self.prev_buttons = 0
        self.pressed = 0
        self.last_seen = 0.0
        self.frame_packets = []
        self.reach = None   # resultado de la reach test (fraccion de alto)
        self.status = {}    # ultimo status del socket de control

    def feed(self, packets, now):
        """Paquetes de este Wiimote recibidos en el frame (en orden)."""
        pressed = 0
        prev = self.prev_buttons
        for p in packets:
            pressed |= p.buttons & ~prev
            prev = p.buttons
            self.history.append(p)
        if len(self.history) > HISTORY:
            del self.history[:len(self.history) - HISTORY]
        self.frame_packets = packets
        if packets:
            self.packet = packets[-1]
            self.last_seen = now
        self.prev_buttons = prev
        self.pressed = pressed

    def was_pressed(self, mask):
        return bool(self.pressed & mask)

    def samples_before_last_b(self, n=8):
        """Cursores en pantalla de los n paquetes anteriores al ultimo flanco de B."""
        hist = self.history
        edge = None
        for i in range(len(hist) - 1, 0, -1):
            if hist[i].buttons & BTN_B and not hist[i - 1].buttons & BTN_B:
                edge = i
                break
        if edge is None:
            return []
        return [p.screen for p in hist[max(0, edge - n):edge]]


class Hub(object):
    """Todos los Wiimotes vistos y el reparto de paquetes por frame."""

    TIMEOUT = 2.0

    def __init__(self):
        self.guns = {}

    def update(self, packets, now):
        by_gun = {}
        for p in packets:
            by_gun.setdefault(p.virtualgun, []).append(p)
        for vg, plist in by_gun.items():
            if vg not in self.guns:
                self.guns[vg] = WiimoteState(vg)
        for vg, state in self.guns.items():
            state.feed(by_gun.get(vg, []), now)

    def active(self, now):
        return [s for vg, s in sorted(self.guns.items())
                if s.packet is not None and now - s.last_seen <= self.TIMEOUT]

    def first_pressed(self, mask, now):
        for s in self.active(now):
            if s.was_pressed(mask):
                return s
        return None

    def any_pressed(self, mask, now):
        return self.first_pressed(mask, now) is not None
