# Tested games

English | [Español](games.es.md)

| game                     | ROM / disc                     | emulator (RetroPie)  | resolution | smoothing level | note                       |
|--------------------------|--------------------------------|----------------------|------------|-----------------|----------------------------|
| Operation Wolf           | `opwolf`                       | lr-mame              | 320x240    |  0              |                            |
| Point Blank              | `ptblank`                      | lr-mame              | 288x224    |  0              |                            |
| Point Blank 2            | `ptblank2`                     | lr-mame              | 320x240    |  0              |                            |
| Point Blank 3            | `ptblank3`                     | lr-mame              | 320x240    |  0              |                            |
| Ghoul Panic              | `ghlpanic`                     | lr-mame              | 512x480    |  0              |                            |
| Time Crisis              | `timecris`                     | lr-mame              | 640x480    |  0              |                            |
| Golly! Ghost!            | `gollygho`                     | lr-mame              | 288x224    |  0              |                            |
| VS. Hogan's Alley        | `hogalley`                     | lr-mame              | 256x240    |  0              | low precision in the bonus |
| Lucky & Wild             | `luckywld`                     | lr-mame2015          | 288x224    |  0              |                            |
| Area 51                  | `area51`                       | lr-mame2003-plus     | 320x240    |  0              |                            |
| CarnEvil                 | `carnevil`                     | lr-mame2003-plus     | 512x400    |  0              | runs at its original 54 fps |
| House of the Dead 2      | `House of the Dead 2, The (USA).gdi` | flycast (standalone) | 640x480    |  0              |                            |
| Virtua Cop 2             | `Virtua Cop 2 (Japan).gdi`     | lr-flycast           | 640x480    |  0              |                            |

How they were tested: RetroPie on a Raspberry Pi 5 (Debian 12), RetroArch 1.19.1,
dbar4gun with `--smoothing-level 0`, each game with the emulator above.
Gun options of the cores: `mame_current_xy_type = "lightgun"` (lr-mame),
`mame2003-plus_xy_device = "lightgun"`, `mame2015_mouse_mode = "lightgun"`.

## Change the emulator of a game with the Wiimote (RetroPie)

1. Start the game from EmulationStation.
2. While "Launching..." is on screen, press **home** (`key enter`): the runcommand menu opens.
3. Move with the **d-pad**, choose **Select emulator for ROM** and then the emulator, confirming with **home**.
4. Choose **Launch**. From then on, that game always starts with that emulator.

To leave the game: **b + minus** (`key esc`).

## Raspberry Pi 5: Point Blank 3 and the lr-mame version

Emulation speed of Point Blank 3 (`ptblank3`) on a Raspberry Pi 5 with lr-mame,
measured without video or sound output. The game needs 60 fps.

| lr-mame core                                                   | measures (fps)                          | average | always above 60 |
|----------------------------------------------------------------|-----------------------------------------|---------|-----------------|
| 0.289, full (arcade, as RetroPie installs it)                  | 56.0, 57.3, 57.7                        | 57.0    | no              |
| 0.289, 54 light gun drivers                                    | 56.8, 57.0, 57.0                        | 56.9    | no              |
| 0.289, only Namco System 10/12                                 | 60.6, 61.6, 60.5, 60.1, 57.2            | 60.0    | no              |
| 0.278, only Namco System 10/12                                 | 61.8, 58.5, 64.8, 58.9                  | 61.0    | no              |
| 0.276, the 8 drivers of the lr-mame games in this list         | 62.0, 58.9, 61.5                        | 60.8    | no              |
| 0.276, only Namco System 10/12                                 | 62.3, 62.5, 67.2, 61.3, 61.6, 62.0      | 62.8    | yes             |
| 0.276, only Namco System 10/12, built for the Pi 5             | 66.4, 63.5, 67.5                        | 65.8    | yes             |

Conclusion:

- The full lr-mame core (0.289) never reaches full speed with Point Blank 3 on a Pi 5.
- A core built only with the drivers the game needs is faster. With many
  drivers (54) that advantage is lost.
- Since lr-mame 0.278 the game is slower and less steady.
- The best one is lr-mame 0.276 built only with Namco System 10/12 and for the
  Pi 5 CPU (`OPTIMIZE=3 ARCHOPTS=-mcpu=cortex-a76`): always above 60 fps, with
  margin, and played in the game it runs at full speed. How to build it: [docs/lr-mame-pi5.md](lr-mame-pi5.md).

Point Blank 2, Ghoul Panic and Golgo 13 run on Namco System 12, so the same core
covers them.

Test setup: Raspberry Pi 5 (4 GB) with RetroPie and RetroArch 1.19.1, overclocked
in `/boot/firmware/config.txt`:

```
arm_freq=2600
over_voltage_delta=50000
```
