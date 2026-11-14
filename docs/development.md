# Development

English | [Español](development.es.md)

`tests/` runs without a Wiimote: `tests/sim/` simulates the IR camera (TV, sensor
bar, player position and aim) and measures the error on a 7x7 grid.

```
pip install . pygame pytest
SDL_VIDEODRIVER=dummy python -m pytest -s
```

The scripts in `tools/` are old hardware tests.

What each folder and file of the code does: [dbar4gun/README.md](../dbar4gun/README.md).

## References

The wiimote report format is not open and had to be reverse engineered. These resources have been very helpful when creating dbar4gun:

- [https://www.wiibrew.org/wiki/Wiimote](https://www.wiibrew.org/wiki/Wiimote)
- [https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL](https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL)
