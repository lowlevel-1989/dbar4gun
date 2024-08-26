from dbar4gun.calibration.base import CalibrationBase

# unsupport python < version 3.12
# from dbar4gun.calibration.base import Point2DCollection
# from dbar4gun.calibration.base import Vector3D
# from dbar4gun.calibration.base import Cursor
# from dbar4gun.calibration.base import LEDs
# from dbar4gun.calibration.base import IsDone

class CalibrationTopLeftTopRightBottomCenterPoint(CalibrationBase):
    def __init__(self):
        self.screen_topleft_point      = [0.0, 0.0]
        self.screen_topright_point     = [1.0, 0.0]
        self.screen_bottomcenter_point = [0.5, 1.0]

        self.target_topleft_point      = [0.05, 0.05]
        self.target_topright_point     = [0.95, 0.05]
        self.target_bottomcenter_point = [ 0.5, 0.95]

        self.gun_topleft_point      = self.screen_topleft_point[:]
        self.gun_topright_point     = self.screen_topright_point[:]
        self.gun_bottomcenter_point = self.screen_bottomcenter_point[:]

        super().__init__()

    def reset(self) -> None:
        self.gun_topleft_point      = self.screen_topleft_point[:]
        self.gun_topright_point     = self.screen_topright_point[:]
        self.gun_bottomcenter_point = self.screen_bottomcenter_point[:]

        super().reset()

    # unsupport python < version 3.12
    # def map_coordinates(self, point : Point2DCollection, acc : tuple[int, int, int]) -> Cursor:
    def map_coordinates(self, point, acc : tuple[int, int, int]):

        # set position target
        if   self.state == 1:
            return self.target_topleft_point[:]
        elif self.state == 3:
            return self.target_topright_point[:]
        elif self.state == 5:
            return self.target_bottomcenter_point[:]

        cursor = super().map_coordinates(point, acc)

        # calculate position on screen
        x = (cursor[self.X] - self.x_min) / self.width
        y = (cursor[self.Y] - self.y_min) / self.height

        x =  max(0.0, min(1.0, x))
        y =  max(0.0, min(1.0, y))

        return [x, y]


    # unsupport python < version 3.12
    # def step(self,
    #        button : bool,
    #        point  : Point2DCollection,
    #        acc    : tuple[int, int, int]) -> tuple[IsDone, LEDs]:
    def step(self,
            button : bool,
            point,
            acc    : tuple[int, int, int]) -> tuple[bool, int]:

        # top left point (leds)
        if self.state == 0 and not button:
            self.state = 1
            return (False, self.LED_1)

        # top left point (capture)
        elif self.state == 1 and button and point[self.TR][self.K]:
            cursor = self.get_cursor(point)
            x = cursor[self.X] + (self.screen_topleft_point[self.X] - self.target_topleft_point[self.X])
            y = cursor[self.Y] + (self.screen_topleft_point[self.Y] - self.target_topleft_point[self.Y])
            self.gun_topleft_point = [x, y]
            self.state = 2
            return (False, self.LED_U)

        # top right point (leds)
        elif self.state == 2 and not button:
            self.state = 3
            return (False, self.LED_4)

        # top right point (capture)
        elif self.state == 3 and button and point[self.TL][self.K]:
            cursor = self.get_cursor(point)
            x = cursor[self.X] + (self.screen_topright_point[self.X] - self.target_topright_point[self.X])
            y = cursor[self.Y] + (self.screen_topright_point[self.Y] - self.target_topright_point[self.Y])
            self.gun_topright_point = [x, y]
            self.state = 4
            return (False, self.LED_U)

        # bottom center point (leds)
        elif self.state == 4 and not button:
            self.state = 5
            return (False, self.LED_2|self.LED_3)

        # bottom center point (capture)
        elif self.state == 5 and button and point[self.TL][self.K] and point[self.TR][self.K]:
            cursor = self.get_cursor(point)
            x = cursor[self.X] + (self.screen_bottomcenter_point[self.X] - self.target_bottomcenter_point[self.X])
            y = cursor[self.Y] + (self.screen_bottomcenter_point[self.Y] - self.target_bottomcenter_point[self.Y])
            self.gun_bottomcenter_point = [x, y]
            self.calibrate()
            self.state = 0

            return (True, self.LED_U)

        # continue
        return (False, self.LED_U)

    def calibrate(self) -> None:
        self.x_min = max(0.0, self.gun_topleft_point[self.X])
        self.y_min = max(0.0, ( self.gun_topleft_point[self.Y] + self.gun_topright_point[self.Y]) * 0.5)
        self.x_max = min(1.0, (( self.gun_bottomcenter_point[self.X] * 2) + self.gun_topright_point[self.X]) * 0.5)
        self.y_max = min(1.0, self.gun_bottomcenter_point[self.Y] )

        self.width  = self.x_max - self.x_min
        self.height = self.y_max - self.y_min
