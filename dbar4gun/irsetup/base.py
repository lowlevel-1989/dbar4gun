import math

class IRSetupBase(object):

    X = 0
    Y = 1
    K = 2    # found dot

    TL = 0   # Top Left  index
    TR = 1   # Top Right index
    BL = 2   # Bottom Left index
    BR = 3   # Bottom Right index

    TC = 0   # Top Center index
    CL = 1   # Center Left index
    CR = 2   # Center Right index
    BC = 3   # Bottom Center index

    def __init__(self):
        self.core_ir_dot_sorted      = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        self.core_ir_dot_sorted_prev = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]

    # unsupport python < version 3.12
    # def sort_and_restore(self, dots : CoreIRCollection, acc : tuple[int, int, int]) -> CoreIRCollection:
    def sort_and_restore(self, ir_dots, acc : tuple[int, int, int]):
        return self.core_ir_dot_sorted

    def get_angle_from_acc(self, acc : tuple[int, int, int]) -> tuple[float, float]:
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
        roll  = math.atan2(y_g, z_g) * -1
        pitch = math.atan2(-x_g, math.sqrt(y_g**2 + z_g**2)) * -1

        return (roll, pitch)

