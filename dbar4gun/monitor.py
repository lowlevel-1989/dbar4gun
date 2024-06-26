import pyudev


# udevadm info --query=all --name=/dev/hidraw0
# udevadm info -a -n /dev/hidraw0

class Monitor(object):
    def __init__(self, queue):
        self.queue = queue

        self.__context = pyudev.Context()
        self.__monitor = pyudev.Monitor.from_netlink(self.__context, source="udev")

    def __first_scan(self):
        devices = self.__context.list_devices(subsystem="hidraw")
        for device in devices:
            if device.get("ID_MODEL_FROM_DATABASE") != "Wii Remote Controller RVL-003" \
                    and device.parent.driver != "wiimote":
                continue

            hidraw_path = device.get("DEVNAME")
            if hidraw_path:
                self.queue.put(["add", hidraw_path])

    def run(self):
        self.__first_scan()

        self.__monitor.filter_by(subsystem="hidraw")
        for action, device in self.__monitor:
            if device.get("ID_MODEL_FROM_DATABASE") != "Wii Remote Controller RVL-003" \
                    and device.parent.driver != "wiimote":
                continue

            hidraw_path = device.get("DEVNAME")
            if not hidraw_path:
                continue

            """
            - add:    A device has been added (e.g. a USB device was plugged in)
            - remove: A device has been removed (e.g. a USB device was unplugged)
            - change: Something about the device changed (e.g. a device property)
            - move:   The device was renamed, moved, or re-parented
            """

            self.queue.put([action, hidraw_path])

