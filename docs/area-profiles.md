# Area profiles

English | [Español](area-profiles.es.md)

An area profile tells dbar4gun which part of the screen the gun covers.

**Most setups do not need it: keep `full` (the default).** Emulators that turn the
gun position into the game image themselves already handle a 4:3 game on a 16:9
TV, and aiming outside the image is "offscreen", to reload:

- RetroArch: every `lr-*` core (lr-mame, lr-mame2003-plus, lr-mame2016, lr-flycast...).
- flycast standalone.

With them a `4:3` profile would correct the image twice and the aim would drift
towards the sides.

**When you need it:** with an emulator that stretches the whole gun range over the
game image. With `full`, a 4:3 game on a 16:9 TV then reaches its edge when you aim
at the edge of the TV, and the further from the center, the larger the error.
Real cases:

| Case | Profile |
|------|---------|
| MAME standalone (the `mame` program, without RetroArch): the default MAME on Batocera and Recalbox, and on a desktop PC | `4:3` |
| AdvanceMAME | `4:3` |
| A game in a window of the desktop, or an image that does not fill the TV (fixed bezel or artwork) | `custom:x0,y0,w,h` |
| Mixing emulators: MAME standalone for one game, RetroArch for the rest | per game in `profiles.cfg` |

`custom:x0,y0,w,h` is the rectangle of the game as a fraction of the TV: left edge,
top edge, width and height (`0.125,0,0.75,1` is a 4:3 image centered on a 16:9 TV).

How to set it:

- Default profile: `--area full|4:3|custom:x0,y0,w,h` (RetroPie-Setup → dbar4gun →
  *default area profile*).
- Per game: `profiles.cfg` in the config dir (`/opt/retropie/configs/all/dbar4gun/`
  on RetroPie). Priority: `rom:<name>` > `system/emulator` > `emulator` > `system`
  > `default`. RetroPie's runcommand hooks apply it when a game starts and go back
  to the default when it ends. For example:

  ```
  mame = 4:3
  rom:mygame = custom:0.125,0,0.75,1
  ```

- Live: `dbar4gun area 4:3`, or the *Area profile* screen of the calibrator.
- **Useful zone** (`--useful-zone 0.85`): the part of the screen height with
  targets (the bottom is usually HUD). The calibration and the reach test use it.
