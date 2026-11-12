import pytest

from dbar4gun import wiimote
from dbar4gun.wiimote import (
    WIIMOTE_LED_1, WIIMOTE_LED_2, WIIMOTE_LED_3, WIIMOTE_LED_4, WIIMOTE_LED_ALL,
)

from tests.fakes import make_wiimote

EXPECTED_BY_PLAYER = {1: WIIMOTE_LED_1, 2: WIIMOTE_LED_2, 3: WIIMOTE_LED_3, 4: WIIMOTE_LED_4}


@pytest.mark.parametrize("index", range(1, 17))
def test_update_index_cycles_leds(monkeypatch, index):
    wm, io = make_wiimote(monkeypatch)

    assert wm.update_index(index) is True
    assert wm.is_pair is True
    assert wm.player == index

    expected = EXPECTED_BY_PLAYER[((index - 1) % 4) + 1]
    assert io.written[-1] == bytes([0x11, expected])


def test_update_index_zero_turns_all_leds_on(monkeypatch):
    wm, io = make_wiimote(monkeypatch)
    assert wm.update_index(0) is True
    assert io.written[-1] == bytes([0x11, WIIMOTE_LED_ALL])


def test_probe_0xf(monkeypatch):
    # 0xF es el test de conexion: jugador ((15 - 1) % 4) + 1 = 3 -> LED_3
    wm, io = make_wiimote(monkeypatch)
    assert wm.update_index(0xF) is True
    assert io.written[-1] == bytes([0x11, WIIMOTE_LED_3])


@pytest.mark.parametrize("index", [17, 20, 33, 255])
def test_update_index_above_16_never_fails(monkeypatch, index):
    wm, io = make_wiimote(monkeypatch)
    assert wm.update_index(index) is True
    assert io.written[-1][1] in (WIIMOTE_LED_1, WIIMOTE_LED_2, WIIMOTE_LED_3, WIIMOTE_LED_4)


def test_check_is_alive_reuses_original_index(monkeypatch):
    # antes se guardaba player % 4: el jugador 4 pasaba a 0 (todos los LEDs)
    wm, io = make_wiimote(monkeypatch)
    wm.update_index(4)
    wm.is_alive_time_last = 0
    wm.check_is_alive()
    assert io.written[-1] == bytes([0x11, WIIMOTE_LED_4])
