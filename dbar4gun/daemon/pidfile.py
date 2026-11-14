"""
Archivo PID y deteccion del daemon anterior: solo se para un proceso que sea
de verdad el daemon de dbar4gun.
"""

import os


PID_FILE = "/var/run/dbar4gun.pid"


# subcomandos que no son el daemon (el calibrator, los clientes del socket...)
CLIENT_COMMANDS = ("gui", "status", "area", "calibrate", "cancel", "reload", "hw",
                   "profile", "hooks", "version", "stop")

# espera a que el daemon anterior termine antes de crear el pid file y el socket
KILL_WAIT = 5.0


def is_daemon_cmdline(args):
    """
    True si los argumentos (de /proc/<pid>/cmdline) son los del daemon:
    el ejecutable `dbar4gun` (o `python -m dbar4gun...`) con `start`, `attach`
    o sin subcomando. `dbar4gun gui`, `dbar4gun status` o `vim dbar4gun.py` no.
    """
    for i, a in enumerate(args):
        if os.path.basename(a) == "dbar4gun" or \
                (a == "-m" and i + 1 < len(args) and args[i + 1].startswith("dbar4gun")):
            rest = args[i + 1:] if a != "-m" else args[i + 2:]
            sub = next((r for r in rest if not r.startswith("-")), None)
            return sub not in CLIENT_COMMANDS
    return False


def is_dbar4gun_process(pid):
    """True si /proc/<pid>/cmdline es el daemon de dbar4gun."""
    try:
        with open("/proc/{}/cmdline".format(int(pid)), "rb") as f:
            args = [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
    except (OSError, ValueError):
        return False
    return is_daemon_cmdline(args)
