import math
import itertools

from dbar4gun.irsetup.base import IRSetupBase

class IRSetupStandard(IRSetupBase):

    # unsupport python < version 3.12
    # def sort_and_restore(self, dots : CoreIRCollection, acc : tuple[int, int, int]) -> CoreIRCollection:
    def sort_and_restore(self, ir_dots, acc : tuple[int, int, int]):

        _X  = self.X
        _Y  = self.Y
        _K  = self.K

        _TL = self.TL
        _TR = self.TR

        self.core_ir_dot_sorted_prev = self.core_ir_dot_sorted[:]

        self.core_ir_dot_sorted[_TL] = self.core_ir_dot_sorted_prev[_TL]
        self.core_ir_dot_sorted[_TL][_K] = 0.0
        self.core_ir_dot_sorted[_TR] = self.core_ir_dot_sorted_prev[_TR]
        self.core_ir_dot_sorted[_TR][_K] = 0.0

        pitch, roll = self.get_angle_from_acc(acc)

        roll  = math.degrees(roll)
        pitch = math.degrees(pitch)

        if abs(pitch) > 70.5:
            if pitch > 0:
                self.core_ir_dot_sorted[_TL]     = self.core_ir_dot_sorted_prev[_TL]
                self.core_ir_dot_sorted[_TL][_Y] = 0.0
                self.core_ir_dot_sorted[_TL][_K] = 0.0
                self.core_ir_dot_sorted[_TR]     = self.core_ir_dot_sorted_prev[_TR]
                self.core_ir_dot_sorted[_TR][_Y] = 0.0
                self.core_ir_dot_sorted[_TR][_K] = 0.0
            else:
                self.core_ir_dot_sorted[_TL]     = self.core_ir_dot_sorted_prev[_TL]
                self.core_ir_dot_sorted[_TL][_Y] = 1.0
                self.core_ir_dot_sorted[_TL][_K] = 0.0
                self.core_ir_dot_sorted[_TR]     = self.core_ir_dot_sorted_prev[_TR]
                self.core_ir_dot_sorted[_TR][_Y] = 1.0
                self.core_ir_dot_sorted[_TR][_K] = 0.0


        dots_ok = []
        for i in range(4):
            if ir_dots[i][_K]:
                dots_ok.append(ir_dots[i])

            if len(dots_ok) == 2:
                break


        for i in range(4):
            if not ir_dots[i][_K]:
                dots_ok.append(ir_dots[i])

        # sort
        if (dots_ok[0][_K] and dots_ok[1][_K]):

            self.core_ir_dot_sorted[_TL] = dots_ok[0]
            self.core_ir_dot_sorted[_TR] = dots_ok[1]

            if dots_ok[0][_X] > dots_ok[1][_X]:
                self.core_ir_dot_sorted[_TL] = dots_ok[1]
                self.core_ir_dot_sorted[_TR] = dots_ok[0]

        else:
            self.core_ir_dot_sorted = self.core_ir_dot_sorted_prev[:]

        return self.core_ir_dot_sorted

