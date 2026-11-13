## Operation Wolf

[English](README.md) | Español

Copia `opwolf.cfg` en la carpeta `cfg` del core, que está dentro de la carpeta de partidas guardadas de RetroArch.
En RetroPie, por defecto, las partidas se guardan junto a las ROMs:

```
~/RetroPie/roms/<sistema>/mame/cfg/opwolf.cfg
```

Por ejemplo, con los juegos en el sistema `lightgun`: `~/RetroPie/roms/lightgun/mame/cfg/opwolf.cfg`.
Si cambiaste la carpeta de partidas (`savefile_directory` en `retroarch.cfg`), usa
`<esa carpeta>/mame/cfg/opwolf.cfg`.

Si `opwolf.cfg` ya existe ahí, al copiarlo se sustituye.

| dispositivo | botón     | acción                |
|-------------|-----------|-----------------------|
| wiimote     | ir        | cursor                |
| wiimote     | b         | gatillo               |
| wiimote     | a         | granada               |
| nunchuck    | z         | granada               |
| wiimote     | plus      | start                 |
| wiimote     | minus     | moneda                |
| combo       | b + home  | menú de mame          |
| combo       | b + minus | key esc               |
| wiimote     | home      | key enter             |
| combo       | a + plus  | empezar calibración   |
| combo       | a + minus | reiniciar calibración |

