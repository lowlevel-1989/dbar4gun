from dbar4gun.irsetup.base import IRSetupBase

class IRSetupStandard(IRSetupBase):

    # unsupport python < version 3.12
    # def sort_and_restore(self, dots : CoreIRCollection) -> CoreIRCollection:
    def sort_and_restore(self, ir_dots):

        _X  = self.X
        _Y  = self.Y
        _K  = self.K

        _TL = self.TL
        _TR = self.TR
        _BL = self.BL
        _BR = self.BR

        self.core_ir_dot_sorted_prev = self.core_ir_dot_sorted[:]

        dots = []
        for i in range(4):
            dot = ir_dots[i]

            if not dot[_K]:
                dot = [1.0, 1.0, 0.0]

            dots.append(dot)

        dots_ok = sorted(dots, key=lambda dot: dot[_K], reverse=True)

        self.core_ir_dot_sorted[_TL] = self.core_ir_dot_sorted_prev[_TL]
        self.core_ir_dot_sorted[_TL][_K] = 0.0
        self.core_ir_dot_sorted[_TR] = self.core_ir_dot_sorted_prev[_TR]
        self.core_ir_dot_sorted[_TR][_K] = 0.0

        if (dots_ok[0][_K] and dots_ok[1][_K]):

            self.core_ir_dot_sorted[_TL] = dots_ok[0]
            self.core_ir_dot_sorted[_TR] = dots_ok[1]

            if dots_ok[0][_X] > dots_ok[1][_X]:
                self.core_ir_dot_sorted[_TL] = dots_ok[1]
                self.core_ir_dot_sorted[_TR] = dots_ok[0]

        elif (dots_ok[0][_K] and not dots_ok[1][_K]):

            self.core_ir_dot_sorted[_TL] = dots_ok[0]
            self.core_ir_dot_sorted[_TR] = self.core_ir_dot_sorted_prev[_TR]

            dx0 = abs(self.core_ir_dot_sorted_prev[_TL][_X] - dots_ok[0][_X])
            dx1 = abs(self.core_ir_dot_sorted_prev[_TR][_X] - dots_ok[0][_X])

            if dx0 > dx1:
                self.core_ir_dot_sorted[_TL] = self.core_ir_dot_sorted_prev[_TL]
                self.core_ir_dot_sorted[_TR] = dots_ok[0]

        return self.core_ir_dot_sorted

