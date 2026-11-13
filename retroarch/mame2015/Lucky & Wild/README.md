## Lucky & Wild

English | [Español](README.es.md)

Copy `luckywld.cfg` to the `cfg` folder of the core, which is inside the RetroArch save directory.
In RetroPie the saves are next to the ROMs by default:

```
~/RetroPie/roms/<system>/mame2015/cfg/luckywld.cfg
```

For example, with the games in the `lightgun` system: `~/RetroPie/roms/lightgun/mame2015/cfg/luckywld.cfg`.
If you changed the save directory (`savefile_directory` in `retroarch.cfg`), use
`<that folder>/mame2015/cfg/luckywld.cfg` instead.

If `luckywld.cfg` already exists there, copying replaces it.

| device   | button     | action            |
|----------|------------|-------------------|
| wiimote  | ir         | cursor            |
| wiimote  | b          | trigger           |
| wiimote  | plus       | start             |
| wiimote  | minus      | coin              |
| wiimote  | (P1) left  | drive left        |
| wiimote  | (P1) right | drive right       |
| wiimote  | (P1) up    | accelerate        |
| wiimote  | (P1) down  | brake             |
| nunchuck | (P1) stick | d-pad             |
| nunchuck | (P1) c     | brake             |
| combo    | b + home   | mame menu         |
| combo    | b + minus  | key esc           |
| wiimote  | home       | key enter         |
| combo    | a + plus   | start calibration |
| combo    | a + minus  | reset calibration |
