class CalibrationBase(object):

    LED_U = 0x00
    LED_1 = 0x10
    LED_2 = 0x20
    LED_3 = 0x40
    LED_4 = 0x80

    def __init__(self):
        self.state  = 0
        self.offset = [0, 0]
        self.scale  = [1, 1]
        self.reset()

    def to_bytes(self, leds):
        return bytearray(bytes.fromhex("{:02x}".format(leds)))

    # return finished and leds
    def step(self, button, cursor):
        leds = self.to_bytes(self.LED_1)
        return [True, leds]

    def reset(self):
        self.state  = 0
        self.offset = [0, 0]
        self.scale  = [1, 1]
        self.calibrate()

    def calibrate(self):
        pass

    def map_coordinates(self, point):
        return point
