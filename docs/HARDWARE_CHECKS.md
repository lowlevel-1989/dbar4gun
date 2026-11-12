# Comprobaciones con hardware

Lo que no se puede verificar sin un Wiimote real. Cada entrada indica la tarea
del plan, qué comprobar y cómo.

## Medido con hardware (2026-11-12, DolphinBar en modo 4 + Wiimote MotionPlus Inside, PC)

- **4 slots siempre presentes:** `hidraw` con `HID_ID=0003:0000057E:00000306`,
  `HID_NAME=HJZ Mayflash Wiimote PC Adapter`, `HID_PHYS=usb-<bus>-<puerto>/input0..3`
  y `HID_UNIQ` vacío. Las claves `usb:<HID_PHYS>` son distintas por slot (C11).
  Con el usuario en sesión (ACL uaccess) se pueden leer sin root.
- **Slot sin Wiimote:** toda escritura falla con `EPIPE` (la barra rechaza el
  SET_REPORT). El slot 1 envía `30 00 00` a ~4 Hz; los slots 2–4 no envían nada.
  El driver no crea la VirtualGun hasta que el Wiimote responde (reintenta cada
  0.2 s, cada intento falla al instante).
- **Con Wiimote:** la secuencia de `enable_ir` funciona tal cual; reports 0x37 de
  22 bytes a **~175 Hz** (no 100): ~1/3 son copia del anterior y hay huecos de
  ~29 ms. El status (0x15 → 0x20) funciona; batería `0x4e` = 39 %.
- **E6 con el Wiimote quieto en la mesa:** los reports nunca se repiten
  idénticos más de 0.17 s (los bits bajos del acelerómetro, en los bytes de
  botones, cambian), así que el detector de 10 s no da falsas desconexiones.
- **Acelerómetro en plano, botones arriba:** `84 83 99` → Z = +1 g (0x99 − 0x80 =
  25 ≈ 0x1A), como supone el simulador. Falta el signo de X (C17).
- Pendiente con este equipo: apagar/encender el Wiimote (E6), dots reales
  (FOV, jitter, tamaño en IR extendido) y el signo de X.
- **Daemon real sin uinput contra la barra** (VirtualGun sin salida, para no
  mover el cursor del PC): se crean 4 workers (VirtualGun 01–04, uno por slot);
  el del slot 1 empareja (batería 37 %, ~180 Hz) y los vacíos responden a
  `status` con `paired: false` en 5 ms (antes no respondían y `status` esperaba
  0.5 s). El calibrator (offscreen) muestra el paso de conexión con estos datos
  y guarda el informe.

### RetroArch: area profile y recarga fuera de pantalla (2026-11-12, código)

- RetroArch (1.19.1 en la Pi y `master`, `input/drivers/udev_input.c`) toma la
  posición absoluta del gun respecto a la pantalla completa y la pasa a la
  imagen del juego (viewport); fuera de ella, o a menos de ~0.1 % del borde, es
  `IS_OFFSCREEN` (recargar). Con los cores `lr-*` el area profile es `full`.
- Pendiente con hardware: en un juego 4:3 (Point Blank, lr-mame), apuntar a las
  bandas negras y disparar debe recargar; la mira debe coincidir con el Wiimote
  en los bordes de la imagen con el perfil `full`.
- Pendiente: House of the Dead 2 va con flycast standalone (no RetroArch):
  comprobar qué area profile necesita.
- Pendiente: `/opt/retropie/configs/all/retroarch.cfg` tiene
  `input_driver = "x"`; sin X, RetroArch debería usar otro driver. Mirar en el
  log de una partida (`--verbose`) qué driver de entrada usa: el mouse index
  de las pistolas depende de que sea `udev`.

### Mouse index (2026-11-12, PC con raton Bluetooth y touchpad)

