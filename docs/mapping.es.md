# Mapa de botones

[English](mapping.md) | Español

Qué envía cada botón del Wiimote con dbar4gun, y qué hace en MAME y en RetroArch con
su configuración por defecto (MAME 0.276 / lr-mame, RetroArch 1.19.1 tal como lo
configura RetroPie).

## Cómo funciona

- **Auto key**: cada gun envía las **teclas por defecto de MAME de su jugador** (gun 1 =
  jugador 1, gun 2 = jugador 2...). Los juegos se juegan de manera cómoda sin necesidad
  de mapear los botones; las excepciones se encuentran en [retroarch](../retroarch/README.es.md).
- **Botones y combos compartidos**: la misma tecla en todos los guns (menús, salir...).
- El número de gun es el orden de la VirtualGun en RetroArch (`mouse index`); lo
  muestran los LEDs del Wiimote.

## Botones iguales en todos los guns

| botón        | dbar4gun envía | MAME                         | RetroArch                          |
|--------------|----------------|------------------------------|------------------------------------|
| ir           | cursor del ratón | apuntar                    | apuntar                            |
| b            | botón izquierdo  | gatillo (botón 1)          | gatillo                            |
| 1            | botón central    |                            |                                    |
| 2            | botón derecho    |                            | recargar                           |
| home         | `enter`        | aceptar (en los menús)       | start del jugador 1 (ver choques)  |

## Auto key

| botón            | gun 1        | gun 2 | gun 3         | gun 4                     | MAME (jugador del gun) |
|------------------|--------------|-------|---------------|---------------------------|------------------------|
| cruceta izquierda | `left`      | `d`   | `j`           | `4` del teclado numérico  | izquierda              |
| cruceta derecha  | `right`      | `g`   | `l`           | `6` del teclado numérico  | derecha                |
| cruceta abajo    | `down`       | `f`   | `k`           | `2` del teclado numérico  | abajo                  |
| cruceta arriba   | `up`         | `r`   | `i`           | `8` del teclado numérico  | arriba                 |
| más              | `1`          | `2`   | `3`           | `4`                       | start                  |
| menos            | `5`          | `6`   | `7`           | `8`                       | moneda                 |
| a                | `alt izq.`   | `s`   | `shift der.`  | `.` del teclado numérico  | botón 2 (granada, pedal...) |
| z del nunchuk    | `b` (1)      | `q`   | `enter`       | `enter` del teclado numérico | botón 3             |
| c del nunchuk    | `shift izq.` | `w`   | `1` del teclado numérico | `5` del teclado numérico | botón 4 (guns 3 y 4: ninguno) |
| stick del nunchuk | como la cruceta |    |               |                           | dirección              |

(1) MAME usa `espacio` para el botón 3 del jugador 1, pero `espacio` es el avance
rápido en RetroArch, así que el gun 1 envía la tecla libre `b`. MAME no la usa por
defecto: para usar la Z del Nunchuk como botón 2 mira [retroarch/mame](../retroarch/mame/README.es.md).

## Combos (todos los guns)

| combo      | dbar4gun envía | MAME                         | RetroArch                 | dbar4gun                    |
|------------|----------------|------------------------------|---------------------------|-----------------------------|
| b + home   | `tab`          | menú                         |                           |                             |
| b + menos  | `esc`          | cancelar (en los menús)      | salir del juego           |                             |
| b + 1      | `espacio`      | también botón 3 del jugador 1 | avance rápido sí / no    |                             |
| b + 2      | `2`            | start del jugador 2          |                           |                             |
| a + home   | `f1`           |                              | menú                      |                             |
| b + más    |                |                              |                           | apagar / encender la cámara IR |
| a + más    |                |                              |                           | calibración                 |
| a + menos  |                |                              |                           | reiniciar la calibración    |

## Choques con RetroArch

El auto key sigue a MAME. Estas teclas de MAME son también atajos por defecto de
RetroArch, y RetroArch los ejecuta durante el juego:

| tecla   | botón              | en RetroArch                         | qué pasa                              |
|---------|--------------------|--------------------------------------|---------------------------------------|
| `f`     | abajo del gun 2    | pantalla completa / ventana          | cambia el modo de ventana             |
| `l`     | derecha del gun 3  | avance rápido mientras se mantiene   | el juego se acelera                   |
| `k`     | abajo del gun 3    | avanzar un fotograma                 | solo con el juego en pausa            |
| `i`     | arriba del gun 3   | netplay: ver la partida              | solo en netplay                       |
| `enter` | z del gun 3, home  | start del jugador 1 (teclado)        | start del jugador 1 en el juego       |
| `q`     | z del gun 2        | L del jugador 1 (teclado)            | botón 5 del jugador 1 (los juegos de pistola no lo usan) |

Los cuatro primeros son atajos de RetroArch. Para desactivarlos **solo en los juegos
de pistola**, añade a la configuración de RetroArch de ese sistema
(`/opt/retropie/configs/lightgun/retroarch.cfg` en RetroPie), encima de la línea
`#include`:

```
input_toggle_fullscreen = "nul"
input_hold_fast_forward = "nul"
input_frame_advance = "nul"
input_netplay_game_watch = "nul"
```

En esos juegos, esas funciones dejan de estar en el teclado; el resto de sistemas
las conserva. El avance rápido sigue en `espacio` (b + 1).

Si los emuladores de pistola cargan otro archivo (`--config ...` en
`/opt/retropie/configs/lightgun/emulators.cfg`), las líneas van en ese archivo.

`enter` y `q` son las teclas del jugador 1 cuando se juega RetroArch con teclado: se
dejan como están.
