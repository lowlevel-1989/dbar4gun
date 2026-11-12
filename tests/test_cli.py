import json
import os
import subprocess
import sys

import pytest

from dbar4gun.control import ControlServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args):
    return subprocess.run([sys.executable, "-m", "dbar4gun.command"] + list(args),
                          cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, timeout=20)


def test_version_and_help_keep_old_flags():
    assert run("version").returncode == 0
    out = run("start", "--help").stdout
    for flag in ("--calibration", "--setup", "--width", "--height", "--disable-tilt-correction",
                 "--port", "--smoothing-level", "--no-distance-compensation", "--area",
                 "--useful-zone", "--bar", "--calibration-targets", "--config-dir", "--socket"):
        assert flag in out, flag


@pytest.fixture
def server(tmp_path):
    path = str(tmp_path / "ctl.sock")
    lines = []

    def handler(line):
        lines.append(line)
        return {"ok": not line.startswith("area bad"), "line": line}

    srv = ControlServer(handler, path)
    srv.bind()
    srv.start()
    yield path, lines
    srv.stop()


def test_client_commands(server):
    path, lines = server
    r = run("area", "4:3", "--socket", path)
    assert r.returncode == 0 and json.loads(r.stdout)["line"] == "area 4:3"
    assert run("status", "--socket", path).returncode == 0
    assert run("calibrate", "2", "--quick", "--socket", path).returncode == 0
    assert run("calibrate", "--socket", path).returncode == 0
    assert run("reload", "--socket", path).returncode == 0
    assert run("area", "bad", "--socket", path).returncode == 1
    assert lines == ["area 4:3", "status", "calibrate 2 quick", "calibrate full", "reload", "area bad"]


def test_client_without_daemon(tmp_path):
    r = run("status", "--socket", str(tmp_path / "missing.sock"))
    assert r.returncode == 1 and "not reachable" in r.stdout
