"""Les préférences ne doivent jamais empêcher l'application de démarrer."""

import json

import pytest

import settings


@pytest.fixture(autouse=True)
def patched_state(fresh_state, monkeypatch):
    monkeypatch.setattr(settings, "state", fresh_state)
    return fresh_state


def _write(payload):
    settings.path().write_text(json.dumps(payload), encoding="utf-8")


# ── Aller-retour ─────────────────────────────────────────────────────────────

def test_roundtrip(patched_state):
    patched_state.play_times = 13
    patched_state.play_delay = 3.0
    patched_state.play_skip_moves = True
    patched_state.sort_by_date = False
    patched_state.window_pos = (1670, 20)
    settings.save()

    for attr, other in (("play_times", 1), ("play_delay", 1.0),
                        ("play_skip_moves", False), ("sort_by_date", True),
                        ("window_pos", None)):
        setattr(patched_state, attr, other)
    settings.load()

    assert patched_state.play_times == 13
    assert patched_state.play_delay == 3.0
    assert patched_state.play_skip_moves is True
    assert patched_state.sort_by_date is False
    assert patched_state.window_pos == (1670, 20)


def test_save_is_atomic(patched_state):
    settings.save()
    assert list(settings.path().parent.glob("*.tmp")) == []


def test_first_launch_keeps_defaults(patched_state):
    settings.load()
    assert patched_state.play_times == 1
    assert patched_state.play_delay == 1.0
    assert patched_state.window_pos is None


# ── Robustesse ───────────────────────────────────────────────────────────────

def test_corrupt_file_keeps_defaults(patched_state):
    settings.path().write_text("{ pas du json", encoding="utf-8")
    settings.load()
    assert patched_state.play_times == 1


def test_wrong_toplevel_type_keeps_defaults(patched_state):
    _write(["pas", "un", "objet"])
    settings.load()
    assert patched_state.play_times == 1


@pytest.mark.parametrize("value", ["beaucoup", None, [], {"a": 1}])
def test_unusable_repetition_value_falls_back(patched_state, value):
    _write({"play_times": value})
    settings.load()
    assert patched_state.play_times == 1


def test_values_are_clamped_to_their_range(patched_state):
    _write({"play_times": -5, "play_delay": -3.0})
    settings.load()
    assert patched_state.play_times == 1
    assert patched_state.play_delay == 0.0

    _write({"play_times": 10**9, "play_delay": 10**9})
    settings.load()
    assert patched_state.play_times == settings.MAX_TIMES
    assert patched_state.play_delay == settings.MAX_DELAY


def test_float_repetition_is_truncated(patched_state):
    _write({"play_times": 4.9})
    settings.load()
    assert patched_state.play_times == 4


def test_non_boolean_flag_falls_back(patched_state):
    _write({"play_skip_moves": "oui"})
    settings.load()
    assert patched_state.play_skip_moves is False


@pytest.mark.parametrize("value", [[1], [1, 2, 3], "1,2", {"x": 1}, [None, 2]])
def test_malformed_window_position_is_ignored(patched_state, value):
    _write({"window_pos": value})
    settings.load()
    assert patched_state.window_pos is None


def test_partial_file_leaves_other_defaults(patched_state):
    _write({"play_delay": 2.5})
    settings.load()
    assert patched_state.play_delay == 2.5
    assert patched_state.play_times == 1
    assert patched_state.sort_by_date is True


def test_save_never_raises_when_disk_refuses(patched_state, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr("builtins.open", refuse)
    settings.save()  # ne doit pas propager
