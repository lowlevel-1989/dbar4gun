# Desarrollo

[English](development.md) | Español

`tests/` funciona sin Wiimote: `tests/sim/` simula la cámara IR (TV, sensor
bar, posición del jugador y dónde apunta) y mide el error en una rejilla de 7x7.

```
pip install . pygame pytest
SDL_VIDEODRIVER=dummy python -m pytest -s
```

Los scripts de `tools/` son pruebas de hardware antiguas.

Qué hace cada carpeta y archivo del código: [dbar4gun/README.es.md](../dbar4gun/README.es.md).

## Referencias

El formato de los reports del Wiimote no es público y hubo que hacer ingeniería inversa. Estos recursos fueron muy útiles para crear dbar4gun:

- [https://www.wiibrew.org/wiki/Wiimote](https://www.wiibrew.org/wiki/Wiimote)
- [https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL](https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL)
