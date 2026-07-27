"""Le filet de sécurité du replay : rien ne doit rester enfoncé."""

import threading
import time

import pytest
from pynput.keyboard import KeyCode
from pynput.mouse import Button

import player

SCREEN = {"x": 0, "y": 0, "w": 1920, "h": 1080, "monitors": 1}


class FakeController:
    """Enregistre les appels au lieu de piloter le vrai périphérique."""

    def __init__(self):
        self.position = (0, 0)
        self.calls = []

    def press(self, what):
        self.calls.append(("press", what))

    def release(self, what):
        self.calls.append(("release", what))

    def scroll(self, dx, dy):
        self.calls.append(("scroll", dx, dy))


def test_release_all_releases_held_key_and_button():
    m, kb = FakeController(), FakeController()
    keys = {KeyCode.from_char("a")}
    buttons = {Button.left}

    player._release_all(m, kb, keys, buttons)

    assert kb.calls == [("release", KeyCode.from_char("a"))]
    assert m.calls == [("release", Button.left)]
    assert not keys and not buttons


def test_release_all_continues_after_a_failure():
    """Une touche récalcitrante ne doit pas empêcher de libérer les autres."""
    class Failing(FakeController):
        def release(self, what):
            if what == KeyCode.from_char("a"):
                raise OSError("boom")
            super().release(what)

    kb = Failing()
    keys = {KeyCode.from_char("a"), KeyCode.from_char("b")}
    player._release_all(FakeController(), kb, keys, set())

    assert kb.calls == [("release", KeyCode.from_char("b"))]
    assert not keys


def test_dispatch_tracks_press_and_release():
    m, kb = FakeController(), FakeController()
    keys, buttons = set(), set()

    down = {"type": "click", "x": 5, "y": 5, "button": "left", "pressed": True, "t": 0}
    player._dispatch(down, m, kb, keys, buttons, SCREEN)
    assert buttons == {Button.left}

    up = dict(down, pressed=False)
    player._dispatch(up, m, kb, keys, buttons, SCREEN)
    assert buttons == set()


def test_dispatch_clamps_coordinates_to_screen():
    m, kb = FakeController(), FakeController()
    event = {"type": "move", "x": 99_999, "y": -50, "t": 0}
    player._dispatch(event, m, kb, set(), set(), SCREEN)
    assert m.position == (1919, 0)


def test_dispatch_clamps_within_a_negative_origin_desktop():
    """Un écran à gauche du principal donne une origine virtuelle négative."""
    screen = {"x": -1080, "y": 0, "w": 4920, "h": 1920, "monitors": 3}
    m, kb = FakeController(), FakeController()

    player._dispatch({"type": "move", "x": -900, "y": 500, "t": 0},
                     m, kb, set(), set(), screen)
    assert m.position == (-900, 500)  # valide, ne doit pas être ramené à 0

    player._dispatch({"type": "move", "x": -5000, "y": 99_999, "t": 0},
                     m, kb, set(), set(), screen)
    assert m.position == (-1080, 1919)


def test_dispatch_survives_unknown_key():
    m, kb = FakeController(), FakeController()
    bad = {"type": "key", "key_type": "special", "key": "touche_inventée",
           "pressed": True, "t": 0}
    player._dispatch(bad, m, kb, set(), set(), SCREEN)
    assert kb.calls == []


# ── Boucle complète ──────────────────────────────────────────────────────────

@pytest.fixture
def fake_devices(monkeypatch):
    m, kb = FakeController(), FakeController()
    monkeypatch.setattr(player, "MouseController", lambda: m)
    monkeypatch.setattr(player, "KeyboardController", lambda: kb)
    return m, kb


def _instant(events):
    """Même contenu, horodatages à zéro : la boucle ne doit rien attendre."""
    return [dict(e, t=0.0) for e in events]


def test_play_loop_repeats_the_session(fresh_state, fake_devices):
    m, _ = fake_devices
    fresh_state.events = _instant([
        {"type": "click", "x": 1, "y": 1, "button": "left", "pressed": True},
        {"type": "click", "x": 1, "y": 1, "button": "left", "pressed": False},
    ])
    fresh_state.play_times = 3
    fresh_state.play_delay = 0.0

    player.play_loop()

    assert m.calls.count(("press", Button.left)) == 3
    assert fresh_state.playing is False
    assert fresh_state.play_current == 0


def test_play_loop_releases_a_key_left_pressed_by_the_session(fresh_state, fake_devices):
    """Une session déséquilibrée ne doit pas laisser la touche enfoncée."""
    _, kb = fake_devices
    fresh_state.events = _instant([
        {"type": "key", "key_type": "special", "key": "ctrl_l", "pressed": True},
    ])

    player.play_loop()

    assert kb.calls[-1][0] == "release"


def test_play_loop_releases_everything_when_stopped_mid_run(fresh_state, fake_devices):
    m, kb = fake_devices
    fresh_state.events = [
        {"type": "key", "key_type": "special", "key": "shift", "pressed": True, "t": 0.0},
        {"type": "click", "x": 1, "y": 1, "button": "left", "pressed": True, "t": 0.0},
        {"type": "move", "x": 2, "y": 2, "t": 30.0},  # jamais atteint
    ]
    threading.Timer(0.1, fresh_state.stop_play.set).start()

    player.play_loop()

    assert ("release", Button.left) in m.calls
    assert kb.calls[-1][0] == "release"
    assert fresh_state.playing is False


def test_play_loop_resets_state_after_an_unexpected_error(fresh_state, fake_devices, monkeypatch):
    """`playing` bloqué à True rendrait l'overlay définitivement click-through."""
    def boom(*args, **kwargs):
        raise RuntimeError("panne")

    monkeypatch.setattr(player, "_dispatch", boom)
    fresh_state.events = _instant([{"type": "move", "x": 1, "y": 1}])
    fresh_state.playing = True

    player.play_loop()

    assert fresh_state.playing is False
    assert fresh_state.play_current == 0


def test_play_loop_can_skip_moves(fresh_state, fake_devices):
    m, _ = fake_devices
    fresh_state.events = _instant([
        {"type": "move", "x": 9, "y": 9},
        {"type": "click", "x": 1, "y": 1, "button": "left", "pressed": True},
        {"type": "click", "x": 1, "y": 1, "button": "left", "pressed": False},
    ])
    fresh_state.play_skip_moves = True

    player.play_loop()

    assert m.position == (1, 1)


def test_wait_until_returns_immediately_when_stopped(fresh_state):
    fresh_state.stop_play.set()
    started = time.perf_counter()
    assert player._wait_until(time.perf_counter() + 10) is True
    assert time.perf_counter() - started < 0.5


def test_wait_until_honours_a_stop_during_the_wait(fresh_state):
    threading.Timer(0.05, fresh_state.stop_play.set).start()
    started = time.perf_counter()
    assert player._wait_until(time.perf_counter() + 10) is True
    assert time.perf_counter() - started < 1.0


def test_wait_until_reports_no_stop_for_a_past_target(fresh_state):
    assert player._wait_until(time.perf_counter() - 1) is False
