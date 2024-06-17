import evdev
import pyudev

context = pyudev.Context()
devices = context.list_devices(subsystem="hidraw")
monitor = pyudev.Monitor.from_netlink(context, source='udev')
monitor.filter_by(subsystem='hidraw')

wiimote = []

for device in devices:
    if device.get("ID_MODEL_FROM_DATABASE") != "Wii Remote Controller RVL-003":
        continue

    hidraw_path = device.get("DEVNAME")
    if hidraw_path:
        wiimote.append(hidraw_path)
        print('add: {}'.format(device.get("DEVNAME")))
        print(wiimote)

for action, device in monitor:
    if device.get("ID_MODEL_FROM_DATABASE") != "Wii Remote Controller RVL-003":
        continue
    print('{0}: {1}'.format(action, device.get("DEVNAME")))

    hidraw_path = device.get("DEVNAME")
    if not hidraw_path:
        continue

    if action == "remove":
        try:
            wiimote.remove(hidraw_path)
        except:
            pass
    else:
        wiimote.append(hidraw_path)
    print(wiimote)

