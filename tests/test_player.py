"""Le filet de sécurité du replay : rien ne doit rester enfoncé."""

import threading
import time

import pytest
from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button

import player
import sessions
import settings

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


def test_play_loop_repeats_until_stopped_when_infinite(fresh_state, fake_devices, monkeypatch):
    """`play_times = INFINITE` ne s'arrête que sur demande d'arrêt."""
    passes = []
    real_dispatch = player._dispatch

    def counting(event, *args):
        passes.append(fresh_state.play_current)
        if len(passes) == 5:
            fresh_state.stop_play.set()
        real_dispatch(event, *args)

    monkeypatch.setattr(player, "_dispatch", counting)
    fresh_state.events = _instant([{"type": "move", "x": 1, "y": 1}])
    fresh_state.play_times = settings.INFINITE
    fresh_state.play_delay = 0.0

    player.play_loop()

    assert passes == [1, 2, 3, 4, 5]


def test_play_loop_ignores_repetitions_changed_mid_run(fresh_state, fake_devices, monkeypatch):
    """Le compte de passes est relevé au départ, pas relu à chaque tour."""
    passes = []

    def bump(event, *args):
        passes.append(fresh_state.play_current)
        fresh_state.play_times = 99  # l'utilisateur touche au réglage en cours

    monkeypatch.setattr(player, "_dispatch", bump)
    fresh_state.events = _instant([{"type": "move", "x": 1, "y": 1}])
    fresh_state.play_times = 2
    fresh_state.play_delay = 0.0

    player.play_loop()

    assert passes == [1, 2]


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


# ── Vitesse de lecture ───────────────────────────────────────────────────────

@pytest.fixture
def recorded_waits(monkeypatch):
    """Relève les instants attendus au lieu de les attendre vraiment."""
    targets = []

    def fake_wait(target):
        targets.append(target)
        return False

    monkeypatch.setattr(player, "_wait_until", fake_wait)
    return targets


def test_play_loop_divides_timestamps_by_the_speed(fresh_state, fake_devices, recorded_waits):
    fresh_state.events = [
        {"type": "move", "x": 1, "y": 1, "t": 0.0},
        {"type": "move", "x": 2, "y": 2, "t": 1.0},
        {"type": "move", "x": 3, "y": 3, "t": 3.0},
    ]
    fresh_state.play_speed = 2.0

    player.play_loop()

    origin = recorded_waits[0]
    assert [round(t - origin, 6) for t in recorded_waits] == [0.0, 0.5, 1.5]


def test_play_loop_stays_on_an_absolute_clock(fresh_state, fake_devices, recorded_waits):
    """Chaque instant vaut t0 + t/vitesse : aucune dérive cumulée possible."""
    fresh_state.events = [{"type": "move", "x": 1, "y": 1, "t": i * 0.1}
                          for i in range(200)]
    fresh_state.play_speed = 0.25

    player.play_loop()

    origin = recorded_waits[0]
    expected = round(199 * 0.1 / 0.25, 6)
    assert round(recorded_waits[-1] - origin, 6) == expected


def test_play_loop_at_normal_speed_keeps_the_timestamps(fresh_state, fake_devices, recorded_waits):
    fresh_state.events = [{"type": "move", "x": 1, "y": 1, "t": 0.0},
                          {"type": "move", "x": 2, "y": 2, "t": 2.5}]

    player.play_loop()

    origin = recorded_waits[0]
    assert [round(t - origin, 6) for t in recorded_waits] == [0.0, 2.5]


def test_play_loop_survives_a_zero_speed(fresh_state, fake_devices, recorded_waits):
    """Une vitesse nulle venue d'un fichier retouché ne doit pas diviser par 0."""
    fresh_state.events = [{"type": "move", "x": 1, "y": 1, "t": 1.0}]
    fresh_state.play_speed = 0.0

    player.play_loop()

    assert len(recorded_waits) == 1
    assert fresh_state.playing is False


def test_play_loop_ignores_a_speed_changed_mid_run(fresh_state, fake_devices,
                                                   recorded_waits, monkeypatch):
    def bump(event, *args):
        fresh_state.play_speed = 4.0  # l'utilisateur touche au réglage en cours

    monkeypatch.setattr(player, "_dispatch", bump)
    fresh_state.events = [{"type": "move", "x": 1, "y": 1, "t": 0.0},
                          {"type": "move", "x": 2, "y": 2, "t": 1.0}]
    fresh_state.play_speed = 1.0

    player.play_loop()

    origin = recorded_waits[0]
    assert round(recorded_waits[-1] - origin, 6) == 1.0


# ── File d'enchaînement ──────────────────────────────────────────────────────

def _save(name, x):
    sessions.save_session(name, [{"type": "move", "x": x, "y": x, "t": 0.0}])


def test_can_play_accepts_a_playlist_without_a_loaded_session(fresh_state):
    assert player.can_play() is False
    fresh_state.playlist = ["a"]
    assert player.can_play() is True