- RetroArch (`input/drivers/udev_input.c`) numera los punteros con libudev:
  primero `ID_INPUT_MOUSE=1`, luego `ID_INPUT_TOUCHPAD`, solo nodos `eventN`.
  Medido en el PC con 2 VirtualGun reales (uinput): orden VirtualGun 01,
  VirtualGun 05, ratón Bluetooth (`virtual/misc/uhid` va después de
  `virtual/input`), touchpad. El driver ahora da mouse index 1 y 2 (LED 4 y 3,
  teclas de los jugadores 1 y 2); antes daba 3 y 7, con las teclas del jugador
  1 en las dos.
- Pendiente: con 2 Wiimotes (barra + Bluetooth) en la Pi con RetroArch,
  comprobar que cada pistola mueve la mira de su jugador sin configurar nada;
  y desconectar/reconectar el de Bluetooth (debe conservar LED y jugador; en
  el log, `DETACHED` y `REATTACHED`).

### DolphinBar bajo carga (2026-11-12, 1 Wiimote en el slot 1)

Pregunta: ¿se cuelga la barra con muchas escrituras juntas? (a veces había que
desenchufar el USB). No se ha reproducido:
- Escrituras al slot activo (LEDs, status, DRM, registros), subiendo el ritmo:
  sin errores hasta ~217/s (escritura ~1 ms, máx. 26 ms). Sin pausa (~237/s)
  la barra rechaza alguna con `EPIPE` y se recupera sola al momento.
- Escrituras simultáneas en los 4 slots (un hilo por slot, como los workers),
  hasta 200/s en el activo y miles de intentos rechazados en los vacíos: los
  reports siguen a ~178/s; con tanta concurrencia una escritura del slot activo
  llega a tardar ~150 ms (los 4 slots comparten el canal de control USB). Un
  intento en un slot vacío tarda hasta ~100 ms en ser rechazado.
- 10 arranques/paradas seguidos del daemon real (sin uinput): empareja en ~3.2 s
  cada vez y la barra sigue bien.
- 15 minutos con el Wiimote quieto (daemon real): 0 reconfiguraciones, ~10500
  reports/min estables; solo las escrituras de LEDs cada 3 s (como la v0.18.2).
  La v0.18.2 reconfiguraba el Wiimote cada 10 s si la parte alta del
  acelerómetro no cambiaba (Wiimote quieto): causa probable de los cuelgues tras
  días encendido.
- El driver escribe muy por debajo de eso (< 10 escrituras/s por Wiimote: DRM
  como mucho cada 0.5 s, status cada 5 s, LEDs/rumble al calibrar).
- Si vuelve a colgarse: anotar cuántos Wiimotes había, qué se estaba haciendo y
  la versión; guardar `journalctl -k` y el log del servicio con
  `--log-level debug` antes de desenchufar.

### Bluetooth (2026-11-12, mismo Wiimote, Fedora, BlueZ con `hid-wiimote`)

- Emparejado con `bluetoothctl scan on` + `bluez/simple-agent` tras pulsar SYNC
  (sin `hcitool`, que Fedora ya no trae). `simple-agent` tiene que correr en una
  terminal: pide el PIN por teclado y en segundo plano no puede contestar.
  Antes de emparejar, BlueZ tiene que haber visto el Wiimote en un scan (si no,
  "Bluetooth device not found"). Ahora lo hace `bluez/pair-wiimote.sh`
  (pendiente de probar el script en sí).
- `hidraw2`: `HID_ID=0005:0000057E:00000330` (modelo TR), `HID_UNIQ` = MAC.
  `is_wiimote` lo detecta y la clave es `bt:b8:ae:6e:50:14:26` (C11 verificado).
- `hid-wiimote` se engancha (crea Wii Remote, Accelerometer, IR y Motion Plus en
  evdev). El `hidraw` es solo de root (el daemon corre como root).
- Driver por Bluetooth: 0x37 a ~80–88 Hz, status y batería bien, sin reports
  idénticos más de 0.22 s. `hid-wiimote` mete algún report 0x30/0x31/0x36
  cuando alguien abre sus evdev: el driver reenvía el DRM (E6) y el IR sigue.
