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
        _BL = self.BL
        _BR = self.BR

        self.core_ir_dot_sorted_prev = self.core_ir_dot_sorted[:]

        dots = []
        for i in range(4):
            dot = ir_dots[i]

            if not dot[_K]:
                dot = [0.0, 1.0, 0.0]

            dots.append(dot)

        dots_ok = sorted(dots, key=lambda dot: dot[_K], reverse=True)

        self.core_ir_dot_sorted[_TL] = self.core_ir_dot_sorted_prev[_TL]
        self.core_ir_dot_sorted[_TL][_K] = 0.0
        self.core_ir_dot_sorted[_TR] = self.core_ir_dot_sorted_prev[_TR]
        self.core_ir_dot_sorted[_TR][_K] = 0.0
        self.core_ir_dot_sorted[_BL] = self.core_ir_dot_sorted_prev[_BL]
        self.core_ir_dot_sorted[_BL][_K] = 0.0
        self.core_ir_dot_sorted[_BR] = self.core_ir_dot_sorted_prev[_BR]
        self.core_ir_dot_sorted[_BR][_K] = 0.0

        pitch, roll = self.get_angle_from_acc(acc)

        roll = math.degrees(roll)

        dots_ok_comb = list(itertools.combinations(dots_ok[:], 2))
        is_hit = False
        for dot in dots_ok_comb:

            p1, p2 = dot

            if p1[_X] > p2[_X]:
                dot = [p2, p1]

            angle = math.degrees(math.atan2(
                                    dot[1][_Y] - dot[0][_Y],
                                    dot[1][_X] - dot[0][_X]) * -1)

            adiff = abs(roll - angle)
            if adiff < 30 and dot[0][_K] and dot[1][_K]:
                dots_ok[0] = dot[0]
                dots_ok[1] = dot[1]
                dots_ok[2] = [0.0, 1.0, 0.0]
                dots_ok[3] = [0.0, 1.0, 0.0]
                is_hit = True
                break

        if not is_hit and dots_ok[0][_K] and dots_ok[1][_K]:
            dots_ok[_TL] = self.core_ir_dot_sorted_prev[_TL]
            dots_ok[_TR] = self.core_ir_dot_sorted_prev[_TR]
            dots_ok[_BL] = self.core_ir_dot_sorted_prev[_BL]
            dots_ok[_BR] = self.core_ir_dot_sorted_prev[_BR]

            dots_ok[_TL][_K] = 0.0
            dots_ok[_TR][_K] = 0.0
            dots_ok[_BL][_K] = 0.0
            dots_ok[_BR][_K] = 0.0

        if (dots_ok[0][_K] and dots_ok[1][_K]):

            self.core_ir_dot_sorted[_TL] = dots_ok[0]
            self.core_ir_dot_sorted[_TR] = dots_ok[1]

            if dots_ok[0][_X] > dots_ok[1][_X]:
                self.core_ir_dot_sorted[_TL] = dots_ok[1]
                self.core_ir_dot_sorted[_TR] = dots_ok[0]

        elif (dots_ok[0][_K] and not dots_ok[1][_K]):

            self.core_ir_dot_sorted[_TL] = dots_ok[0]
            self.core_ir_dot_sorted[_TR] = self.core_ir_dot_sorted_prev[_TR]

            # Valida si se sale por la izquerda
            if dots_ok[0][_X] < 0.5:
                self.core_ir_dot_sorted[_TL] = self.core_ir_dot_sorted_prev[_TL]
                self.core_ir_dot_sorted[_TR] = dots_ok[0]

        self.core_ir_dot_sorted[_BL] =  dots_ok[2]
        self.core_ir_dot_sorted[_BR] =  dots_ok[3]

        """
        if abs(pitch) > 70.5:
            if pitch > 0:
                print(1)
            else:
                print(0)
        """

        return self.core_ir_dot_sorted

