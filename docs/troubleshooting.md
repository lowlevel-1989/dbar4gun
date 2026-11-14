# Known issues

English | [Español](troubleshooting.es.md)

## 1. Failure of IR LEDs on the DolphinBar

**Issue:** The DolphinBar has infrared LEDs that can burn out easily, making it impossible to aim correctly.
**Solution:** Replace the damaged LEDs or swap the bar for a new one. The calibrator's *IR diagnostics* shows each dot; with `--experimental-ir-extended` it also shows the dot size (a weak LED looks smaller).

## 2. I can move the pointer, but I can't shoot

**Issue:** If you can move the pointer but can't shoot, the driver may be detecting a keyboard or mouse as a second light gun.
**Solution:** Change the "mouse index" in the emulator settings to match the light gun's index and avoid conflicts. The calibrator's *Players and buttons* screen shows the LED → VirtualGun → mouse index map and the keys each button emits.

~~~
wiimote led 1  -> mouse index 0 (and 4, 8...)
wiimote led 2  -> mouse index 1
wiimote led 3  -> mouse index 2
wiimote led 4  -> mouse index 3
~~~

The LED shows the mouse index the way RetroArch numbers mice (udev): every
mouse in the system counts, in libudev's order. The keys of each gun are the
ones of the player with that mouse index, so in RetroArch the gun works for
that player without changing anything. The index is checked every 3 seconds:
if a mouse is plugged in or removed, the LED and the keys follow it. A
Wiimote connected by Bluetooth keeps its VirtualGun (and its place in the
list) when it disconnects and comes back.

When the driver takes a Wiimote (and every time it reconnects), the Wiimote
rumbles briefly and its LEDs sweep 1-2-3-4-all before showing its own LED. The
DolphinBar only lights a fixed LED, so the sweep tells you the driver has it.

## 3. The pointer becomes unstable for no apparent reason

**Issue:** The pointer moves erratically for no apparent reason.
**Possible Cause:** Sunlight, a lamp or a reflection interferes with the infrared sensor.
**Solution:** Check it with *IR diagnostics* in the calibrator (extra IR sources are drawn in red). Reflections and other sources are usually ignored now; if not, try another `--ir-sensitivity` level.

## 4. Calibration issues

**Issue:** Difficulties in calibrating the Wiimote properly.
**Possible Causes and solutions:**
- Two short rumbles: the capture was rejected (unsteady aim, or the bar was not visible). Hold still and shoot again.
- You are too close to the TV: the bottom of the screen is out of the camera's reach. Run the *Reach test* in the calibrator; it tells you how far to move back.
- If using DolphinBar, one of the IR LEDs may be damaged (see 1).

## 5. The crosshair does not reach the edges of the game

**Issue:** In 4:3 games on a 16:9 TV the gun range covers the whole TV.
**Solution:** With RetroArch (`lr-*` cores) use the `full` profile: RetroArch maps the gun to the game image itself. With a standalone emulator that stretches the gun range over the image, use the `4:3` area profile (`dbar4gun area 4:3`, the `--area` option or per game in `profiles.cfg`).
