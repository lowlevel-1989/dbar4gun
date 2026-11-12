"""
Escenarios de aceptacion de precision (TV 45", grid 7x7 en el area 4:3).
`make_driver()` devuelve un objeto con calibrate(scene, roll_deg) y feed(report).
"""

from tests.sim.metrics import measure_grid
from tests.sim.scene import Scene, TV


def _run(make_driver, calib_scene, play_scene, calib_roll=0.0, play_roll=0.0):
    drv = make_driver()
    drv.calibrate(calib_scene, calib_roll)
    return measure_grid(play_scene, drv.feed, roll_deg=play_roll)


def run_all(make_driver):
    tv = TV(45)
    at = lambda x, d: Scene(tv=tv, player=(x, 0.0, d))
    return [
        ("3 m",                         _run(make_driver, at(0, 3.0), at(0, 3.0))),
        ("calib roll 0, juego roll 15", _run(make_driver, at(0, 3.0), at(0, 3.0), 0.0, 15.0)),
        ("calib 3.0 m, juego 2.6 m",    _run(make_driver, at(0, 3.0), at(0, 2.6))),
        ("50 cm de lado",               _run(make_driver, at(0, 3.0), at(0.5, 3.0))),
    ]


def format_table(title, rows):
    lines = ["", title]
    for name, s in rows:
        lines.append("  {:<30} {}".format(name, s))
    return "\n".join(lines)
