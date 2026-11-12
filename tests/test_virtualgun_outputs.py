"""describe_outputs() coincide con lo que escribe VirtualGunDevice.sync()."""

import itertools

import evdev
import pytest

from dbar4gun import virtualgun as V


class FakeUInput(object):
    def __init__(self):
        self.state = {}

    def write(self, etype, code, value):
        if etype == evdev.ecodes.EV_KEY:
            self.state[code] = bool(value)

    def syn(self):
        pass


def pressed_names(buttons, port, nb=0, joy=(0.5, 0.5)):
    gun = V.VirtualGunDevice(1920, 1080, port)
    gun.index_map = (port % (len(V._MAP) // V._MAP_INDEX_MAX)) * V._MAP_INDEX_MAX
    gun.virtualgun = FakeUInput()
    gun.set_buttons(buttons, nb, joy)
    gun.set_cursor([0.5, 0.5])
    gun.sync()
    out = set()
    for code, v in gun.virtualgun.state.items():
        if v:
            n = evdev.ecodes.KEY.get(code) or evdev.ecodes.BTN.get(code)
            out.add(n[0] if isinstance(n, list) else n)
    return out


BUTTONS = [V.VIRTUALGUN_BUTTON_A_MASK, V.VIRTUALGUN_BUTTON_B_MASK, V.VIRTUALGUN_BUTTON_HOME_MASK,
           V.VIRTUALGUN_BUTTON_PLUS_MASK, V.VIRTUALGUN_BUTTON_MINUS_MASK, V.VIRTUALGUN_BUTTON_ONE_MASK,
           V.VIRTUALGUN_BUTTON_TWO_MASK, V.VIRTUALGUN_BUTTON_UP_MASK, V.VIRTUALGUN_BUTTON_LEFT_MASK]


@pytest.mark.parametrize("port", [0, 1, 3])
def test_matches_sync_for_all_pairs(port):
    combos = [0] + BUTTONS + [a | b for a, b in itertools.combinations(BUTTONS, 2)]
    for buttons in combos:
        assert set(V.describe_outputs(buttons, port)) == pressed_names(buttons, port), hex(buttons)


def test_nunchuck():
    names = V.describe_outputs(0, 0, V.VIRTUALGUN_BUTTON_Z_MASK, (0.1, 0.5))
    assert set(names) == pressed_names(0, 0, V.VIRTUALGUN_BUTTON_Z_MASK, (0.1, 0.5))
    assert "KEY_LEFT" in names