- **Bug encontrado y arreglado:** cuando un programa abre y cierra los evdev de
  `hid-wiimote` (un emulador, el escritorio, `evtest`, o `pygame.init()` del
  calibrator, que abría los joysticks), el kernel **apaga la cámara IR** (status
  LF 0x88 → 0x80) y los 0x37 siguen llegando sin dots. Ahora el driver pide el
  status cada 5 s y, si la cámara está apagada, reconfigura el IR (medido: vuelve
  en ~3.5 s). El calibrator ya no abre joysticks (solo display y font).
  Pendiente en RetroPie: entrar y salir de un juego de RetroArch con el Wiimote
  por Bluetooth y comprobar que el IR vuelve solo (log: "IR camera turned off by
  another driver").

### Raspberry Pi 5 (2026-11-12, Debian 12, Python 3.11, RetroPie)

- Copia del repo en `~/dbar4gun-test` con un venv como el del scriptmodule
  (`--system-site-packages`): usa el `python3-pygame` 2.1.2 de apt (SDL 2.32,
  con backend KMS/DRM) y pip no instala otro. Los 311 tests pasan (13.9 s),
  GUI incluida en headless.
- Coste del pipeline por report: ~20 µs (0.35 % del tiempo entre reports a 175 Hz).
- Pendiente: instalar con el scriptmodule (necesita `sudo`) y abrir el
  calibrator desde EmulationStation en la TV.

## E1: LEDs por jugador

- Conectar 4 o más Wiimotes (o 1 Wiimote con ratones USB conectados, que suben el index).
- Esperado: el jugador 4 enciende el LED 4 y queda emparejado (antes se quedaba
  reintentando `enable_ir` en cada lectura); el 5.º vuelve al LED 1.
- `check_is_alive` (cada 3 s) no debe cambiar los LEDs.

## E2: eventos udev

- Con el daemon corriendo, conectar y desconectar un Wiimote varias veces
  (Bluetooth y DolphinBar). En el log debe aparecer un único `CREATED` por conexión
  y un `DELETED` por desconexión, sin VirtualGun duplicadas (`ls /dev/input/by-id`,
  `evtest`).
- Arrancar el daemon con un Wiimote ya conectado: una sola VirtualGun.

## E5: pid file

- `sudo dbar4gun start`, matar con `kill -9`, escribir en `/var/run/dbar4gun.pid`
  el pid de otro proceso (p. ej. `sleep 300 &`) y lanzar `sudo dbar4gun stop`:
  el `sleep` debe seguir vivo y el pid file desaparecer.

## E11: Python 3.7

- En RetroPie sobre Buster (python 3.7), con la versión 0.18.2:
  `python3 -c "import dbar4gun.wiimote"` debe fallar
  (`AttributeError: module 'typing' has no attribute 'Protocol'`).
- Con la versión nueva: el mismo import funciona y `sudo dbar4gun start` arranca y
  crea la VirtualGun al conectar un Wiimote.

## R3: supuestos del simulador (`tests/sim/`)

Se miden con el calibrator: *Hardware check* (ver abajo).

- **FOV de la cámara:** el simulador usa 33° en horizontal (f = 1728.5 px). Para
  medirlo, poner el Wiimote a una distancia D conocida y perpendicular a la barra,
  y anotar la separación en px entre los 2 dots (`dbar4gun gui`, datos raw):
  f = sep_px * D / 0.20. Si sale distinto, ajustar `FOV_H_DEG` en `tests/sim/camera.py`.
- **Acelerómetro:** se supone 0x80 = 0 g y ~0x1A cuentas por g, y que con el Wiimote
  plano, botones arriba, Z marca +1 g. Falta confirmar el signo de X al girar
  el Wiimote en sentido horario (roll positivo): anotar los bytes AA AA AA del
  report 0x37 en plano, a +90° y a −90°.

## Core de precisión

### C17: roll del acelerómetro
- `sudo dbar4gun start` y `dbar4gun status` con el Wiimote apuntando a la TV:
  `roll_deg` ≈ 0. Girarlo unos 45° en sentido horario (visto desde detrás):
  `roll_deg` ≈ +45. Si sale −45, cambiar `ACC_X_SIGN` en `dbar4gun/core/tracker.py`.
- Con el Wiimote girado 180° (boca abajo), tapar y destapar la barra: el cursor
  debe seguir moviéndose en la dirección correcta (TL/TR ordenados por el
  acelerómetro).

### C5/C18: pérdida de dots
- Apuntar a una esquina del juego y tapar un LED de la barra con el dedo: el
  cursor no debe saltar (reconstrucción con el último vector).
- Apuntar fuera de la pantalla rápido hacia un lado: el cursor debe quedarse en
  ese borde (recarga fuera de pantalla), no congelado en el último punto.

### C9: distancia
- `dbar4gun status` muestra `distance_m`; comprobar con un metro a 2, 3 y 4 m
  (depende del FOV real, ver R3). Calibrar a 3 m y jugar a 2.5 m: la precisión
  debe mantenerse.

### C4/C12: captura de calibración
- A+plus: LED 1 encendido, el crosshair del juego se queda en el target de
  arriba a la izquierda. Pulsar B con el Wiimote quieto: un pulso de rumble
  corto. Pulsar B moviéndolo: dos pulsos (captura rechazada, se repite el paso).
- Tapar la barra y pulsar B: dos pulsos (`last_calibration_error: no_ir` en
  `dbar4gun status`).
- Al terminar: pulso largo y vuelven los LEDs del jugador (E12).
- Comprobar que el rumble funciona igual por Bluetooth y con la DolphinBar.

### C11: calibración guardada
- Tras calibrar, existe `/opt/retropie/configs/all/dbar4gun/calibration.json`
  (o `/var/lib/dbar4gun/` fuera de RetroPie), del usuario `pi` en RetroPie.
- Reiniciar el servicio: la calibración se carga (`calibration loaded: <clave>`
  en el log, `calibrated: true` en `dbar4gun status`).
- Por Bluetooth la clave debe ser `bt:<MAC del Wiimote>`
  (`cat /sys/class/hidraw/hidrawN/device/uevent`, campo `HID_UNIQ`). Con la
  DolphinBar debe ser `usb:<HID_PHYS>` y distinta para cada slot.

### C19: quick recalibration
- Con calibración guardada, A+plus pide solo 2 targets (LED 1 y LED 4, las
  esquinas de arriba). En el simulador es útil sobre todo si la barra se ha
  movido; tras moverse el jugador, la distance compensation ya corrige.
- A+minus vuelve al mapa nominal; entonces A+plus hace la calibración de 3 puntos.

### E8: status report
- Conectar y desconectar el Nunchuk con el juego abierto: el Wiimote debe seguir
  enviando IR (antes se reiniciaba todo con ~1.6 s de sleeps). `dbar4gun status`
  debe mostrar `battery` (se pide un status report en cada consulta).

### M1/P1: perfiles y socket
- `dbar4gun area 4:3` con un juego 4:3 en MAME: al apuntar al borde de la imagen
  del juego el crosshair queda en el borde.
- `/run/dbar4gun.sock` existe con permisos `srw-rw-rw-` y `dbar4gun status` funciona
  como usuario `pi` (sin sudo).
- Umbral de pulso inestable (`MAX_SPREAD_SEP = 0.15` en
  `dbar4gun/core/calibration.py`): con el pulso normal de varias personas, la
  captura no debería rechazarse casi nunca; un tirón claro sí. Ajustar si hace falta.

## Calibrator

### D7: lanzamiento desde EmulationStation
- Instalar con el scriptmodule (`retropie/dbar4gun.sh`) y activar el servicio.
  Debe aparecer "dbar4gun calibrator" en Ports (lo lanza runcommand, sin sudo).
- Lanzarlo desde EmulationStation: pygame debe tomar la pantalla completa (KMS)
  y, al salir con Home, EmulationStation debe volver a mostrarse bien.
- Imagen: debe ocupar toda la TV (no una esquina), sin bandas ni defectos, y
  moverse fluida (el cursor del Wiimote sin tirones). Dibuja a 720p como mucho y
  la GPU escala (pygame SCALED); con la versión anterior, por encima de 640x480
  iba lento y a veces salía en una esquina. Si va mal, probar la opción
  "calibrator resolution" del scriptmodule (por ejemplo 854x480) y anotar el
  resultado.
- El venv se crea con `--system-site-packages` para usar el `python3-pygame`
  de apt. Comprobar `"/opt/retropie/supplementary/dbar4gun/bin/python" -c "import pygame"`.
- Con el calibrator abierto, los botones del Wiimote siguen emitiendo teclas
  (por ejemplo Home → Enter). El calibrator solo usa los paquetes UDP, pero hay
  que comprobar que ES no reacciona por detrás.

### D9: IR diagnostics
- Con una fuente IR extra (vela, lámpara, ventana), debe aparecer en rojo como
  "extra IR source" y el par de la barra debe seguir siendo el correcto.
- `sudo dbar4gun start --experimental-ir-extended` y botón 1 en el diagnóstico:
  deben aparecer los tamaños de los dots (report 0x33). Tapar a medias un LED
  y comprobar que su tamaño baja. Al salir con Home vuelve el modo básico y el
  Nunchuk debe funcionar otra vez.
- Medido por Bluetooth: `irmode extended` cambia a reports 0x33 y `irmode basic`
  vuelve a 0x37 sin perder el emparejamiento (70–90 reports/s en los dos
  modos). Falta ver los tamaños con dots reales.

### D10: instalación
- Barra nivelada: con el Wiimote recto, inclinar la barra unos 5° y comprobar
  el valor y el signo (positivo = lado derecho más alto).
- Barra centrada: desplazar la barra 10 cm a un lado, calibrar y comprobar el %.

### D11: alcance
- Desde 1.5–2 m, barrer de arriba abajo: la parte baja debe salir en rojo y la
  distancia recomendada, al ponerse en ella, debe permitir llegar a la useful zone.
  La recomendación depende del FOV real (ver R3).

### D12: wizard
- Calibrar dos Wiimotes uno detrás de otro (A en el segundo al terminar).
- Mensajes: tapar la barra y disparar ("No IR"); disparar moviéndose ("Unsteady aim").
- La verificación del centro debe dar menos de 20 px con un pulso normal.

### P2: perfiles por juego
- `dbar4gun hooks install` (lo hace el scriptmodule). Lanzar un juego de MAME:
  `dbar4gun status` debe mostrar `"area": "4:3"` durante el juego y el perfil
  por defecto al salir.
- Comprobar que el contenido previo de `runcommand-onstart.sh` del usuario sigue ahí.

## Calibrator: shooting gallery, filter, players, area profiles, history

### C13/D13: One Euro y auto-tune
- Con `--smoothing-level 3` (por defecto) el cursor quieto no debe temblar en el
  juego y no debe notarse más retraso que en la v0.18.2 al mover rápido.
  `--smoothing-level 0` lo desactiva (debe temblar más).
- Auto-tune: 3 s quieto y 3 s moviendo. Comprobar que los valores aplicados se
  guardan (`dbar4gun status` → `filter`) y que se conservan al reiniciar el servicio
  y al recalibrar.
- El objetivo de jitter (0.5 px de juego) puede no alcanzarse con un pulso real;
  en ese caso se elige la fc_min más baja de la lista. Ajustar `FC_CANDIDATES` /
  `JITTER_TARGET_GAME` en `dbar4gun/gui/logic.py` si hace falta.

### D5: shooting gallery
- Tras calibrar, la galería debe dar una media de pocos px de juego. El resultado
  aparece en el history (D16) de esa VirtualGun.
- Elegir antes de empezar qué simular (pantalla completa, 4:3 con una
  resolución o un juego de la lista). Comparar el error en px de juego con lo
  que se nota jugando a ese juego. Las resoluciones de la lista salen del código
  de MAME; Point Blank 2/3, Ghoul Panic y los de Dreamcast no están porque su
  resolución se decide en marcha: si se mira en MAME (información de la pantalla),
  se pueden añadir.

### D14: jugadores y botones
- Los LEDs que muestra la pantalla coinciden con los del Wiimote y las teclas
  emitidas con lo que recibe el emulador (`evtest` sobre la VirtualGun).
- Detalle de la v0.18.2 (no cambiado): con B pulsado, al añadir + (u otro combo)
  `sync()` sale antes de escribir `BTN_LEFT` y el botón queda pulsado hasta soltar
  el combo. Comprobar si afecta a algún juego.

### D15: perfiles
- Editar un área custom con el Wiimote, aplicarla (A) y comprobar en MAME que
  el crosshair llega a los bordes. B la guarda como `default` en `profiles.cfg`
  junto con `useful_zone`; al reiniciar el servicio debe usarse.

### D16: history
- Calibrar dos veces, restaurar la primera desde el history: el cursor debe
  volver a la calibración anterior sin reiniciar.

## Tracking, calibración de 4 puntos y lectura

### C8: fuentes IR extra
- Con una lámpara incandescente o una ventana al sol en el campo de visión, el
  cursor no debe saltar. Con un reflejo (mesa brillante bajo la barra), el
  IR diagnostics debe mostrar los dots fusionados en uno.
- Tapar un LED con una lámpara cerca de la barra: no debe emparejar LED + lámpara
  (reconstruye durante 0.5 s).

### C15: IR sensitivity
- `--ir-sensitivity marcan` (por defecto) debe funcionar igual que la v0.18.2.
  Probar los niveles 1–5 con la barra de la Wii y la DolphinBar: con más
  distancia o luz ambiente hace falta más sensibilidad (nivel alto), y con
  reflejos, menos. Anotar qué nivel va mejor con cada barra.
- También desde el calibrator: *Hardware check* → IR quality. Si recomienda
  más o menos sensibilidad, el 2 prueba el nivel siguiente y vuelve a medir
  (se guarda en `hardware.json`). Verificado por Bluetooth: el cambio
  reconfigura la cámara con ACK sin errores y sigue emparejado; falta ver con
  dots reales qué nivel va mejor con cada barra (y con el LED dañado).

### C16: calibración de 4 puntos
- `--calibration 3`: A+plus pide las 4 esquinas (LED 1, LED 4, LED 3+4, LED 1+2).
  En el simulador mejora el máximo (31.7 → 15.1 px) y mucho si el jugador no
  está centrado; comprobar en un juego.

### E6/E7: lectura con timeout y desconexión
- **Qué envía la barra cuando un Wiimote se apaga** (DolphinBar): con
  `--log-level debug`, apagar un Wiimote. Debe aparecer
  `no new reports for 10 s, reconnecting` y, al encenderlo, volver solo.
  Anotar si la barra deja de enviar reports o repite el último.
- **Si `hid-wiimote` cambia el report mode**: con un Wiimote por Bluetooth, si
  llegan reports 0x30–0x3f distintos de 0x37, el driver reenvía el DRM
  (`12 00 37`) como mucho cada 0.5 s. El IR debe seguir funcionando.
- Con el Wiimote quieto encima de la mesa y la barra fuera de vista, comprobar
  que no se da por desconectado (el acelerómetro suele variar en el bit bajo;
  si no varía, en 10 s se reconfigura, que no hace daño).

### E10: logs
- `journalctl -u dbar4gun` muestra los mensajes con nivel (`INFO`, `WARNING`...).
  `--log-level debug` en el servicio para más detalle.

### E13: un solo proceso (experimental)
- `sudo dbar4gun start --single-process` con 2–4 Wiimotes: todos deben funcionar
  y `dbar4gun status` responder. Medir el uso de CPU en una RPi 3 frente al modo
  normal (`top`). Conectar un Wiimote congela el resto ~1.6 s (configuración del
  IR); es una limitación conocida de este modo.
- **Medido (2026-11-12, PC, 1 Wiimote por Bluetooth, daemon real sin uinput):**
  funciona: empareja, `status` en 6–15 ms, ~72 reports/s, `hw ir_sensitivity`
  e `irmode extended/basic` funcionan igual que en el modo normal. 1 proceso,
  26 MB frente a 3 procesos y 68 MB del modo normal, con la misma CPU (3 % de
  un core). Con la DolphinBar la diferencia es mayor (4 workers en el modo
  normal). La congelación al conectar un Wiimote ahora es ~0.8 s (antes la
  cámara se configuraba dos veces). Falta: varios Wiimotes a la vez y
  conectar/desconectar en caliente.

## Otras plataformas (P4)

Batocera y Recalbox quedan fuera por ahora.


- **Escritorio:** el servicio de `platforms/desktop/` y la GUI como usuario normal.

## Hardware check en el calibrator

`dbar4gun gui` → *Hardware check*, con el servicio en
marcha. Cada paso da un veredicto y, al final, el informe queda en
`<config dir>/hardware_report.json` (pásamelo para ajustar los valores por
defecto). Los valores aplicados van a `<config dir>/hardware.json`
(`dbar4gun hw` los muestra).

1. **Conexión:** DolphinBar (slot) o Bluetooth, reports/s y batería. Por
   Bluetooth la clave debe ser `bt:<MAC>` (C11).
2. **Calidad IR:** apoyar el Wiimote apuntando a la TV ~3 s. Con el LED dañado
   de la barra debe avisar "grupo de LEDs IZQUIERDO/DERECHO débil" (comprobar
   que el lado coincide con el LED dañado) y recomendar más `--ir-sensitivity`.
   Con una lámpara a la vista: "fuentes IR de más".
3. **Acelerómetro (C17):** girar el Wiimote despacio ±45° apuntando a la barra.
   Si dice INVERTIDO, pulsar 2 para aplicarlo y repetir el paso: debe salir
   correcto.
4. **FOV (R3):** de frente a la barra a una distancia medida con cinta **desde
   el Wiimote hasta la barra** (no por el suelo), elegirla con arriba/abajo y el
   ancho de la barra (centro a centro de los grupos de LEDs) con izq/der.
   Repetir a 2 distancias (B): los dos FOV deben coincidir en ±1°. Pulsar 2 para
   aplicarlo; después `distance_m` de `dbar4gun status` debe coincidir con la
   cinta y la reach test debe recomendar una distancia razonable.
5. **Barra:** apuntar al target del centro. Con `--bar` mal puesto debe decir
   que no coincide.
6. **Desconexión (E6):** apagar el Wiimote y volver a encenderlo. Anotar si
   dice "los reports se cortaron" o "la barra repitió el último report", y el
   tiempo hasta volver.

### Nunchuk ya conectado al emparejar
- Con el Nunchuk enchufado, emparejar el Wiimote (o reiniciar el servicio): el
  stick y C/Z deben funcionar sin desenchufarlo (`dbar4gun status` →
  `nunchuck: true`). Antes solo se detectaba al enchufarlo con el Wiimote ya
  conectado. Probar con la DolphinBar y por Bluetooth.
- **Verificado con la DolphinBar (2026-11-12):** driver arrancado desde cero con
  el Nunchuk ya enchufado: `nunchuck` detectado con el primer status pedido;
  stick en todo su rango (x 0.07–0.89, y 0.14–0.86) y C y Z por separado. Los
  datos de la extensión llegan sin cifrar sin inicializarla (lo hace la barra).
  Falta por Bluetooth.
