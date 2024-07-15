
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
    # def sort_and_restore(self, dots : CoreIRCollection) -> CoreIRCollection:
    def sort_and_restore(self, ir_dots):

        return self.core_ir_dot_sorted

