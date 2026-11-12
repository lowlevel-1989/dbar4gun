import os
import stat
import subprocess
import sys

import pytest

from dbar4gun.profiles import (
    parse_profiles, resolve_profile, install_hooks, uninstall_hooks, hook_block,
    BLOCK_BEGIN, BLOCK_END, DEFAULT_PROFILES,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TABLE = parse_profiles("""
default = full
arcade = 4:3        # comentario
arcade/lr-mame2015 = custom:0.1,0,0.8,1
lr-flycast = "full"
rom:luckywld = 5:4
""")


@pytest.mark.parametrize("args,want", [
    (("arcade", "lr-mame2003", "/roms/arcade/ghoul.zip"), "4:3"),
    (("arcade", "lr-mame2015", "/roms/arcade/x.zip"), "custom:0.1,0,0.8,1"),
    (("arcade", "lr-mame2015", "/roms/arcade/LuckyWld.zip"), "5:4"),
    (("dreamcast", "lr-flycast", "hotd2.gdi"), "full"),
    (("nes", "lr-fceumm", "duckhunt.nes"), "full"),
    (("ARCADE", "", ""), "4:3"),
])
def test_resolve(args, want):
    assert resolve_profile(TABLE, *args) == want


def test_default_profiles_parse():
    t = parse_profiles(DEFAULT_PROFILES)
    # RetroArch ya lleva el gun a la imagen del juego: nada de 4:3 para lr-*
    assert "default" not in t and "arcade" not in t
    assert resolve_profile(t, "arcade", "lr-mame", "opwolf.zip") == "default"
    assert resolve_profile(t, "lightgun", "lr-mame2003-plus", "area51.zip") == "default"
    assert resolve_profile(t, "nes", "lr-fceumm", "x.nes") == "default"
    from dbar4gun.core.area import AreaProfile
    for v in t.values():
        AreaProfile.parse(v)


USER_ONSTART = """#!/bin/bash
# hook del usuario
echo "start $1" >> /tmp/log
"""


def test_install_is_idempotent_and_keeps_user_content(tmp_path):
    start = tmp_path / "runcommand-onstart.sh"
    start.write_text(USER_ONSTART)
    os.chmod(str(start), 0o750)

    t1 = install_hooks(str(tmp_path), "/x/bin/dbar4gun")
    content1 = start.read_text()
    assert content1.startswith(USER_ONSTART)
    assert content1.count(BLOCK_BEGIN) == 1
    assert (tmp_path / "runcommand-onend.sh").read_text().startswith("#!/usr/bin/env bash")
    assert (tmp_path / "dbar4gun" / "profiles.cfg").exists()
    assert stat.S_IMODE(os.stat(str(start)).st_mode) == 0o750
    assert stat.S_IMODE(os.stat(str(tmp_path / "runcommand-onend.sh")).st_mode) == 0o755
    assert len(t1) == 3

    # segunda instalacion: no cambia nada
    assert install_hooks(str(tmp_path), "/x/bin/dbar4gun") == []
    assert start.read_text() == content1

    # profiles.cfg del usuario no se sobrescribe
    (tmp_path / "dbar4gun" / "profiles.cfg").write_text("default = 4:3\n")
    install_hooks(str(tmp_path), "/y/bin/dbar4gun")
    assert (tmp_path / "dbar4gun" / "profiles.cfg").read_text() == "default = 4:3\n"
    assert "/y/bin/dbar4gun" in start.read_text() and "/x/bin" not in start.read_text()

    uninstall_hooks(str(tmp_path))
    assert start.read_text() == USER_ONSTART
    assert uninstall_hooks(str(tmp_path)) == []


def test_hook_scripts_run_with_bash(tmp_path):
    """El bloque es bash valido y llama al binario con system, emulator y rom."""
    log = tmp_path / "calls"
    fake = tmp_path / "fakebin"
    fake.write_text('#!/bin/sh\necho "$@" >> {}\n'.format(log))
    os.chmod(str(fake), 0o755)
    install_hooks(str(tmp_path), str(fake))
    subprocess.check_call(["bash", str(tmp_path / "runcommand-onstart.sh"),
                           "arcade", "lr-mame2003", "/roms/a b.zip", "cmd"])
    subprocess.check_call(["bash", str(tmp_path / "runcommand-onend.sh"),
                           "arcade", "lr-mame2003", "/roms/a b.zip", "cmd"])
    assert log.read_text().splitlines() == [
        "profile start arcade lr-mame2003 /roms/a b.zip",
        "profile end",
    ]


def test_missing_binary_does_not_break_runcommand(tmp_path):
    install_hooks(str(tmp_path), str(tmp_path / "missing"))
    assert subprocess.call(["bash", str(tmp_path / "runcommand-onstart.sh"), "a", "b", "c"]) == 0


def test_cli_profile_and_hooks(tmp_path):
    from dbar4gun.control import ControlServer

    path = str(tmp_path / "s.sock")
    lines = []
    srv = ControlServer(lambda l: (lines.append(l), {"ok": True})[1], path)
    srv.bind()
    srv.start()
    profiles = tmp_path / "profiles.cfg"
    profiles.write_text("arcade = 4:3\n")
    try:
        def run(*a):
            return subprocess.run([sys.executable, "-m", "dbar4gun.command"] + list(a),
                                  cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  universal_newlines=True, timeout=20)
        assert run("profile", "start", "arcade", "lr-mame2003", "x.zip",
                   "--profiles", str(profiles), "--socket", path).returncode == 0
        assert run("profile", "end", "--profiles", str(profiles), "--socket", path).returncode == 0
        assert run("hooks", "install", "--configs-dir", str(tmp_path / "cfg")).returncode == 1
        (tmp_path / "cfg").mkdir()
        r = run("hooks", "install", "--configs-dir", str(tmp_path / "cfg"), "--bin", "/b/dbar4gun")
        assert r.returncode == 0 and "runcommand-onstart.sh" in r.stdout
    finally:
        srv.stop()
    assert lines == ["area 4:3", "area default"]


def test_cli_profile_uses_the_daemon_profiles_path(tmp_path):
    """
    Sin --profiles, el hook de runcommand usa el profiles.cfg del daemon (su
    --config-dir), no el directorio por defecto de la plataforma.
    """
    from dbar4gun.control import ControlServer

    profiles = tmp_path / "custom-dir" / "profiles.cfg"
    profiles.parent.mkdir()
    profiles.write_text("arcade = 4:3\n")
    lines = []

    def handler(line):
        lines.append(line)
        if line == "status":
            return {"ok": True, "profiles": str(profiles)}
        return {"ok": True}

    path = str(tmp_path / "s.sock")
    srv = ControlServer(handler, path)
    srv.bind()
    srv.start()
    try:
        r = subprocess.run([sys.executable, "-m", "dbar4gun.command", "profile", "start",
                            "arcade", "lr-mame2003", "x.zip", "--socket", path],
                           cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, timeout=20)
        assert r.returncode == 0, r.stdout
    finally:
        srv.stop()
    assert lines == ["status", "area 4:3"]


def test_status_reports_profiles_path(tmp_path):
    import types
    from dbar4gun.dbar4gun import Dbar4Gun
    d = Dbar4Gun(types.SimpleNamespace(width=1920, height=1080, port=35460,
                                      config_dir=str(tmp_path)), None, None, None)
    try:
        assert d.handle_command("status")["profiles"] == str(tmp_path / "profiles.cfg")
    finally:
        d.sock.close()
