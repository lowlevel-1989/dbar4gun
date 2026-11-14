# dbar4gun en RetroPie

[English](README.md) | Español

`dbar4gun.sh` es el módulo de RetroPie-Setup de dbar4gun: instala el driver, lo
arranca como servicio y añade el calibrator a Ports.

## 1. Instalar

Descarga el módulo en RetroPie-Setup:

```
cd ~/RetroPie-Setup/scriptmodules/supplementary
curl -LO https://raw.githubusercontent.com/lowlevel-1989/dbar4gun/master/retropie/dbar4gun.sh
```

Abre RetroPie-Setup (`sudo ~/RetroPie-Setup/retropie_setup.sh`) y elige:

*Manage packages → driver → dbar4gun → Install*

## 2. Arrancar el servicio

*Manage packages → driver → dbar4gun → Configuration → Enable dbar4gun*

1. Elige la resolución de tu TV (1080p, 720p o manual).
2. Elige el modo de calibración (el primero, 3 puntos, es el de por defecto).
3. En el menú de opciones, revisa los valores y elige **dbar4gun start**.

Desde entonces el servicio arranca con el sistema. Las opciones de ese menú:

| opción | qué hace |
|---|---|
| width / height | tamaño de tu pantalla |
| smoothing level | suavizado del cursor: 0 desactivado, más alto = más suave |
| tilt correction | el cursor no se mueve al inclinar el Wiimote |
| default area profile | `full` (por defecto), `4:3` o `custom:...`: [area profiles](../docs/area-profiles.es.md) |
| useful zone | parte de la altura de la pantalla con targets (0.85) |
| distance compensation | la calibración sigue valiendo si te acercas o te alejas |
| calibrator en Ports | añade o quita *Ports → dbar4gun calibrator* |
| area profiles por juego | runcommand aplica el perfil de cada juego (`profiles.cfg`) |
| calibrator resolution / language | `native` o `1280x720` si va lento; `en` o `es` |
| Bluetooth: double input | ver [Bluetooth](#4-bluetooth) |

Para pararlo: *Configuration → Disable dbar4gun*. Para ver su estado:

```
systemctl status dbar4gun
```

## 3. Antes de jugar

- Desactiva los atajos de RetroArch que chocan con las pistolas: ver
  [Antes de jugar: RetroArch](../README.es.md#antes-de-jugar-retroarch).
- Calibra desde donde juegas: *Ports → dbar4gun calibrator*. Cómo:
  [calibración](../docs/calibration.es.md).

## 4. Bluetooth

Con la DolphinBar (modo 4) no hay nada que emparejar.

La Raspberry Pi 3 y posteriores tienen Bluetooth. Una Raspberry Pi 2 o anterior
necesita un dongle Bluetooth: [dongles que funcionan](https://elinux.org/RPi_USB_Bluetooth_adapters#Working_Bluetooth_adapters).

Empareja el Wiimote desde RetroPie:
[adding-a-bluetooth-controller-to-retropie](https://retropie.org.uk/docs/Bluetooth-Controller/#adding-a-bluetooth-controller-to-retropie)

Por Bluetooth, el kernel crea además un mando para el Wiimote (y otro para el
Nunchuk), así que EmulationStation y RetroArch recibirían cada botón dos veces:
de ese mando y como tecla de dbar4gun. dbar4gun bloquea esos dos mandos
mientras usa el Wiimote, y los botones llegan una sola vez. Para mantener las
dos entradas: menú de opciones → *Bluetooth: allow the double input* (o la
opción `--no-input-grab`). Con la DolphinBar no existe ese mando.

## 5. Actualizar

Vuelve a descargar `dbar4gun.sh` (paso 1) y, en el mismo menú, elige *Update*
(o *Install*). Las calibraciones y la configuración se conservan.
