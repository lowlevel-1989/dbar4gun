# Opciones y comandos

[English](usage.md) | Español

## Opciones del servicio

Todas las opciones: `dbar4gun start --help`.

| opción | por defecto | |
|---|---|---|
| `--calibration {0,1,2,3}` | 2 | 0 desactivada, 1 centro + arriba a la izquierda, 2 tres puntos, 3 cuatro puntos (homography) |
| `--width`, `--height` | 1920, 1080 | tamaño de la pantalla (rango ABS de la pistola) |
| `--disable-tilt-correction` | | |
| `--no-distance-compensation` | | entonces la precisión depende de mantener la distancia de la calibración |
| `--no-input-grab` | | Bluetooth: no bloquear los mandos del kernel del Wiimote y del Nunchuk (sus botones llegan dos veces) |
| `--smoothing-level N` | 3 | filtro One Euro: 0 desactivado, más alto = más suave |
| `--area` | full | `full`, `4:3`, `custom:x0,y0,w,h` |
| `--useful-zone` | 0.85 | fracción de la altura de la pantalla con targets |
| `--calibration-targets x1,y1,x2,y2,x3,y3` | | targets de 3 puntos en el espacio de la pistola |
| `--ir-sensitivity {1..5,marcan,cliff}` | marcan | sensibilidad de la cámara IR (niveles de wiibrew) |
| `--config-dir` | según la plataforma | calibraciones y `profiles.cfg` |
| `--socket` | /run/dbar4gun.sock | socket de control |
| `--port` | 35460 | puerto UDP para el calibrator |
| `--log-level` | info | |
| `--single-process` | | experimental: un solo proceso para todos los Wiimotes |
| `--experimental-ir-extended` | | permite el modo IR extendido (tamaño de los dots) |

### arrancar (o reiniciar) el servicio, como root

```
dbar4gun start --width 1920 --height 1080
```

### ver la versión

```
dbar4gun version
dbar4gun --version
```

### calibrator visual (necesita pygame: `pip install pygame`)
```
dbar4gun gui              # pantalla completa, solo con el Wiimote (Home para salir)
dbar4gun gui --windowed --width 1280 --height 720
dbar4gun gui --lang es    # en español
```

### parar el servicio, como root

```
dbar4gun stop
```

### conectar un dispositivo, como root

```
dbar4gun attach /dev/hidraw0
```

## Comandos de control

Hablan con el servicio en marcha a través de `/run/dbar4gun.sock` y no necesitan root.

```
dbar4gun status                 # Wiimotes, batería, Hz, calibración, distancia (JSON)
dbar4gun area 4:3               # area profile ahora
dbar4gun calibrate [2] [--quick]
dbar4gun cancel
dbar4gun reload                 # relee las calibraciones guardadas y hardware.json
dbar4gun hw [fov 38.5] [acc_x_sign -1] [bar_width 0.20] [ir_sensitivity 4|default]   # valores medidos del hardware
dbar4gun check --area 4:3 --useful-zone 0.85   # valida valores de opciones (sin daemon)
dbar4gun profile start <system> <emulator> [rom]   # lo usan los hooks de runcommand
dbar4gun hooks install|uninstall
```

El protocolo (también el paquete UDP del calibrator) está en [docs/PROTOCOL.md](PROTOCOL.md).
Instalar en Linux sin RetroPie: [install-linux.es.md](install-linux.es.md).

## Memoria

Ahora mismo dbar4gun consume ~24 MB. Cada Wiimote conectado por Bluetooth suma ~19 MB más, porque se crea un proceso dedicado para gestionar cada Wiimote.

En el caso de la DolphinBar, se detecta como cuatro Wiimotes aunque no estén conectados, lo que suma ~76 MB.

### Resumen del consumo de memoria

| Elemento                              | Consumo de memoria |
|---------------------------------------|--------------------|
| dbar4gun                              | ~24 MB             |
| monitor                               | ~19 MB             |
| Por cada Wiimote por Bluetooth        | ~19 MB             |
| DolphinBar (detectada como 4 Wiimotes)| ~76 MB             |

Si ya conoces la dirección de tu(s) Wiimote(s) (por ejemplo `/dev/hidraw0`), puedes conectarlo directamente con el subcomando `attach`. En ese caso no hace falta el monitor y el consumo de memoria baja muchísimo.

| Elemento                              | Consumo de memoria |
|---------------------------------------|--------------------|
| dbar4gun attach                       | ~24 MB             |
