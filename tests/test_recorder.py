"""Équilibrage des appuis : toute session doit refermer ce qu'elle ouvre."""

from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button

import recorder


def _start(state):
    recorder.start()
    assert state.recording is True


def test_start_sets_clock_before_arming_recording(fresh_state):
    """`ts()` ne doit jamais être appelé avec l'horloge du run précédent."""
    fresh_state.start_time = 0.0
    recorder.start()
    assert fresh_state.start_time > 0.0
    assert fresh_state.recording is True


def test_start_clears_previous_run(fresh_state):
    fresh_state.events.append({"type": "move", "x": 0, "y": 0, "t": 0.0})
    fresh_state.held_keys[("char", "a")] = {"key_type": "char", "key": "a"}
    recorder.start()
    assert fresh_state.events == []
    assert fresh_state.held_keys == {}


def test_stop_releases_key_still_held(fresh_state):
    _start(fresh_state)
    recorder.on_key_record(KeyCode.from_char("a"), True)
    recorder.stop()

    key_events = [e for e in fresh_state.events if e["type"] == "key"]
    assert [e["pressed"] for e in key_events] == [True, False]
    assert fresh_state.held_keys == {}


def test_stop_releases_modifier_still_held(fresh_state):
    _start(fresh_state)
    recorder.on_key_record(Key.ctrl_l, True)
    recorder.stop()

    last = fresh_state.events[-1]
    assert last == {
        "type": "key", "pressed": False, "t": last["t"],
        "key_type": "special", "key": "ctrl_l",
    }


def test_stop_releases_interrupted_drag(fresh_state):
    _start(fresh_state)
    recorder.on_click(100, 200, Button.left, True)
    recorder.on_move(150, 250)
    recorder.stop()

    last = fresh_state.events[-1]
    assert last["type"] == "click"
    assert last["pressed"] is False
    assert last["button"] == "left"
    # Relâché là où le curseur se trouve, pas là où le drag a commencé.
    assert (last["x"], last["y"]) == (150, 250)


def test_stop_adds_nothing_when_balanced(fresh_state):
    _start(fresh_state)
    recorder.on_click(1, 1, Button.left, True)
    recorder.on_click(1, 1, Button.left, False)
    recorder.on_key_record(KeyCode.from_char("a"), True)
    recorder.on_key_record(KeyCode.from_char("a"), False)
    before = len(fresh_state.events)
    recorder.stop()
    assert len(fresh_state.events) == before


def test_hotkeys_are_never_recorded(fresh_state):
    _start(fresh_state)
    for key in recorder.HOTKEYS:
        recorder.on_key_record(key, True)
    recorder.stop()
    assert fresh_state.events == []


def test_nothing_recorded_while_idle(fresh_state):
    recorder.on_click(1, 1, Button.left, True)
    recorder.on_move(2, 2)
    recorder.on_scroll(3, 3, 0, 1)
    recorder.on_key_record(KeyCode.from_char("a"), True)
    assert fresh_state.events == []


def test_moves_are_throttled(fresh_state):
    _start(fresh_state)
    for i in range(50):
        recorder.on_move(i, i)
    moves = [e for e in fresh_state.events if e["type"] == "move"]
    # Échantillonnage à 60 Hz : une rafale instantanée ne produit qu'un point.
    assert len(moves) < 50


def test_key_roundtrip_through_serialisation():
    for key in (Key.ctrl_l, KeyCode.from_char("x"), Key.f5):
        assert recorder.data_to_key(recorder.key_to_data(key)) == key
