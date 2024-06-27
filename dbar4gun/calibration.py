
class TwoPointCalibration:
    def __init__(self, screen_point1, screen_point2, screen_size):
        self.screen_point1   = screen_point1
        self.screen_point2   = screen_point2
        self.screen_size     = screen_size

        self.reset()

    def reset(self):
        self.detected_point1 = self.screen_point1[:]
        self.detected_point2 = self.screen_point2[:]

    def set_gun_point1(self, gun_point):
        self.detected_point1 = gun_point

    def set_gun_point2(self, gun_point):
        self.detected_point2 = gun_point

    def calibrate(self):
        # Calculate the differences in screen coordinates
        dx_screen = self.screen_point2[0] - self.screen_point1[0]
        dy_screen = self.screen_point2[1] - self.screen_point1[1]

        # Calculate the differences in detected coordinates
        dx_detected = self.detected_point2[0] - self.detected_point1[0]
        dy_detected = self.detected_point2[1] - self.detected_point1[1]

        # Calculate scaling factors
        self.scale_x = dx_screen / dx_detected
        self.scale_y = dy_screen / dy_detected

        # Calculate offsets
        self.offset_x = self.screen_point1[0] - self.detected_point1[0] * self.scale_x
        self.offset_y = self.screen_point1[1] - self.detected_point1[1] * self.scale_y

    def map_coordinates(self, detected_point):
        # Map detected coordinates to screen coordinates
        mapped_x = detected_point[0] * self.scale_x + self.offset_x
        mapped_y = detected_point[1] * self.scale_y + self.offset_y

        mapped_x = max(0, min(mapped_x, self.screen_size[0]))
        mapped_y = max(0, min(mapped_y, self.screen_size[1]))

        return (int(mapped_x), int(mapped_y))
