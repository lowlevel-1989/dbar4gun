## lr-mame: Nunchuk Z as button 2 (optional)

English | [Español](README.es.md)

The Nunchuk Z of gun 1 sends `key b`, which MAME does not use by default.
To use it like the Wiimote A in every game, choose one:

- **MAME menu** (b + home): Input Settings → Input Assignments (general) → Player 1
  Controls → **P1 Button 2**. Press **d-pad right** until it says "Press Enter to
  append", then **home** (`key enter`) and the **Nunchuk Z**.
- **Copy [default.cfg](default.cfg)**: it only adds `key b` to P1 Button 2; MAME saves
  only what differs from its defaults, so everything else keeps the default keys.

Copy `default.cfg` to the `cfg` folder of the core, which is inside the RetroArch save directory.
In RetroPie the saves are next to the ROMs by default:

```
~/RetroPie/roms/<system>/mame/cfg/default.cfg
```

For example, with the games in the `lightgun` system: `~/RetroPie/roms/lightgun/mame/cfg/default.cfg`.
If you changed the save directory (`savefile_directory` in `retroarch.cfg`), use
`<that folder>/mame/cfg/default.cfg` instead.

If `default.cfg` already exists there, copying replaces it and the general changes you made in MAME are lost: use the MAME menu instead.
