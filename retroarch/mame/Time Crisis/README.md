## Time Crisis

English | [Español](README.es.md)

Copy `timecris.cfg` to the `cfg` folder of the core, which is inside the RetroArch save directory.
In RetroPie the saves are next to the ROMs by default:

```
~/RetroPie/roms/<system>/mame/cfg/timecris.cfg
```

For example, with the games in the `lightgun` system: `~/RetroPie/roms/lightgun/mame/cfg/timecris.cfg`.
If you changed the save directory (`savefile_directory` in `retroarch.cfg`), use
`<that folder>/mame/cfg/timecris.cfg` instead.

If `timecris.cfg` already exists there, copying replaces it.

| device   | button    | action            |
|----------|-----------|-------------------|
| wiimote  | ir        | cursor            |
| wiimote  | b         | trigger           |
| wiimote  | a         | pedal (cover)     |
| nunchuck | z         | pedal (cover)     |
| wiimote  | plus      | start             |
| wiimote  | minus     | coin              |
| combo    | b + home  | mame menu         |
| combo    | b + minus | key esc           |
| wiimote  | home      | key enter         |
| combo    | a + plus  | start calibration |
| combo    | a + minus | reset calibration |

