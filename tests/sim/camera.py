import math

SENSOR_W = 1024
SENSOR_H = 768
FOV_H_DEG = 33.0
# f = 512 / tan(16.5 grados) = 1728.5 px (pixeles cuadrados)
FOCAL_PX = (SENSOR_W / 2.0) / math.tan(math.radians(FOV_H_DEG / 2.0))


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def norm(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


WORLD_UP = (0.0, 1.0, 0.0)


class CameraPose(object):
    """
    Camara en `position` mirando a `target`, con roll en grados
    (positivo = Wiimote girado en sentido horario visto desde el jugador).

    Mundo: x a la derecha, y arriba, z hacia el jugador (la TV esta en z = 0).
    """

    def __init__(self, position, target, roll_deg=0.0):
        self.position = position
        f = norm(sub(target, position))
        r = norm(cross(f, WORLD_UP))
        u = cross(r, f)

        a = math.radians(roll_deg)
        c, s = math.cos(a), math.sin(a)
        # girar los ejes de la camara alrededor de f (horario visto desde atras)
        self.right = add(scale(r, c), scale(u, -s))
        self.up = add(scale(r, s), scale(u, c))
        self.forward = f

    def project(self, point):
        """(u, v) en px del sensor (v hacia abajo), o None si queda fuera del FOV."""
        d = sub(point, self.position)
        zc = dot(d, self.forward)
        if zc <= 1e-6:
            return None
        u = SENSOR_W / 2.0 + FOCAL_PX * dot(d, self.right) / zc
        v = SENSOR_H / 2.0 - FOCAL_PX * dot(d, self.up) / zc
        if not (0.0 <= u <= SENSOR_W - 1 and 0.0 <= v <= SENSOR_H - 1):
            return None
        return (u, v)

    def gravity(self):
        """
        Componentes de +1g (reaccion a la gravedad, hacia arriba) en ejes del
        acelerometro del Wiimote: (x = izquierda, y = delante, z = arriba).
        Como el hardware real (wiibrew; medido con el hardware check: con el
        Wiimote boca arriba, X positivo hacia la izquierda).
        """
        return (-dot(WORLD_UP, self.right),
                dot(WORLD_UP, self.forward),
                dot(WORLD_UP, self.up))