def test_can_play_accepts_a_loaded_session_without_a_playlist(fresh_state):
    fresh_state.events = [{"type": "move", "x": 1, "y": 1, "t": 0.0}]
    assert player.can_play() is True


def test_sequence_falls_back_to_the_loaded_session(fresh_state):
    fresh_state.events = [{"type": "move", "x": 9, "y": 9, "t": 0.0}]
    fresh_state.active_session = "chargée"
    assert player.sequence() == [("chargée", fresh_state.events)]


def test_sequence_reads_the_playlist_in_order(fresh_state):
    _save("a", 1)
    _save("b", 2)
    fresh_state.playlist = ["b", "a"]

    assert [name for name, _ in player.sequence()] == ["b", "a"]


def test_sequence_skips_a_missing_session(fresh_state):
    _save("a", 1)
    fresh_state.playlist = ["fantôme", "a"]

    assert [name for name, _ in player.sequence()] == ["a"]


def test_sequence_applies_skip_moves_to_every_queued_session(fresh_state):
    sessions.save_session("a", [
        {"type": "move", "x": 1, "y": 1, "t": 0.0},
        {"type": "click", "x": 1, "y": 1, "button": "left", "pressed": True, "t": 0.1},
    ])
    fresh_state.playlist = ["a", "a"]
    fresh_state.play_skip_moves = True

    typed = [[e["type"] for e in evts] for _, evts in player.sequence()]
    assert typed == [["click"], ["click"]]


def test_play_loop_chains_the_queued_sessions_in_order(fresh_state, fake_devices, monkeypatch):
    seen = []
    monkeypatch.setattr(player, "_dispatch", lambda e, *a: seen.append(e["x"]))
    _save("a", 1)
    _save("b", 2)
    fresh_state.playlist = ["b", "a"]
    fresh_state.play_delay = 0.0

    player.play_loop()

    assert seen == [2, 1]


def test_play_loop_repeats_the_whole_chain(fresh_state, fake_devices, monkeypatch):
    seen = []
    monkeypatch.setattr(player, "_dispatch", lambda e, *a: seen.append(e["x"]))
    _save("a", 1)
    _save("b", 2)
    fresh_state.playlist = ["a", "b"]
    fresh_state.play_times = 2
    fresh_state.play_delay = 0.0

    player.play_loop()

    assert seen == [1, 2, 1, 2]


def test_play_loop_ignores_the_loaded_session_when_the_queue_is_garnished(
        fresh_state, fake_devices, monkeypatch):
    seen = []
    monkeypatch.setattr(player, "_dispatch", lambda e, *a: seen.append(e["x"]))
    _save("a", 1)
    fresh_state.events = [{"type": "move", "x": 99, "y": 99, "t": 0.0}]
    fresh_state.playlist = ["a"]
    fresh_state.play_delay = 0.0

    player.play_loop()

    assert seen == [1]


def test_play_loop_releases_the_keys_between_two_chained_sessions(fresh_state, fake_devices):
    """Une session déséquilibrée ne doit pas bloquer Ctrl sur toute la file."""
    _, kb = fake_devices
    sessions.save_session("bloquante", [
        {"type": "key", "key_type": "special", "key": "ctrl_l",
         "pressed": True, "t": 0.0},
    ])
    _save("suivante", 5)
    fresh_state.playlist = ["bloquante", "suivante"]
    fresh_state.play_delay = 0.0

    player.play_loop()

    assert kb.calls == [("press", Key.ctrl_l), ("release", Key.ctrl_l)]


def test_play_loop_does_nothing_when_every_queued_session_is_missing(
        fresh_state, fake_devices):
    m, _ = fake_devices
    fresh_state.playlist = ["fantôme", "aussi fantôme"]

    player.play_loop()

    assert m.calls == []
    assert fresh_state.playing is False


def test_play_loop_reports_the_current_step_then_clears_it(fresh_state, fake_devices, monkeypatch):
    seen = []

    def note(event, *args):
        seen.append((fresh_state.play_session, fresh_state.play_step,
                     fresh_state.play_steps))

    monkeypatch.setattr(player, "_dispatch", note)
    _save("a", 1)
    _save("b", 2)
    fresh_state.playlist = ["a", "b"]
    fresh_state.play_delay = 0.0

    player.play_loop()

    assert seen == [("a", 1, 2), ("b", 2, 2)]
    assert (fresh_state.play_session, fresh_state.play_step,
            fresh_state.play_steps) == (None, 0, 0)


def test_play_loop_pauses_between_two_chained_sessions(fresh_state, fake_devices):
    """Le délai réglé sert aussi de respiration entre deux sessions."""
    _save("a", 1)
    _save("b", 2)
    fresh_state.playlist = ["a", "b"]
    fresh_state.play_delay = 0.2

    started = time.perf_counter()
    player.play_loop()

    assert time.perf_counter() - started >= 0.2


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
