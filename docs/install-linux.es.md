# Instalar en Linux (sin RetroPie)

[English](install-linux.md) | Español

Con RetroPie, sigue en su lugar [retropie/README.es.md](../retropie/README.es.md).

## 1. Dependencias

- git, python >= 3.7, bluez >= 5.0
- pygame, solo para el calibrator: `pip install pygame` o el paquete de tu
  distro

## 2. Instalar

```
git clone https://github.com/lowlevel-1989/dbar4gun
cd dbar4gun
python -m venv $(pwd)
source $(pwd)/bin/activate
pip install $(pwd)
```

Esto instala también evdev y pyudev.

## 3. Arrancar el servicio (como root)

```
dbar4gun start --width 1920 --height 1080
```

`--width` y `--height` son el tamaño de tu pantalla. Todas las opciones y
comandos: [usage.es.md](usage.es.md).

Para que arranque con el sistema, copia `platforms/desktop/dbar4gun.service` a
`/etc/systemd/system/`, cambia la ruta de `dbar4gun` (la de tu venv) y las
opciones, y ejecuta:

```
sudo systemctl daemon-reload
sudo systemctl enable --now dbar4gun
```

El calibrator y los comandos de control no necesitan root:
`dbar4gun gui --windowed`, `dbar4gun area 4:3`.

## 4. Emparejar el Wiimote (Bluetooth)

Con la DolphinBar (modo 4) no hay nada que emparejar.

Pulsa el botón SYNC rojo del Wiimote (debajo de la tapa de las pilas) y lanza
enseguida:

~~~
bluez/pair-wiimote.sh
~~~

Encuentra solo el Wiimote en modo SYNC (no hace falta saber su MAC), lo empareja
con `bluez/simple-agent` (si pide un PIN, pulsa Enter sin escribir nada) y lo
marca como de confianza, así que a partir de ahí se reconecta al pulsar
cualquier botón. Empareja cada Wiimote igual, de uno en uno.

Los mismos pasos a mano (la mayoría de distribuciones ya no traen `hcitool`),
con la MAC que muestra el scan para `Nintendo RVL-CNT-01`:

~~~
sudo -v
bluetoothctl --timeout 20 scan on & sleep 6; sudo python3 bluez/simple-agent -c DisplayYesNo hci0 XX:XX:XX:XX:XX:XX
bluetoothctl trust XX:XX:XX:XX:XX:XX
~~~

Si tienes problemas para volver a emparejar el Wiimote por Bluetooth, bórralo y
repite los pasos anteriores:

~~~
bluetoothctl remove XX:XX:XX:XX:XX:XX
~~~

## Dónde está la configuración

| plataforma | config dir (por defecto)             | area profile por juego |
|------------|--------------------------------------|------------------------|
| RetroPie   | `/opt/retropie/configs/all/dbar4gun` | hooks de runcommand (los instala el módulo de RetroPie, `dbar4gun hooks install`) |
| escritorio | `/var/lib/dbar4gun`                  | wrapper `platforms/desktop/dbar4gun-run.sh` |

`--config-dir` cambia la carpeta. Contiene `calibration.json` (calibraciones,
history, filter), `hardware.json` (valores medidos con el hardware check),
`hardware_report.json` y `profiles.cfg` (area profile por juego).

Para cambiar el area profile por juego en un escritorio, lanza el emulador con
el wrapper:

```
platforms/desktop/dbar4gun-run.sh arcade mame ghoul.zip -- mame ghoul
```

Batocera y Recalbox quedan fuera por ahora.
