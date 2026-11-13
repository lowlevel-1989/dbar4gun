## Time Crisis

[English](README.md) | Español

Copia `timecris.cfg` en la carpeta `cfg` del core, que está dentro de la carpeta de partidas guardadas de RetroArch.
En RetroPie, por defecto, las partidas se guardan junto a las ROMs:

```
~/RetroPie/roms/<sistema>/mame/cfg/timecris.cfg
```

Por ejemplo, con los juegos en el sistema `lightgun`: `~/RetroPie/roms/lightgun/mame/cfg/timecris.cfg`.
Si cambiaste la carpeta de partidas (`savefile_directory` en `retroarch.cfg`), usa
`<esa carpeta>/mame/cfg/timecris.cfg`.

Si `timecris.cfg` ya existe ahí, al copiarlo se sustituye.

| dispositivo | botón     | acción                |
|-------------|-----------|-----------------------|
| wiimote     | ir        | cursor                |
| wiimote     | b         | gatillo               |
| wiimote     | a         | pedal (cubrirse)      |
| nunchuck    | z         | pedal (cubrirse)      |
| wiimote     | plus      | start                 |
| wiimote     | minus     | moneda                |
| combo       | b + home  | menú de mame          |
| combo       | b + minus | key esc               |
| wiimote     | home      | key enter             |
| combo       | a + plus  | empezar calibración   |
| combo       | a + minus | reiniciar calibración |

