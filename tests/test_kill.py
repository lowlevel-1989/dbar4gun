"""
Parar el daemon: solo se mata un proceso de dbar4gun y se limpian el
archivo PID y el socket de control.
"""

import os
import subprocess
import sys
import time
import types

import pytest

from dbar4gun.daemon.pidfile import is_dbar4gun_process
from dbar4gun.daemon.service import Dbar4Gun


@pytest.fixture
def daemon(tmp_path):
    config = types.SimpleNamespace(width=1920, height=1080, port=35460)
    d = Dbar4Gun(config, None, None, None)
    d.pid_file = str(tmp_path / "dbar4gun.pid")
    yield d
    d.sock.close()


def _spawn(argv):
    p = subprocess.Popen(argv)
    time.sleep(0.1)
    return p


def test_foreign_process_is_not_killed(daemon):
    victim = _spawn(["sleep", "30"])
    try:
        with open(daemon.pid_file, "w") as f:
            f.write(str(victim.pid))

        assert daemon.kill() == 0
        time.sleep(0.1)

        assert victim.poll() is None, "un proceso ajeno fue terminado"
        assert not os.path.exists(daemon.pid_file)
    finally:
        victim.kill()
        victim.wait()


def test_dbar4gun_process_is_terminated(daemon):
    # un proceso cuyo cmdline contiene "dbar4gun"
    target = _spawn([sys.executable, "-c",
                     "import time; time.sleep(30)", "dbar4gun"])
    try:
        assert is_dbar4gun_process(target.pid)
        with open(daemon.pid_file, "w") as f:
            f.write(str(target.pid))

        assert daemon.kill() == 0
        assert target.wait(timeout=5) != 0
    finally:
        if target.poll() is None:
            target.kill()
            target.wait()


@pytest.mark.parametrize("content", ["", "garbage", "999999999", str(os.getpid())])
def test_stale_pid_file_is_removed(daemon, content):
    with open(daemon.pid_file, "w") as f:
        f.write(content)
    assert daemon.kill() == 0
    assert not os.path.exists(daemon.pid_file)


def test_no_pid_file(daemon):
    assert daemon.kill() == 0


@pytest.mark.parametrize("args,expected", [
    (["/opt/retropie/supplementary/dbar4gun/bin/python3",
      "/opt/retropie/supplementary/dbar4gun/bin/dbar4gun", "start", "--width", "1920"], True),
    (["/usr/bin/dbar4gun", "--width", "1920"], True),                 # sin subcomando = start
    (["/usr/bin/dbar4gun", "attach", "/dev/hidraw0"], True),
    (["python3", "-m", "dbar4gun.command", "start"], True),
    (["/usr/bin/dbar4gun", "gui", "--port", "35000"], False),        # el calibrator
    (["/usr/bin/dbar4gun", "status"], False),
    (["/usr/bin/dbar4gun", "profile", "start", "arcade", "mame"], False),
    (["vim", "dbar4gun.py"], False),
    (["sleep", "30"], False),
])
def test_daemon_cmdline(args, expected):
    from dbar4gun.daemon.pidfile import is_daemon_cmdline
    assert is_daemon_cmdline(args) is expected


def test_kill_waits_for_the_old_daemon(daemon):
    """
    El daemon anterior tarda en salir: kill() espera, para que al terminar no
    borre el pid file ni el socket del daemon nuevo.
    """
    code = ("import signal, sys, time\n"
            "signal.signal(signal.SIGTERM, lambda *a: (time.sleep(0.5), sys.exit(0)))\n"
            "time.sleep(30)\n")
    target = subprocess.Popen([sys.executable, "-c", code, "dbar4gun", "start"])
    time.sleep(0.3)
    try:
        with open(daemon.pid_file, "w") as f:
            f.write(str(target.pid))
        t0 = time.monotonic()
        assert daemon.kill() == 0
        assert time.monotonic() - t0 >= 0.4
        target.wait(timeout=5)
    finally:
        if target.poll() is None:
            target.kill()
            target.wait()


def test_stop_keeps_a_pid_file_that_is_not_ours(daemon):
    with open(daemon.pid_file, "w") as f:
        f.write("12345")
    daemon.stop()
    assert open(daemon.pid_file).read() == "12345"
    with open(daemon.pid_file, "w") as f:
        f.write(str(os.getpid()))
    daemon.stop()
    assert not os.path.exists(daemon.pid_file)


def test_control_socket_of_another_daemon_is_kept(tmp_path):
    from dbar4gun.control import ControlServer
    path = str(tmp_path / "ctl.sock")
    old = ControlServer(lambda line: {"ok": True}, path)
    old.bind()
    new = ControlServer(lambda line: {"ok": True}, path)
    new.bind()                      # el daemon nuevo rehace el socket
    old.stop()                      # el viejo sale despues: no debe borrarlo
    assert os.path.exists(path)
    new.stop()
    assert not os.path.exists(path)
