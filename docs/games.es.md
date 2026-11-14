# Juegos probados

[English](games.md) | Español

| juego                    | ROM / disco                    | emulador (RetroPie)  | resolución | smoothing level | nota                       |
|--------------------------|--------------------------------|----------------------|------------|-----------------|----------------------------|
| Operation Wolf           | `opwolf`                       | lr-mame              | 320x240    |  0              |                            |
| Point Blank              | `ptblank`                      | lr-mame              | 288x224    |  0              |                            |
| Point Blank 2            | `ptblank2`                     | lr-mame              | 320x240    |  0              |                            |
| Point Blank 3            | `ptblank3`                     | lr-mame              | 320x240    |  0              |                            |
| Ghoul Panic              | `ghlpanic`                     | lr-mame              | 512x480    |  0              |                            |
| Time Crisis              | `timecris`                     | lr-mame              | 640x480    |  0              |                            |
| Golly! Ghost!            | `gollygho`                     | lr-mame              | 288x224    |  0              |                            |
| VS. Hogan's Alley        | `hogalley`                     | lr-mame              | 256x240    |  0              | poca precisión en el bonus |
| Lucky & Wild             | `luckywld`                     | lr-mame2015          | 288x224    |  0              |                            |
| Area 51                  | `area51`                       | lr-mame2003-plus     | 320x240    |  0              |                            |
| CarnEvil                 | `carnevil`                     | lr-mame2003-plus     | 512x400    |  0              | va a sus 54 fps originales |
| House of the Dead 2      | `House of the Dead 2, The (USA).gdi` | flycast (standalone) | 640x480    |  0              |                            |
| Virtua Cop 2             | `Virtua Cop 2 (Japan).gdi`     | lr-flycast           | 640x480    |  0              |                            |

Cómo se probaron: RetroPie en una Raspberry Pi 5 (Debian 12), RetroArch 1.19.1,
dbar4gun con `--smoothing-level 0`, cada juego con el emulador de la
tabla. Opciones de pistola de los cores: `mame_current_xy_type = "lightgun"` (lr-mame),
`mame2003-plus_xy_device = "lightgun"`, `mame2015_mouse_mode = "lightgun"`.

## Cambiar el emulador de un juego con el Wiimote (RetroPie)

1. Abre el juego desde EmulationStation.
2. Mientras sale "Launching..." en pantalla, pulsa **home** (`key enter`): se abre el menú de runcommand.
3. Muévete con la **cruceta**, elige **Select emulator for ROM** y después el emulador, confirmando con **home**.
4. Elige **Launch**. A partir de ahí, ese juego arranca siempre con ese emulador.

Para salir del juego: **b + minus** (`key esc`).

## Raspberry Pi 5: Point Blank 3 y la versión de lr-mame

Velocidad de emulación de Point Blank 3 (`ptblank3`) en una Raspberry Pi 5 con
lr-mame, medida sin salida de vídeo ni de sonido. El juego necesita 60 fps.

| core de lr-mame                                                | medidas (fps)                           | media | siempre por encima de 60 |
|----------------------------------------------------------------|-----------------------------------------|-------|--------------------------|
| 0.289, completo (arcade, como lo instala RetroPie)             | 56.0, 57.3, 57.7                        | 57.0  | no                       |
| 0.289, 54 drivers de pistola                                   | 56.8, 57.0, 57.0                        | 56.9  | no                       |
| 0.289, solo Namco System 10/12                                 | 60.6, 61.6, 60.5, 60.1, 57.2            | 60.0  | no                       |
| 0.278, solo Namco System 10/12                                 | 61.8, 58.5, 64.8, 58.9                  | 61.0  | no                       |
| 0.276, los 8 drivers de los juegos de lr-mame de esta lista    | 62.0, 58.9, 61.5                        | 60.8  | no                       |
| 0.276, solo Namco System 10/12                                 | 62.3, 62.5, 67.2, 61.3, 61.6, 62.0      | 62.8  | sí                       |
| 0.276, solo Namco System 10/12, compilado para la Pi 5         | 66.4, 63.5, 67.5                        | 65.8  | sí                       |

Conclusión:

- El core completo de lr-mame (0.289) nunca llega a la velocidad completa con
  Point Blank 3 en una Pi 5.
- Un core compilado solo con los drivers que necesita el juego va más rápido.
  Con muchos drivers (54) esa ventaja se pierde.
- Desde lr-mame 0.278 el juego va más lento y menos estable.
- El mejor es lr-mame 0.276 compilado solo con Namco System 10/12 y para la CPU
  de la Pi 5 (`OPTIMIZE=3 ARCHOPTS=-mcpu=cortex-a76`): siempre por encima de
  60 fps, con margen, y jugando va a velocidad completa. Cómo compilarlo: [docs/lr-mame-pi5.es.md](lr-mame-pi5.es.md).

Point Blank 2, Ghoul Panic y Golgo 13 usan Namco System 12, así que el mismo
core sirve para ellos.

Equipo de prueba: Raspberry Pi 5 (4 GB) con RetroPie y RetroArch 1.19.1, con
overclock en `/boot/firmware/config.txt`:

```
arm_freq=2600
over_voltage_delta=50000
```
