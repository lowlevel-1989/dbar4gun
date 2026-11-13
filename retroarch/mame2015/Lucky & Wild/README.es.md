## Lucky & Wild

[English](README.md) | Español

Copia `luckywld.cfg` en la carpeta `cfg` del core, que está dentro de la carpeta de partidas guardadas de RetroArch.
En RetroPie, por defecto, las partidas se guardan junto a las ROMs:

```
~/RetroPie/roms/<sistema>/mame2015/cfg/luckywld.cfg
```

Por ejemplo, con los juegos en el sistema `lightgun`: `~/RetroPie/roms/lightgun/mame2015/cfg/luckywld.cfg`.
Si cambiaste la carpeta de partidas (`savefile_directory` en `retroarch.cfg`), usa
`<esa carpeta>/mame2015/cfg/luckywld.cfg`.

Si `luckywld.cfg` ya existe ahí, al copiarlo se sustituye.

| dispositivo | botón      | acción              |
|-------------|------------|---------------------|
| wiimote     | ir         | cursor              |
| wiimote     | b          | gatillo             |
| wiimote     | plus       | start               |
| wiimote     | minus      | moneda              |
| wiimote     | (P1) left  | girar a la izquierda |
| wiimote     | (P1) right | girar a la derecha  |
| wiimote     | (P1) up    | acelerar            |
| wiimote     | (P1) down  | frenar              |
| nunchuck    | (P1) stick | cruceta             |
| nunchuck    | (P1) c     | frenar              |
| combo       | b + home   | menú de mame        |
| combo       | b + minus  | key esc             |
| wiimote     | home       | key enter           |
| combo       | a + plus   | empezar calibración |
| combo       | a + minus  | reiniciar calibración |
