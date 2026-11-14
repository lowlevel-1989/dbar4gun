"""
Orden de las VirtualGun en RetroArch: se respeta el orden de encendido.

RetroArch numera los ratones por su ruta en /sys como texto: una VirtualGun
creada despues con input100 iba antes que otra con input99 y le quitaba el
jugador 1 sin apagar el primer Wiimote (medido en una Raspberry Pi 5 con
input87 e input106, y reproducido en un PC con input996 e input1000).
"""

import os
import shutil
import types

from dbar4gun import mouseindex
from dbar4gun.daemon.service import Dbar4Gun


class FakeSys(object):
    """/sys/class/input con VirtualGun que se pueden crear y recrear."""

    def __init__(self, tmp_path, first):
        self.root = str(tmp_path)
        self.next = first

    def path(self, number):
        return os.path.join(self.root, "class", "input", "input%d" % number)

    def create(self, port):
        number = self.next
        self.next += 1
        folder = self.path(number)
        os.makedirs(os.path.join(folder, "event%d" % number))
        with open(os.path.join(folder, "name"), "w") as f:
            f.write("VirtualGun %02d\n" % (port + 1))
        return number

    def recreate(self, port):
        number = mouseindex.virtualguns(self.root)[port][0]
        shutil.rmtree(self.path(number))
        return self.create(port)

    def pointer_order(self):
        # libudev: por la ruta en /sys, como texto
        guns = mouseindex.virtualguns(self.root)
        return [ev for _, (num, ev) in sorted(guns.items(), key=lambda g: "input%d" % g[1][0])]

    def players(self, ports):
        order = self.pointer_order()
        guns = mouseindex.virtualguns(self.root)
        return [order.index(guns[p][1]) + 1 for p in ports]


def make_daemon(fake):
    d = Dbar4Gun(types.SimpleNamespace(width=1920, height=1080, port=35460), None, None, None)
    d.sock.close()
    asked = []

    def ask(cmd, args=(), ports=None, timeout=None):
        assert cmd == "recreate"
        for p in ports:
            asked.append(p)
            fake.recreate(p)
        return [(p, {"ok": True}) for p in ports]

    d._ask_workers = ask
    return d, asked


def test_virtualguns_from_sysfs(tmp_path):
    fake = FakeSys(tmp_path, 99)
    fake.create(0)
    fake.create(1)
    assert mouseindex.virtualguns(fake.root) == {0: (99, "event99"), 1: (100, "event100")}


def test_input100_goes_before_input99_in_retroarch(tmp_path):
    fake = FakeSys(tmp_path, 99)
    fake.create(0)                       # Wiimote 1, encendido primero
    fake.create(1)                       # Wiimote 2
    guns = mouseindex.virtualguns(fake.root)
    assert fake.players([0, 1]) == [2, 1]
    assert not mouseindex.in_order([0, 1], guns, fake.pointer_order())


def test_later_wiimote_does_not_take_player_1(tmp_path):
    fake = FakeSys(tmp_path, 87)
    d, asked = make_daemon(fake)
    fake.create(0)
    assert d.check_gun_order(fake.root, fake.pointer_order)
    assert asked == []
    fake.next = 106                      # el kernel ya ha creado otros dispositivos
    fake.create(1)
    assert d.check_gun_order(fake.root, fake.pointer_order)
    assert asked == [0, 1]               # se recrean en orden de encendido
    assert fake.players([0, 1]) == [1, 2]


def test_power_on_order_is_kept(tmp_path):
    """El orden de encendido es el que vale, no el slot: no se toca nada."""
    fake = FakeSys(tmp_path, 20)
    d, asked = make_daemon(fake)
    fake.create(1)                       # se enciende primero el Wiimote del slot 2
    d.check_gun_order(fake.root, fake.pointer_order)
    fake.create(0)
    assert d.check_gun_order(fake.root, fake.pointer_order)
    assert asked == []
    assert d.gun_order == [1, 0]
    assert fake.players([1, 0]) == [1, 2]


def test_recreated_guns_keep_their_place(tmp_path):
    fake = FakeSys(tmp_path, 98)
    d, asked = make_daemon(fake)
    for port in (0, 1):
        fake.create(port)
        d.check_gun_order(fake.root, fake.pointer_order)
    fake.create(2)                       # input100: cambian las cifras
    assert d.check_gun_order(fake.root, fake.pointer_order)
    assert d.gun_order == [0, 1, 2]
    assert fake.players([0, 1, 2]) == [1, 2, 3]
    asked.clear()
    assert d.check_gun_order(fake.root, fake.pointer_order)
    assert asked == []                   # ya en orden: no se vuelve a recrear


def test_gun_replaced_by_its_worker_goes_last(tmp_path):
    """Si una VirtualGun desaparece y su puerto vuelve con otra, es la ultima encendida."""
    fake = FakeSys(tmp_path, 10)
    d, asked = make_daemon(fake)
    for port in (0, 1):
        fake.create(port)
        d.check_gun_order(fake.root, fake.pointer_order)
    fake.recreate(0)                     # el Wiimote del slot 1 se ha cambiado
    assert d.check_gun_order(fake.root, fake.pointer_order)
    assert d.gun_order == [1, 0]
    assert asked == []
