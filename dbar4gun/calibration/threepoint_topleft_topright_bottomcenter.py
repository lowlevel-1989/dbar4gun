from dbar4gun.calibration.base import CalibrationBase

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

    def reset(self):
        self.gun_topleft_point      = self.screen_topleft_point[:]
        self.gun_topright_point     = self.screen_topright_point[:]
        self.gun_bottomcenter_point = self.screen_bottomcenter_point[:]

        super().reset()

    def map_coordinates(self, point):

        # set position target
        if   self.state == 1:
            return self.target_topleft_point[:]
        elif self.state == 3:
            return self.target_topright_point[:]
        elif self.state == 5:
            return self.target_bottomcenter_point[:]

        # calculate position on screen
        x = (point[0] - self.x_min) / self.width
        y = (point[1] - self.y_min) / self.height

        x =  max(0.0, min(1.0, x))
        y =  max(0.0, min(1.0, y))

        return (x, y)


    # return finished and leds
    def step(self, button, cursor):

        # top left point (leds)
        if self.state == 0 and button == False:
            self.state = 1
            leds = self.to_bytes(self.LED_1)
            return [False, leds]

        # top left point (capture)
        elif self.state == 1 and button and cursor[1] < 1.0:
            x = cursor[0] + (self.screen_topleft_point[0] - self.target_topleft_point[0])
            y = cursor[1] + (self.screen_topleft_point[1] - self.target_topleft_point[1])
            self.gun_topleft_point = [x, y]
            self.state = 2
            return [False, self.LED_U]

        # top right point (leds)
        elif self.state == 2 and button == False:
            self.state = 3
            leds = self.to_bytes(self.LED_4)
            return [False, leds]

        # top right point (capture)
        elif self.state == 3 and button and cursor[1] < 1.0:
            x = cursor[0] + (self.screen_topright_point[0] - self.target_topright_point[0])
            y = cursor[1] + (self.screen_topright_point[1] - self.target_topright_point[1])
            self.gun_topright_point = [x, y]
            self.state = 4
            return [False, self.LED_U]

        # bottom center point (leds)
        elif self.state == 4 and button == False:
            self.state = 5
            leds = self.to_bytes(self.LED_2|self.LED_3)
            return [False, leds]

        # bottom center point (capture)
        elif self.state == 5 and button and cursor[1] > 0:
            x = cursor[0] + (self.screen_bottomcenter_point[0] - self.target_bottomcenter_point[0])
            y = cursor[1] + (self.screen_bottomcenter_point[1] - self.target_bottomcenter_point[1])
            self.gun_bottomcenter_point = [x, y]
            self.calibrate()
            self.state = 0

            return [True, self.LED_U]

        # continue
        return [False, self.LED_U]

    def calibrate(self):
        self.x_min = max(0.0, self.gun_topleft_point[0])
        self.y_min = max(0.0, ( self.gun_topleft_point[1] + self.gun_topright_point[1]) / 2)
        self.x_max = min(1.0, (( self.gun_bottomcenter_point[0] * 2) + self.gun_topright_point[0]) /2)
        self.y_max = min(1.0, self.gun_bottomcenter_point[1] )

        self.width  = self.x_max - self.x_min
        self.height = self.y_max - self.y_min

