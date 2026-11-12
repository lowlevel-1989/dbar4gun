# Protocolos de dbar4gun

## UDP v2 (driver → calibrator)

El driver envía un paquete por cada report 0x37 de cada Wiimote a
`127.0.0.1:<--port>` (35460 por defecto). Struct fija en orden de red
(`dbar4gun/protocol.py`, `FORMAT`), **125 bytes**. Un paquete con otro tamaño o
con el primer byte distinto de 2 se descarta.

| # | Tipo | Campo | Notas |
|---|------|-------|-------|
| 1 | `B` | version | siempre 2 |
| 2 | `B` | index | índice de ratón que devolvió la VirtualGun (incluye ratones reales) |
| 3 | `B` | virtualgun | número de VirtualGun (puerto + 1) |
| 4 | `H` | buttons | botones del Wiimote tal cual, sin la máscara de calibración |
| 5 | `B` | flags | ver tabla de flags |
| 6 | 4 × `HHB` | raw dots | `raw_x` (0..1023), `raw_y` (0..767), tamaño (0xFF = desconocido). Dot ausente: `raw_y = 0x3FF` |
| 7 | 2 × `ffB` | TL, TR | posición del tracker normalizada (`x = 1 - raw_x/1023`, `y = raw_y/767`) y flags del dot |
| 8 | `ff` | camera point | tras tilt correction y distance compensation |
| 9 | `ff` | cursor | salida del gun (área aplicada, 0..1) |
| 10 | `ff` | screen | cursor en la TV completa, sin área ni clamp |
| 11 | `b` | step | paso de calibración, −1 si no se está calibrando |
| 12 | `B` | captured | disparos válidos de la calibración (todas las vueltas) |
| 13 | `B` | total | pasos de la calibración en curso |
| 14 | `ff` | target | target actual (TV completa) |
| 15 | `f` | spread | dispersión de las últimas muestras en separaciones de barra, −1 = n/d |
| 16 | `B` | error | último error de captura: 0 ninguno, 1 `no_ir`, 2 `unstable`, 3 `bad_geometry`, 4 `inconsistent` (un disparo lejos del otro al mismo target) |
| 17 | `f` | roll | roll del acelerómetro en grados (NaN = n/d) |
| 18 | `f` | angle | ángulo de TL→TR en grados |
| 19 | `f` | separation | separación angular de los dots (rad) |
| 20 | `f` | sep_ref | separación de referencia de la calibración (rad) |
| 21 | `B` | battery | % de batería, 0xFF = n/d |
| 22 | `f` | hz | reports por segundo |
| 23 | `ffff` | area | `x0, y0, w, h` del area profile |
| 24 | `f` | useful_zone | useful zone |

Flags generales (`flags`):

| Bit | Nombre |
|-----|--------|
| 0x01 | calibrado (hay calibración guardada o hecha en esta sesión) |
| 0x02 | distance compensation activa |
| 0x04 | barra arriba |
| 0x08 | fake cursor (B+plus) |
| 0x10 | sin dots (`lost`) |
| 0x20 | camera point válido |
| 0x40 | calibrando |

Flags de TL/TR: 0x01 válido, 0x02 reconstruido.

La distancia aproximada a la barra es `0.20 / (2 * tan(separation / 2))` m.

## Socket de control

`/run/dbar4gun.sock` (`--socket`), Unix stream, permisos 0666. El cliente envía
una línea y recibe una línea JSON con al menos `ok`.

| Comando | Respuesta |
|---------|-----------|
| `status` | `version`, `area`, `useful_zone`, `hardware`, `profiles` (ruta del `profiles.cfg` del daemon, la usa `dbar4gun profile`) y `wiimotes`: lista con `virtualgun`, `player`, `key`, `hidraw`, `paired` (false en un slot vacío de la DolphinBar), `ir_sensitivity`, `report_age` (s desde el último report distinto), `nunchuck`, `hardware`, `battery`, `hz`, `calibrated`, `calibrating`, `calibration_step`, `calibration_mode`, `mode_option`, `affine` (6 valores o 9 si es homografía), `bar_position`, `scale_ratio`, `screen_aspect`, `filter`, `sep_ref`, `distance_m`, `distance_ref_m`, `roll_deg`, `dots`, `last_calibration_error`... |
| `area <perfil>` | `default` (el del servicio o `profiles.cfg`), `full`, `4:3` (cualquier `a:b`) o `custom:x0,y0,w,h` |
| `usefulzone <0.3..1.0>` | useful zone de todos los Wiimotes |
| `save` | escribe el área y la useful zone actuales en `profiles.cfg` (`default`, `useful_zone`) |
| `calibrate [vg] [full\|quick] [targets=x1,y1,...]` | `started`: VirtualGuns que empezaron. `targets` en coordenadas de la TV completa (2, 3 o 4 según el modo) |
| `cancel` | cancela las calibraciones en curso |
| `reload` | relee las calibraciones guardadas; `loaded`: VirtualGuns actualizadas |
| `filter <vg> <fc_min> <beta> [d_cutoff]` | parámetros del One Euro de ese Wiimote (se guardan con la calibración) |
| `history <vg>` | history de calibraciones: `index`, `timestamp`, `accuracy`, `mode`, `sep_ref` |
| `restore <vg> <index>` | vuelve a una calibración del history |
| `accuracy <vg> <mean_tv> <max_tv> [mean_game max_game]` | anota la precisión medida en la última calibración |
| `irmode basic\|extended` | modo IR extendido (tamaño de los dots); solo con `--experimental-ir-extended` |
| `hw` | valores de hardware vigentes (`hardware`) y ruta de `hardware.json` |
| `hw <clave> <valor> [...]` | `fov` (20..60 grados), `acc_x_sign` (1 o −1), `bar_width` (0.05..0.6 m), `ir_sensitivity` (`1`..`5`, `marcan`, `cliff` o `default`): se validan, se guardan en `hardware.json` y se aplican a todos los Wiimotes (la IR sensitivity reconfigura la cámara, ~0.8 s) |
| `hwreport <json>` | guarda el informe de la hardware check en `hardware_report.json` (el resto de la línea es un objeto JSON); `path` |

Desde la línea de comandos: `dbar4gun status`, `dbar4gun area 4:3`,
`dbar4gun calibrate [vg] [--quick]`, `dbar4gun cancel`, `dbar4gun reload`,
`dbar4gun hw [clave valor ...]`.

## hardware.json

En el directorio de configuración, común a todos los Wiimotes:

```json
{"acc_x_sign": 1.0, "bar_width_m": 0.2, "fov_h_deg": 33.0, "ir_sensitivity": null}
```

- `fov_h_deg` y `bar_width_m` solo cambian las distancias (`distance_m`,
  reach test, distancia recomendada). El pipeline usa siempre la focal
  nominal (33°), así que medir el FOV no invalida las calibraciones guardadas
  (en el simulador, un FOV real de 38–42° da la misma precisión).
- `acc_x_sign` es el signo del eje X del acelerómetro frente al roll (`1`: el
  eje X del Wiimote es positivo hacia la izquierda, medido con hardware real);
  ordena TL/TR cuando no hay un par reciente (más allá de ±90°).
- `ir_sensitivity`: `null` usa la `--ir-sensitivity` del servicio; si tiene un
  nivel, manda sobre la opción del servicio. Orden de más a menos sensible
  usado por el hardware check: `5`, `4`, `marcan`, `2`, `1`.
