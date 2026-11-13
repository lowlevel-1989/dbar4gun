## lr-mame: la Z del Nunchuk como botón 2 (opcional)

[English](README.md) | Español

La Z del Nunchuk del gun 1 envía `key b`, que MAME no usa por defecto.
Para usarla como la A del Wiimote en todos los juegos, elige una opción:

- **Menú de MAME** (b + home): Input Settings → Input Assignments (general) → Player 1
  Controls → **P1 Button 2**. Pulsa la **cruceta a la derecha** hasta que diga "Press
  Enter to append", después **home** (`key enter`) y la **Z del Nunchuk**.
- **Copiar [default.cfg](default.cfg)**: solo añade `key b` a P1 Button 2; MAME guarda
  solo lo que cambia respecto a sus valores por defecto, así que lo demás sigue igual.

Copia `default.cfg` en la carpeta `cfg` del core, que está dentro de la carpeta de partidas guardadas de RetroArch.
En RetroPie, por defecto, las partidas se guardan junto a las ROMs:

```
~/RetroPie/roms/<sistema>/mame/cfg/default.cfg
```

Por ejemplo, con los juegos en el sistema `lightgun`: `~/RetroPie/roms/lightgun/mame/cfg/default.cfg`.
Si cambiaste la carpeta de partidas (`savefile_directory` en `retroarch.cfg`), usa
`<esa carpeta>/mame/cfg/default.cfg`.

Si `default.cfg` ya existe ahí, al copiarlo se sustituye y se pierden los cambios generales que hubieras hecho en MAME: en ese caso usa el menú de MAME.
