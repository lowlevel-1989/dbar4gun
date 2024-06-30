from dbar4gun.calibration.base import CalibrationBase

class CalibrationCenterTopLeftPoint(CalibrationBase):
    def __init__(self):
        self.screen_center_point  = [0.5, 0.5]
        self.screen_topleft_point = [0.0, 0.0]

        self.gun_center_point  = self.screen_center_point[:]
        self.gun_topleft_point = self.screen_topleft_point[:]

        super().__init__()

    def reset(self):
        self.gun_center_point  = self.screen_center_point[:]
        self.gun_topleft_point = self.screen_topleft_point[:]

        super().reset()

    def map_coordinates(self, point):
        x = (point[0] - self.x_min) / self.width
        y = (point[1] - self.y_min) / self.height

        x =  max(0.0, min(1.0, x))
        y =  max(0.0, min(1.0, x))

        return (x, y)


    # return led and finished
    # b0000 0x00 NO UPDATE
    # b0001 0x10 LED 1
    # b0010 0x20 LED 2
    # b0100 0x40 LED 3
    # b1000 0x80 LED 4
    def step(self, button, cursor):

        # center point (leds)
        if self.state == 0 and button == False:
            self.state = 1
            leds = self.to_bytes(0x20|0x40)
            return [False, leds]

        # center point (capture)
        elif self.state == 1 and button:
            self.gun_center_point = cursor
            self.state = 2
            return [False, 0]

        # top left point (leds)
        elif self.state == 2 and button == False:
            self.state = 3
            leds = self.to_bytes(0x10|0x80)
            return [False, leds]

        # top left point (capture)
        elif self.state == 3 and button:
            self.gun_topleft_point = cursor
            self.calibrate()
            self.state = 0

            return [True, 0]

        # continue
        return [False, 0]

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

