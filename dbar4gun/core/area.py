"""
Perfil de area. MAME (y otros) estiran el rango ABS del gun sobre la imagen
del juego, que puede no ocupar toda la TV (4:3 dentro de 16:9).

    out = (x - x0) / w, con clamp a [0, 1]

Perfiles: "full", "<a>:<b>" (relacion de aspecto centrada, p. ej. "4:3") o
"custom:x0,y0,w,h" (normalizado a la TV completa).
"""


class AreaProfile(object):
    __slots__ = ("name", "x0", "y0", "w", "h")

    def __init__(self, name="full", x0=0.0, y0=0.0, w=1.0, h=1.0):
        if w <= 0 or h <= 0:
            raise ValueError("area: width and height must be > 0")
        self.name = name
        self.x0, self.y0, self.w, self.h = x0, y0, w, h

    @classmethod
    def parse(cls, text, screen_aspect=16.0 / 9.0):
        text = (text or "full").strip().lower()
        if text == "full":
            return cls("full")

        if text.startswith("custom:"):
            try:
                x0, y0, w, h = [float(v) for v in text[7:].split(",")]
            except ValueError:
                raise ValueError("area: expected custom:x0,y0,w,h")
            if not (0 <= x0 < 1 and 0 <= y0 < 1 and x0 + w <= 1.0001 and y0 + h <= 1.0001):
                raise ValueError("area: custom area outside the screen")
            return cls(text, x0, y0, w, h)

        if ":" in text:
            try:
                a, b = [float(v) for v in text.split(":")]
                aspect = a / b
            except (ValueError, ZeroDivisionError):
                raise ValueError("area: invalid aspect '{}'".format(text))
            if aspect <= 0:
                raise ValueError("area: invalid aspect '{}'".format(text))
            if aspect <= screen_aspect:
                # pillarbox: barras a los lados
                w = aspect / screen_aspect
                return cls(text, (1.0 - w) * 0.5, 0.0, w, 1.0)
            # letterbox: barras arriba y abajo
            h = screen_aspect / aspect
            return cls(text, 0.0, (1.0 - h) * 0.5, 1.0, h)

        raise ValueError("area: unknown profile '{}' (full, 4:3, custom:x0,y0,w,h)".format(text))

    def to_output(self, x, y):
        """Pantalla -> salida del gun, sin clamp."""
        return ((x - self.x0) / self.w, (y - self.y0) / self.h)

    def to_screen(self, ox, oy):
        """Salida del gun -> pantalla."""
        return (self.x0 + ox * self.w, self.y0 + oy * self.h)

    def to_dict(self):
        return {"name": self.name, "x0": self.x0, "y0": self.y0, "w": self.w, "h": self.h}

    def __repr__(self):
        return "AreaProfile({!r}, {:.4f}, {:.4f}, {:.4f}, {:.4f})".format(
            self.name, self.x0, self.y0, self.w, self.h)


def clamp01(v):
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v
