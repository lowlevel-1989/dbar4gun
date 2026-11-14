# Area profiles

[English](area-profiles.md) | Español

Un area profile le dice a dbar4gun qué parte de la pantalla cubre la pistola.

**La mayoría de montajes no lo necesitan: deja `full` (el de por defecto).** Los
emuladores que llevan ellos mismos la posición de la pistola a la imagen del juego
ya resuelven un juego 4:3 en una TV 16:9, y apuntar fuera de la imagen es
"offscreen", para recargar:

- RetroArch: todos los cores `lr-*` (lr-mame, lr-mame2003-plus, lr-mame2016, lr-flycast...).
- flycast standalone.

Con ellos, un perfil `4:3` corregiría la imagen dos veces y la mira se desviaría
hacia los lados.

**Cuándo hace falta:** con un emulador que estira todo el rango de la pistola sobre
la imagen del juego. Con `full`, un juego 4:3 en una TV 16:9 llega a su borde
cuando apuntas al borde de la TV, y cuanto más lejos del centro, más error.
Casos reales:

| Caso | Perfil |
|------|--------|
| MAME standalone (el programa `mame`, sin RetroArch): el MAME por defecto de Batocera y Recalbox, y en un PC de escritorio | `4:3` |
| AdvanceMAME | `4:3` |
| Un juego en una ventana del escritorio, o una imagen que no ocupa toda la TV (marco o decorado fijo) | `custom:x0,y0,w,h` |
| Mezclar emuladores: MAME standalone para un juego y RetroArch para el resto | por juego en `profiles.cfg` |

`custom:x0,y0,w,h` es el rectángulo del juego como fracción de la TV: borde
izquierdo, borde superior, ancho y alto (`0.125,0,0.75,1` es una imagen 4:3
centrada en una TV 16:9).

Cómo ponerlo:

- Perfil por defecto: `--area full|4:3|custom:x0,y0,w,h` (RetroPie-Setup →
  dbar4gun → *default area profile*).
- Por juego: `profiles.cfg` en el directorio de configuración
  (`/opt/retropie/configs/all/dbar4gun/` en RetroPie). Prioridad: `rom:<nombre>`
  > `system/emulator` > `emulator` > `system` > `default`. Los hooks de
  runcommand de RetroPie lo aplican al empezar un juego y vuelven al de por
  defecto al terminar. Por ejemplo:

  ```
  mame = 4:3
  rom:mygame = custom:0.125,0,0.75,1
  ```

- En vivo: `dbar4gun area 4:3`, o la pantalla *Area profile* del calibrator.
- **Useful zone** (`--useful-zone 0.85`): la parte de la altura de la pantalla
  con targets (la parte de abajo suele ser el HUD). La usan la calibración y el
  reach test.
