import os
import io
import re
import time
import struct
import evdev
import math

from pprint import pprint

mouse_cap = {
    evdev.ecodes.EV_KEY: [
        evdev.ecodes.BTN_LEFT, evdev.ecodes.BTN_RIGHT,
        ],
    evdev.ecodes.EV_ABS: [
        (evdev.ecodes.ABS_X, evdev.AbsInfo(value=0,
                min=0, max=1920, fuzz=0, flat=0, resolution=0)),
        (evdev.ecodes.ABS_Y, evdev.AbsInfo(value=0,
                min=0, max=1080, fuzz=0, flat=0, resolution=0)),
    ]
}

mouse = evdev.UInput(mouse_cap,
                     name="VirtualGun mouse",
                     product=0x19, vendor=0x89, version=0x01)

print(mouse.capabilities(verbose=True))

print(mouse.name)
print(mouse.product)
print(mouse.vendor)
print(mouse.version)
print(mouse.phys)
print(mouse.device)
print(mouse.device.path)
print(mouse.devnode)

event = os.path.basename(mouse.device.path)

path = f"/sys/class/input/{event}/device/"

mouse = None
for entry in os.listdir(path):
    print("entry:", entry)
    if "mouse" in entry:
        mouse = entry
        break

index = 0
if mouse:
    match = re.search(r'mouse(\d+)', mouse)
    if match:
        index = int(match.group(1))

print("mouse:", mouse)
print("index:", index)



