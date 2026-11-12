"""
C12: rumble sin bloquear el bucle. Los pulsos se apagan por timestamp: cada
report se llama a update(now) y devuelve el nuevo estado del motor si cambia.
"""

# (inicio, fin) en segundos desde que empieza el patron
PATTERN_OK = ((0.0, 0.12),)
PATTERN_ERROR = ((0.0, 0.12), (0.22, 0.34))
PATTERN_DONE = ((0.0, 0.30),)
# el driver ha tomado el Wiimote (al conectar y al reconectar)
PATTERN_CONNECT = ((0.0, 0.20),)

PATTERNS = {
    "ok": PATTERN_OK,
    "error": PATTERN_ERROR,
    "done": PATTERN_DONE,
    "connect": PATTERN_CONNECT,
}


class Rumble(object):
    def __init__(self):
        self.on = False
        self.pattern = None
        self.t0 = 0.0

    def start(self, pattern, now):
        if isinstance(pattern, str):
            pattern = PATTERNS[pattern]
        self.pattern = pattern
        self.t0 = now

    @property
    def active(self):
        return self.pattern is not None

    def update(self, now):
        """Nuevo estado (True/False) si cambia, si no None."""
        want = False
        if self.pattern is not None:
            dt = now - self.t0
            for a, b in self.pattern:
                if a <= dt < b:
                    want = True
                    break
            if dt >= self.pattern[-1][1]:
                self.pattern = None
        if want != self.on:
            self.on = want
            return want
        return None
