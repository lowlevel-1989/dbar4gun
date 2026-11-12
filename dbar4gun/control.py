"""
P1: socket Unix de control. Protocolo de texto: el cliente envia una linea y
recibe una linea JSON.

    area <perfil>               full | 4:3 | custom:x0,y0,w,h
    calibrate [player] [kind]   kind: full (por defecto) | quick
    status
    reload                      relee las calibraciones guardadas

El socket queda con permisos 0666 para que runcommand y la GUI (usuario pi)
puedan usarlo sin root; los comandos no dan acceso a nada fuera del driver.
"""

import json
import os
import socket
import threading

SOCKET_PATH = "/run/dbar4gun.sock"
MAX_LINE = 4096


class ControlServer(threading.Thread):
    def __init__(self, handler, path=SOCKET_PATH):
        super(ControlServer, self).__init__()
        self.daemon = True
        self.handler = handler
        self.path = path
        self.running = False
        self.sock = None

    def bind(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        os.chmod(self.path, 0o666)
        # para no borrar al salir el socket de otro daemon que lo haya rehecho
        self.inode = os.stat(self.path).st_ino
        self.sock.listen(4)
        self.sock.settimeout(0.5)
        self.running = True

    def run(self):
        if self.sock is None:
            self.bind()
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self._serve(conn)
            except Exception as e:
                try:
                    conn.sendall((json.dumps({"ok": False, "error": str(e)}) + "\n").encode())
                except OSError:
                    pass
            finally:
                conn.close()

    def _serve(self, conn):
        conn.settimeout(2.0)
        data = b""
        while b"\n" not in data and len(data) < MAX_LINE:
            chunk = conn.recv(1024)
            if not chunk:
                break
            data += chunk
        line = data.split(b"\n", 1)[0].decode("utf-8", "replace").strip()
        reply = self.handler(line)
        conn.sendall((json.dumps(reply, sort_keys=True) + "\n").encode())

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
        try:
            if os.stat(self.path).st_ino == getattr(self, "inode", None):
                os.unlink(self.path)
        except OSError:
            pass


def send_command(line, path=SOCKET_PATH, timeout=3.0):
    """Envia un comando y devuelve la respuesta JSON (dict)."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(path)
        s.sendall((line.strip() + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    finally:
        s.close()
    return json.loads(data.decode("utf-8"))


def parse_command(line):
    """'calibrate 2 quick' -> ("calibrate", ["2", "quick"])"""
    parts = line.split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]
