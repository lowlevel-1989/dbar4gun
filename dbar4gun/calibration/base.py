class CalibrationBase(object):
    def __init__(self):
        self.state  = 0
        self.offset = [0, 0]
        self.scale  = [1, 1]
        self.reset()

    def to_bytes(self, leds):
        return bytearray(bytes.fromhex("{:02x}".format(leds)))

    # return led and finished
    # b0000 0x00 NO UPDATE
    # b0001 0x10 LED 1
    # b0010 0x20 LED 2
    # b0100 0x40 LED 3
    # b1000 0x80 LED 4
    def step(self, button, cursor):
        leds = self.to_bytes(0x10)
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
