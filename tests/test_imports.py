"""Todos los modulos deben importar en python >= 3.7 (RetroPie sobre Buster)."""

import importlib

import pytest

MODULES = [
    "dbar4gun",
    "dbar4gun.info",
    "dbar4gun.command",
    "dbar4gun.dbar4gun",
    "dbar4gun.monitor",
    "dbar4gun.virtualgun",
    "dbar4gun.control",
    "dbar4gun.store",
    "dbar4gun.core",
    "dbar4gun.core.area",
    "dbar4gun.core.calibration",
    "dbar4gun.core.feedback",
    "dbar4gun.core.gun",
    "dbar4gun.core.parser",
    "dbar4gun.core.pointer",
    "dbar4gun.core.tracker",
    "dbar4gun.wiimote",
]


@pytest.mark.parametrize("name", MODULES)
def test_import(name):
    importlib.import_module(name)


def test_import_gui():
    pytest.importorskip("pygame")
    importlib.import_module("dbar4gun.gui")


def test_setup_lists_every_package():
    """setup.py enumera los paquetes a mano: uno olvidado rompe la instalacion."""
    import os
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "setup.py")) as f:
        listed = set(re.findall(r'"(dbar4gun(?:\.[a-z_]+)*)"', f.read()))
    for dirpath, _, files in os.walk(os.path.join(root, "dbar4gun")):
        if "__init__.py" in files:
            pkg = os.path.relpath(dirpath, root).replace(os.sep, ".")
            assert pkg in listed, pkg
