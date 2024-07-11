from dbar4gun.calibration.base import CalibrationBase

# unsupport python < version 3.12
# from dbar4gun.calibration.base import Point2DCollection
# from dbar4gun.calibration.base import Vector3D
# from dbar4gun.calibration.base import Cursor
# from dbar4gun.calibration.base import LEDs
# from dbar4gun.calibration.base import IsDone


class CalibrationCenterTopLeftPoint(CalibrationBase):
    def __init__(self):
        self.screen_center_point  = [0.5, 0.5]
        self.screen_topleft_point = [0.0, 0.0]

        self.target_center_point  = [ 0.5,  0.5]
        self.target_topleft_point = [0.05, 0.05]

        self.gun_center_point  = self.screen_center_point[:]
        self.gun_topleft_point = self.screen_topleft_point[:]

        super().__init__()

    def reset(self) -> None:
        self.gun_center_point  = self.screen_center_point[:]
        self.gun_topleft_point = self.screen_topleft_point[:]

        super().reset()

    # unsupport python < version 3.12
    # def map_coordinates(self, point : Point2DCollection, acc : Vector3D) -> Cursor:
    def map_coordinates(self, point, acc : tuple[float, float, float]) -> tuple[float, float]:

        # set position target
        if   self.state == 1:
            return self.target_center_point[:]
        elif self.state == 3:
            return self.target_topleft_point[:]

        cursor = super().map_coordinates(point, acc)

        # calculate position on screen
        x = (cursor[self.X] - self.x_min) / self.width
        y = (cursor[self.Y] - self.y_min) / self.height

        x =  max(0.0, min(1.0, x))
        y =  max(0.0, min(1.0, y))

        return (x, y)


    # unsupport python < version 3.12
    # def step(self,
    #        button : bool,
    #        point  : Point2DCollection,
    #        acc    : Vector3D) -> tuple[IsDone, LEDs]:
    def step(self,
            button : bool,
            point,
            acc    : tuple[float, float, float]) -> tuple[bool, int]:

        # center point (leds)
        if self.state == 0 and button == False:
            self.state = 1
            return [False, self.LED_2|self.LED_3]

        # center point (capture)
        elif self.state == 1 and button and point[self.TL][self.K] and point[self.TR][self.K]:
            cursor = self.get_cursor(point)
            self.gun_center_point = cursor
            self.state = 2
            return [False, self.LED_U]

        # top left point (leds)
        elif self.state == 2 and button == False:
            self.state = 3
            return [False, self.LED_1|self.LED_4]

        # top left point (capture)
        elif self.state == 3 and button and point[self.TR][self.K]:
            cursor = self.get_cursor(point)
            x = cursor[self.X] + (self.screen_topleft_point[self.X] - self.target_topleft_point[self.X])
            y = cursor[self.Y] + (self.screen_topleft_point[self.Y] - self.target_topleft_point[self.Y])
            self.gun_topleft_point = [x, y]
            self.calibrate()
            self.state = 0

            return [True, self.LED_U]

        # continue
        return [False, self.LED_U]

    def calibrate(self) -> None:
        self.x_min = max(0.0, self.gun_topleft_point[self.X])
        self.y_min = max(0.0, self.gun_topleft_point[self.Y])
        self.x_max = min(1.0,
            ( self.gun_center_point[self.X] - self.gun_topleft_point[self.X] ) + \
                    self.gun_center_point[self.X] )
        self.y_max = min(1.0,
            ( self.gun_center_point[self.Y] - self.gun_topleft_point[self.Y] ) + \
                    self.gun_center_point[self.Y] )

        self.width  = self.x_max - self.x_min
        self.height = self.y_max - self.y_min

