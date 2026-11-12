# dbar4gun en otras plataformas

El driver es el mismo en todas: `dbar4gun start` (como root) más los comandos
del socket de control (`dbar4gun status`, `dbar4gun area 4:3`, ...). Lo que
cambia en cada plataforma es cómo arranca el servicio, dónde vive la
configuración y cómo el area profile sigue al juego.

| Plataforma | Config dir (por defecto)               | Hook del area profile por juego |
|------------|----------------------------------------|---------------------------------|
| RetroPie   | `/opt/retropie/configs/all/dbar4gun`   | `runcommand-onstart.sh` / `onend.sh` (los instala el scriptmodule, `dbar4gun hooks install`) |
| Escritorio | `/var/lib/dbar4gun`                    | wrapper `platforms/desktop/dbar4gun-run.sh` |

`--config-dir` cambia el directorio. Contiene `calibration.json` (calibraciones,
history, filter), `hardware.json` (valores medidos con el hardware check),
`hardware_report.json` y `profiles.cfg` (area profile por juego).

## Linux de escritorio

1. `pip install dbar4gun[gui]` (o un venv) y copiar
   `platforms/desktop/dbar4gun.service` a `/etc/systemd/system/`, ajustando la
   ruta y las opciones. `systemctl enable --now dbar4gun`.
2. El socket de control (`/run/dbar4gun.sock`) tiene permisos de escritura para
   todos, así que el calibrator y los comandos de perfil funcionan como usuario
   normal: `dbar4gun gui --windowed`, `dbar4gun area 4:3`.
3. Para cambiar el area profile por juego, lanzar el emulador con el wrapper:

   ```
   platforms/desktop/dbar4gun-run.sh arcade mame ghoul.zip -- mame ghoul
   ```

Batocera y Recalbox quedan fuera por ahora. Lo pendiente de verificar con
hardware en cada plataforma está en `docs/HARDWARE_CHECKS.md`.
