# Button map

English | [Español](mapping.es.md)

What each Wiimote button sends with dbar4gun, and what it does in MAME and in
RetroArch with their default settings (MAME 0.276 / lr-mame, RetroArch 1.19.1 as
configured by RetroPie).

## How it works

- **Auto key**: each gun sends the **MAME default keys of its player** (gun 1 =
  player 1, gun 2 = player 2...). Games are comfortable to play without mapping the
  buttons; the exceptions are in [retroarch](../retroarch).
- **Shared buttons and combos**: the same key on every gun (menus, exit...).
- The gun number is the order of the VirtualGun in RetroArch (`mouse index`); the
  Wiimote LEDs show it.

## Buttons that are the same on every gun

| button       | dbar4gun sends | MAME                     | RetroArch                        |
|--------------|----------------|--------------------------|----------------------------------|
| ir           | mouse cursor   | gun aim                  | gun aim                          |
| b            | mouse left     | trigger (button 1)       | trigger                          |
| 1            | mouse middle   |                          |                                  |
| 2            | mouse right    |                          | reload                           |
| home         | `enter`        | UI select (in the menus) | start of player 1 (see clashes)  |

## Auto key

| button         | gun 1      | gun 2 | gun 3        | gun 4           | MAME (player of the gun) |
|----------------|------------|-------|--------------|-----------------|--------------------------|
| d-pad left     | `left`     | `d`   | `j`          | `keypad 4`      | left                     |
| d-pad right    | `right`    | `g`   | `l`          | `keypad 6`      | right                    |
| d-pad down     | `down`     | `f`   | `k`          | `keypad 2`      | down                     |
| d-pad up       | `up`       | `r`   | `i`          | `keypad 8`      | up                       |
| plus           | `1`        | `2`   | `3`          | `4`             | start                    |
| minus          | `5`        | `6`   | `7`          | `8`             | coin                     |
| a              | `left alt` | `s`   | `right shift`| `keypad .`      | button 2 (grenade, pedal...) |
| nunchuck z     | `b` (1)    | `q`   | `enter`      | `keypad enter`  | button 3                 |
| nunchuck c     | `left shift` | `w` | `keypad 1`   | `keypad 5`      | button 4 (guns 3 and 4: none) |
| nunchuck stick | as the d-pad |     |              |                 | direction                |

(1) MAME uses `space` for button 3 of player 1, but `space` is fast forward in
RetroArch, so gun 1 sends the free key `b`. MAME does not use it by default: to use
the Nunchuk Z as button 2 see [retroarch/mame](../retroarch/mame).

## Combos (every gun)

| combo      | dbar4gun sends | MAME                    | RetroArch           | dbar4gun                  |
|------------|----------------|-------------------------|---------------------|---------------------------|
| b + home   | `tab`          | menu                    |                     |                           |
| b + minus  | `esc`          | UI cancel               | exit the game       |                           |
| b + 1      | `space`        | also button 3 of player 1 | fast forward on/off |                         |
| b + 2      | `2`            | start of player 2       |                     |                           |
| a + home   | `f1`           |                         | menu                |                           |
| b + plus   |                |                         |                     | IR camera off / on        |
| a + plus   |                |                         |                     | calibration               |
| a + minus  |                |                         |                     | reset calibration         |

## Clashes with RetroArch

The auto key follows MAME. These MAME keys are also RetroArch defaults, and
RetroArch acts on them during the game:

| key     | button          | in RetroArch                    | what happens                         |
|---------|-----------------|---------------------------------|--------------------------------------|
| `f`     | gun 2 down      | fullscreen / window             | the window mode changes              |
| `l`     | gun 3 right     | fast forward while held         | the game speeds up                   |
| `k`     | gun 3 down      | frame advance                   | only while paused                    |
| `i`     | gun 3 up        | netplay: watch the game         | only in netplay                      |
| `enter` | gun 3 Z, home   | start of player 1 (keyboard)    | start of player 1 in the game        |
| `q`     | gun 2 Z         | L of player 1 (keyboard)        | button 5 of player 1 (light gun games do not use it) |

The first four are RetroArch hotkeys. To turn them off **only for the light gun
games**, add to the RetroArch config of that system
(`/opt/retropie/configs/lightgun/retroarch.cfg` in RetroPie), above the `#include`
line:

```
input_toggle_fullscreen = "nul"
input_hold_fast_forward = "nul"
input_frame_advance = "nul"
input_netplay_game_watch = "nul"
```

In those games, those functions are no longer on the keyboard; the rest of the
systems keep them. Fast forward is still on `space` (b + 1).

If the light gun emulators load another file (`--config ...` in
`/opt/retropie/configs/lightgun/emulators.cfg`), the lines go in that file.

`enter` and `q` are the keys of player 1 when playing RetroArch with the keyboard:
they are left as they are.
