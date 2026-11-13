"""Funciones del scriptmodule de RetroPie con stubs de las funciones de RetroPie-Setup."""

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, "retropie", "dbar4gun.sh")

STUBS = r'''
loadModuleConfig() { for kv in "$@"; do echo "local ${kv%%=*}=\"${kv#*=}\""; done; }
iniConfig() { :; }
iniSet() { :; }
printMsgs() { :; }
systemctl() { :; }
getDepends() { :; }
mkUserDir() { mkdir -p "$1"; }
setConfigRoot() { md_conf_root="$configdir${1:+/$1}"; }
addPort() { echo "ADDPORT mode=$md_mode root=$md_conf_root id=$1 port=$2 title=$3 cmd=$4"; }
__user="$(id -un)"
__group="$(id -gn)"
'''


def run_bash(tmp_path, body):
    md_inst = tmp_path / "inst"
    (md_inst / "bin").mkdir(parents=True, exist_ok=True)
    wrapper = md_inst / "bin" / "dbar4gun"
    wrapper.write_text('#!/bin/sh\ncd "{}" && exec "{}" -m dbar4gun.command "$@"\n'.format(ROOT, sys.executable))
    os.chmod(str(wrapper), 0o755)
    (tmp_path / "configs" / "all").mkdir(parents=True, exist_ok=True)
    script = STUBS + "\nsource '{}'\n".format(MODULE) + '''
md_inst="{inst}"
md_id="dbar4gun"
md_mode="install"
configdir="{cfg}"
home="{home}"
datadir="{home}/RetroPie"
romdir="{home}/RetroPie/roms"
user="$(id -un)"
f() {{
    eval $(_loadconfig_dbar4gun)
{body}
}}
f
'''.format(inst=md_inst, cfg=tmp_path / "configs", home=tmp_path / "home", body=body)
    return subprocess.run(["bash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, timeout=60)


def test_params_defaults(tmp_path):
    r = run_bash(tmp_path, '    _params_dbar4gun')
    assert r.returncode == 0, r.stdout
    out = r.stdout.strip()
    assert "--area full" in out and "--useful-zone 0.85" in out
    assert "--config-dir {}/all/dbar4gun".format(tmp_path / "configs") in out
    assert "--no-distance-compensation" not in out
    assert "--calibration 2" in out and "--smoothing-level 3" in out


def test_params_options(tmp_path):
    r = run_bash(tmp_path, '    db_area=4:3; db_distance_compensation=0; db_disable_tilt_correction=1\n'
                           '    _params_dbar4gun')
    out = r.stdout.strip()
    assert "--area 4:3" in out and "--no-distance-compensation" in out
    assert "--disable-tilt-correction" in out


def test_calibrator_entry(tmp_path):
    """
    El calibrator va a Ports con addPort (runcommand, sin sudo), como el
    "Desktop" de RetroPie: el menu de RetroPie se lanza con sudo y no funciona
    si el usuario necesita contrasena.
    """
    old = tmp_path / "home" / "RetroPie" / "retropiemenu" / "dbar4gun-calibrator.sh"
    old.parent.mkdir(parents=True)
    old.write_text("old entry")
    r = run_bash(tmp_path, '    _calibrator_entry_dbar4gun install')
    assert r.returncode == 0, r.stdout
    line = [l for l in r.stdout.splitlines() if l.startswith("ADDPORT")][0]
    assert "mode=install" in line and "root={}/ports".format(tmp_path / "configs") in line
    assert "id=dbar4gun port=dbar4gun title=dbar4gun calibrator" in line
    assert "cmd={}/bin/dbar4gun gui --port 35460".format(tmp_path / "inst") in line
    assert not old.exists()                     # la entrada vieja del menu se quita

    r = run_bash(tmp_path, '    _calibrator_entry_dbar4gun remove')
    line = [l for l in r.stdout.splitlines() if l.startswith("ADDPORT")][0]
    assert "mode=remove" in line and "title=dbar4gun calibrator" in line

@pytest.mark.parametrize("size,args", [
    ("native", ""),
    ("1280x720", " --width 1280 --height 720"),
    ("640x480", " --width 640 --height 480"),
])
def test_calibrator_size(tmp_path, size, args):
    r = run_bash(tmp_path, '    db_calibrator_size={}; db_port=35000; _calibrator_cmd_dbar4gun'.format(size))
    assert r.stdout.strip() == "{}/bin/dbar4gun gui --port 35000{}".format(tmp_path / "inst", args)


@pytest.mark.parametrize("lang,args", [("en", ""), ("es", " --lang es")])
def test_calibrator_lang(tmp_path, lang, args):
    r = run_bash(tmp_path, '    db_calibrator_lang={}; db_port=35000; _calibrator_cmd_dbar4gun'.format(lang))
    assert r.stdout.strip() == "{}/bin/dbar4gun gui --port 35000{}".format(tmp_path / "inst", args)


@pytest.mark.parametrize("value,ok", [("native", True), ("1280x720", True), ("big", False), ("1280", False)])
def test_calibrator_size_is_validated(tmp_path, value, ok):
    body = ('    iniSet() {{ echo "SET $1=$2"; }}\n'
            '    printMsgs() {{ echo "MSG $2"; }}\n'
            '    _set_calibrator_size_dbar4gun "{}"; echo "rc=$? size=$db_calibrator_size"').format(value)
    out = run_bash(tmp_path, body).stdout
    if ok:
        assert "rc=0 size={}".format(value) in out
    else:
        assert "rc=1 size=native" in out and "MSG Invalid" in out

def test_hooks_install_remove(tmp_path):
    r = run_bash(tmp_path, '    _hooks_dbar4gun install')
    assert r.returncode == 0, r.stdout
    onstart = tmp_path / "configs" / "all" / "runcommand-onstart.sh"
    assert "# >>> dbar4gun >>>" in onstart.read_text()
    assert (tmp_path / "configs" / "all" / "dbar4gun" / "profiles.cfg").exists()
    run_bash(tmp_path, '    _hooks_dbar4gun remove')
    assert "dbar4gun" not in onstart.read_text()


@pytest.mark.parametrize("func,value,ok", [
    ("_set_area_dbar4gun", "4:3", True),
    ("_set_area_dbar4gun", "custom:0.1,0.05,0.8,0.9", True),
    ("_set_area_dbar4gun", "16:10x", False),
    ("_set_area_dbar4gun", "", False),
    ("_set_useful_zone_dbar4gun", "0.9", True),
    ("_set_useful_zone_dbar4gun", "1.5", False),
    ("_set_useful_zone_dbar4gun", "abc", False),
])
def test_menu_values_are_validated(tmp_path, func, value, ok):
    """Un valor invalido no se guarda (el servicio no arrancaria) y se avisa."""
    body = '''    iniSet() {{ echo "SET $1=$2"; }}
    printMsgs() {{ echo "MSG $2"; }}
    {func} "{value}"; echo "rc=$?"
    echo "area=$db_area zone=$db_useful_zone"'''.format(func=func, value=value)
    r = run_bash(tmp_path, body)
    out = r.stdout
    if ok:
        assert "rc=0" in out and "SET " in out and "MSG" not in out, out
        assert value in out.split("area=")[1]
    else:
        assert "rc=1" in out and "SET " not in out and "MSG Invalid" in out, out
        assert "area=full zone=0.85" in out


def test_calibration_menu_offers_4_points():
    """El menu de RetroPie ofrece el modo 3 (4 puntos, mejor jugando de lado)."""
    src = open(MODULE).read()
    menu = src[src.index("function _menu_calibration_mode"):src.index("function _menu_set_resolution")]
    assert 'iniSet "db_calibration" "3"' in menu
    assert "BottomRight, BottomLeft" in menu
    # desactivar la calibracion es la ultima opcion
    assert menu.index('4 "disabled"') > menu.index("BottomRight, BottomLeft")
    assert menu.index('iniSet "db_calibration" "0"') > menu.index('iniSet "db_calibration" "3"')


def test_params_calibration_mode_3(tmp_path):
    r = run_bash(tmp_path, '    db_calibration=3; _params_dbar4gun')
    assert "--calibration 3" in r.stdout
