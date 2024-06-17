import evdev
import pyudev

context = pyudev.Context()
devices = context.list_devices(subsystem="hidraw")

for device in devices:
    for key in device.keys():
        print(f'{key}: {device.get(key)}')
    print('------')
"""
    hid_device = device.parent
    if hid_device.subsystem != "hid":
        continue



    if device.get("ID_MODEL_FROM_DATABASE") != "Wii Remote Controller RVL-003":
        continue

    print(list(device.keys()))
    print(device.get("ID_MODEL_FROM_DATABASE", ""))
    print(device.get("ID_VENDOR_FROM_DATABASE", ""))
    print('-' * 40)
    print("HIT ", device)
    print("HIT ", device.sys_name)
    print("HIT ", device.device_node)
    for child in hid_device.parent.children:
        print(child.get("DEVNAME", ""))
        print(child.get("ID_VENDOR_FROM_DATABASE", ""))
        print(child.get("ID_MODEL_FROM_DATABASE", ""))
        print(child.get("SUBSYSTEM", ""))
        #print(list(child.keys()))
        print('-' * 40)
"""
