"""P4: wrapper de escritorio (con un dbar4gun falso)."""

import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "platforms")


def fake_bin(tmp_path):
    log = tmp_path / "calls"
    fake = tmp_path / "dbar4gun"
    fake.write_text('#!/bin/sh\necho "$@" >> {}\n'.format(log))
    os.chmod(str(fake), 0o755)
    env = dict(os.environ, DBAR4GUN=str(fake))
    return log, env


def test_desktop_wrapper_keeps_exit_code(tmp_path):
    log, env = fake_bin(tmp_path)
    script = os.path.join(P, "desktop", "dbar4gun-run.sh")
    rc = subprocess.call([script, "arcade", "mame", "ghoul.zip", "--", "sh", "-c", "exit 3"], env=env)
    assert rc == 3
    assert log.read_text().splitlines() == ["profile start arcade mame ghoul.zip", "profile end"]
