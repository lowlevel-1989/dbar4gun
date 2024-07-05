from dbar4gun.calibration.base import CalibrationBase

class CalibrationCenterTopLeftPoint(CalibrationBase):
    def __init__(self):
        self.screen_center_point  = [0.5, 0.5]
        self.screen_topleft_point = [0.0, 0.0]

        self.target_center_point  = [ 0.5,  0.5]
        self.target_topleft_point = [0.05, 0.05]

        self.gun_center_point  = self.screen_center_point[:]
        self.gun_topleft_point = self.screen_topleft_point[:]

        super().__init__()

    def reset(self):
        self.gun_center_point  = self.screen_center_point[:]
        self.gun_topleft_point = self.screen_topleft_point[:]

        super().reset()

    def map_coordinates(self, point):

        # set position target
        if   self.state == 1:
            return self.target_center_point[:]
        elif self.state == 3:
            return self.target_topleft_point[:]

        # calculate position on screen
        x = (point[0] - self.x_min) / self.width
        y = (point[1] - self.y_min) / self.height

        x =  max(0.0, min(1.0, x))
        y =  max(0.0, min(1.0, y))

        return (x, y)


    # return finished and leds
    def step(self, button, cursor):

        # center point (leds)
        if self.state == 0 and button == False:
            self.state = 1
            leds = self.to_bytes(self.LED_2|self.LED_3)
            return [False, leds]

        # center point (capture)
        elif self.state == 1 and button and cursor[1] > 0:
            self.gun_center_point = cursor
            self.state = 2
            return [False, self.LED_U]

        # top left point (leds)
        elif self.state == 2 and button == False:
            self.state = 3
            leds = self.to_bytes(self.LED_1|self.LED_4)
            return [False, leds]

        # top left point (capture)
        elif self.state == 3 and button and cursor[1] < 1.0:
            x = cursor[0] + (self.screen_topleft_point[0] - self.target_topleft_point[0])
            y = cursor[1] + (self.screen_topleft_point[1] - self.target_topleft_point[1])
            self.gun_topleft_point = [x, y]
            self.calibrate()
            self.state = 0

            return [True, self.LED_U]

        # continue
        return [False, self.LED_U]

    def calibrate(self):
        self.x_min = max(0.0, self.gun_topleft_point[0])
        self.y_min = max(0.0, self.gun_topleft_point[1])
        self.x_max = min(1.0,
            ( self.gun_center_point[0] - self.gun_topleft_point[0] ) + \
                    self.gun_center_point[0] )
        self.y_max = min(1.0,
            ( self.gun_center_point[1] - self.gun_topleft_point[1] ) + \
                    self.gun_center_point[1] )

        self.width  = self.x_max - self.x_min
        self.height = self.y_max - self.y_min

