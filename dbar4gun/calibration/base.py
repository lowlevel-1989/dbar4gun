import math

# unsupport python < version 3.12
# type Vector2D          = tuple[float, float]
# type Cursor            = Vector2D
# type Vector3D          = tuple[float, float, float]
# type Point2D           = Vector2D
# type Point2DCollection = tuple[Point2D, Point2D, Point2D, Point2D]
# type IsDone            = bool
# type LEDs              = int

class CalibrationBase(object):

    LED_U = 0x00
    LED_1 = 0x10
    LED_2 = 0x20
    LED_3 = 0x40
    LED_4 = 0x80

    TL = 0
    TR = 1
    BL = 2
    BR = 3

    X = 0
    Y = 1
    K = 2

    def __init__(self):
        self.state  = 0
        self.enable_tilt_correction = True
        self.reset()

    def set_tilt_correction(self, enable: bool) -> None:
        self.enable_tilt_correction = enable

    # unsupport python < version 3.12
    # def step(self,
    #        button : bool,
    #        point  : Point2DCollection,
    #        acc    : tuple[int, int, int]) -> tuple[IsDone, LEDs]:
    def step(self,
            button : bool,
            point,
            acc    : tuple[int, int, int]) -> tuple[bool, int]:


        return [True, self.LED_1]

    def reset(self) -> None:
        self.state  = 0
        self.calibrate()

    def calibrate(self) -> None:
        pass

    # unsupport python < version 3.12
    # def tilt_correction(self, point : Point2D) -> Cursor:
    def tilt_correction(self, point : tuple[float, float]) -> tuple[float, float]:

        # Calculate the angle of rotation using atan2 and invert the angle by multiplying by -1
        angle = math.atan2(
            point[self.TR][self.Y] - point[self.TL][self.Y],
            point[self.TR][self.X] - point[self.TL][self.X]) * -1

        cursor = self.get_cursor_raw(point)

        # transform origin 0, 0
        cursor[self.X] = cursor[self.X] - 0.5
        cursor[self.Y] = cursor[self.Y] - 0.5

        # apply the rotation transformation to the cursor
        rotx = math.cos(angle) * cursor[self.X] - math.sin(angle) * cursor[self.Y];
        roty = math.sin(angle) * cursor[self.X] + math.cos(angle) * cursor[self.Y];

        # re-center the rotated coordinates back to the screen coordinate system
        cursor[self.X] = 0.5 + rotx
        cursor[self.Y] = 0.5 + roty

        return cursor

    # TODO: optimize
    # unsupport python < version 3.12
    # def fix_offscreen(self, point : Point2D) -> Point2D:
    def fix_offscreen(self, point : tuple[float, float]) -> tuple[float, float]:
        distance_left   = point[self.X]
        distance_right  = 1 - point[self.X]
        distance_bottom = point[self.Y]
        distance_top    = 1 - point[self.Y]

        # Put the distances in a dictionary
        distances = {
            "left":   distance_left,
            "right":  distance_right,
            "bottom": distance_bottom,
            "top":    distance_top
        }

        # Determine which edge is the closest
        nearest_edge = min(distances, key=distances.get)

        # Adjust the object's position to the closest edge
        if nearest_edge   == "left":
            point[self.X] = 0
        elif nearest_edge == "right":
            point[self.X] = 1
        elif nearest_edge == "bottom":
            point[self.X] = 0
        elif nearest_edge == "top":
            point[self.X] = 1

        return point

    # unsupport python < version 3.12
    # def get_cursor_raw(self, point : Point2DCollection) -> Cursor:
    def get_cursor_raw(self, point) -> tuple[float, float]:
        cursor_raw = [
            (point[self.TR][self.X] + point[self.TL][self.X]) / 2,
            (point[self.TR][self.Y] + point[self.TL][self.Y]) / 2
        ]

        # agregar el rango completo a la pantalla
        x_min = 0.1
        y_min = 0.0
        x_max = 0.9
        y_max = 1.0

        width  = x_max - x_min
        height = y_max - y_min

        x = (cursor_raw[self.X] - x_min) / width
        y = (cursor_raw[self.Y] - y_min) / height

        x =  max(0.0, min(1.0, x))
        y =  max(0.0, min(1.0, y))

        return [x, y]

    def get_angle_from_acc(acc : tuple[int, int, int]):
        x, y, z = acc

        # The accelerometer readings are normally between 0 and 255
        # Neutral values are around 127
        x -= 127
        y -= 127
        z -= 127

        # Convert these readings to "g" acceleration (divide by 63.5)
        x_g = x / 63.5
        y_g = y / 63.5
        z_g = z / 63.5

        # Calculate angles using trigonometric functions
        roll  = math.atan2(y_g, z_g) * 180 / math.pi
        pitch = math.atan2(-x_g, math.sqrt(y_g**2 + z_g**2)) * 180 / math.pi

        return roll, pitch


    # unsupport python < version 3.12
    # def get_cursor(self, point : Point2DCollection) -> Cursor:
    def get_cursor(self, point) -> tuple[float, float]:
        if self.enable_tilt_correction and \
                point[self.TL][self.K] and point[self.TR][self.K]:
            return self.tilt_correction(point)
        return self.get_cursor_raw(point)

    # unsupport python < version 3.12
    # def map_coordinates(self, point : Point2DCollection, acc : tuple[int, int, int]) -> Cursor:
    def map_coordinates(self, point, acc : tuple[int, int, int]) -> tuple[float, float]:

        cursor = self.get_cursor(point)

        """
        if not point[self.TL][self.K] \
                and not point[self.TR][self.K] \
                and not point[self.BL][self.K] \
                and not point[self.BR][self.K]:

            cursor = self.fix_offscreen(cursor)
        """

        cursor[self.X] =  max(0.0, min(1.0, cursor[self.X]))
        cursor[self.Y] =  max(0.0, min(1.0, cursor[self.Y]))

        return cursor
