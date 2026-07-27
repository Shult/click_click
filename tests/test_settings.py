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
    patched_state.play_speed = 2.0
    patched_state.play_skip_moves = True
    patched_state.sort_by_date = False
    patched_state.window_pos = (1670, 20)
    settings.save()

    for attr, other in (("play_times", 1), ("play_delay", 1.0),
                        ("play_speed", 1.0), ("play_skip_moves", False),
                        ("sort_by_date", True), ("window_pos", None)):
        setattr(patched_state, attr, other)
    settings.load()

    assert patched_state.play_times == 13
    assert patched_state.play_delay == 3.0
    assert patched_state.play_speed == 2.0
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


# ── Répétitions : mode infini ────────────────────────────────────────────────

def test_infinite_repetition_survives_a_roundtrip(patched_state):
    patched_state.play_times = settings.INFINITE
    settings.save()
    patched_state.play_times = 7
    settings.load()
    assert patched_state.play_times == settings.INFINITE


def test_negative_repetition_never_becomes_infinite(patched_state):
    """Ramener −5 dans l'intervalle donnerait 0, donc une boucle sans fin."""
    _write({"play_times": -5})
    settings.load()
    assert patched_state.play_times == 1


def test_format_times_shows_infinity_symbol():
    assert settings.format_times(settings.INFINITE) == "∞"
    assert settings.format_times(12) == "12"


@pytest.mark.parametrize("text,expected", [
    ("200", 200), ("1", 1), ("  42  ", 42), ("007", 7),
])
def test_parse_times_accepts_positive_integers(text, expected):
    assert settings.parse_times(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "0", "-3", "2.5", "abc", "1 2", None])
def test_parse_times_rejects_anything_else(text):
    assert settings.parse_times(text) is None


def test_parse_times_clamps_to_the_maximum():
    assert settings.parse_times("999999") == settings.MAX_TIMES


# ── Vitesse de lecture ───────────────────────────────────────────────────────

def test_speed_survives_a_roundtrip(patched_state):
    patched_state.play_speed = 0.25
    settings.save()
    patched_state.play_speed = 1.0
    settings.load()
    assert patched_state.play_speed == 0.25


def test_missing_speed_falls_back_to_normal(patched_state):
    _write({"play_delay": 2.0})
    settings.load()
    assert patched_state.play_speed == 1.0


@pytest.mark.parametrize("value", ["vite", None, [], {"a": 1}])
def test_unusable_speed_falls_back(patched_state, value):
    _write({"play_speed": value})
    settings.load()
    assert patched_state.play_speed == 1.0


def test_speed_is_clamped_to_its_range(patched_state):
    _write({"play_speed": 0.01})
    settings.load()
    assert patched_state.play_speed == settings.MIN_SPEED

    _write({"play_speed": 100})
    settings.load()
    assert patched_state.play_speed == settings.MAX_SPEED


def test_quarter_speed_is_not_rounded_to_two_tenths(patched_state):
    """Un arrondi au dixième écraserait 0,25× — le palier le plus lent."""
    _write({"play_speed": 0.25})
    settings.load()
    assert patched_state.play_speed == 0.25


def test_off_step_speed_is_kept(patched_state):
    """Un settings.json retouché à la main reste jouable tel quel."""
    _write({"play_speed": 1.2})
    settings.load()
    assert patched_state.play_speed == 1.2


@pytest.mark.parametrize("current,up,expected", [
    (1.0, True, 1.5),
    (1.0, False, 0.75),
    (0.25, False, 0.25),      # déjà au minimum
    (4.0, True, 4.0),         # déjà au maximum
    (1.2, True, 1.5),         # hors palier : le suivant, sans saut
    (1.2, False, 1.0),
])
def test_step_speed_moves_one_step(current, up, expected):
    assert settings.step_speed(current, up) == expected


def test_every_step_is_reachable_from_the_minimum():
    reached, value = [settings.MIN_SPEED], settings.MIN_SPEED
    for _ in range(len(settings.SPEEDS)):
        value = settings.step_speed(value, True)
        reached.append(value)
    assert sorted(set(reached)) == list(settings.SPEEDS)


def test_format_speed_drops_useless_decimals():
    assert settings.format_speed(1.0) == "1×"
    assert settings.format_speed(0.25) == "0.25×"
    assert settings.format_speed(1.5) == "1.5×"


# ── File d'enchaînement ──────────────────────────────────────────────────────

def test_playlist_survives_a_roundtrip(patched_state):
    patched_state.playlist = ["intro", "boucle", "sortie"]
    settings.save()
    patched_state.playlist = []
    settings.load()
    assert patched_state.playlist == ["intro", "boucle", "sortie"]


def test_playlist_keeps_duplicates(patched_state):
    """Rejouer deux fois la même session dans un enchaînement est légitime."""
    _write({"playlist": ["a", "b", "a"]})
    settings.load()
    assert patched_state.playlist == ["a", "b", "a"]


def test_missing_playlist_is_empty(patched_state):
    _write({"play_delay": 1.0})
    settings.load()
    assert patched_state.playlist == []


@pytest.mark.parametrize("value", ["a,b", {"a": 1}, 3, None])
def test_playlist_of_the_wrong_type_is_ignored(patched_state, value):
    _write({"playlist": value})
    settings.load()
    assert patched_state.playlist == []


def test_playlist_drops_entries_that_are_not_names(patched_state):
    _write({"playlist": ["bon", 42, None, ["a"], "aussi bon"]})
    settings.load()
    assert patched_state.playlist == ["bon", "aussi bon"]


def test_playlist_rejects_a_name_that_escapes_the_sessions_folder(patched_state):
    """Un fichier trafiqué ne doit pas faire lire ailleurs sur le disque."""
    _write({"playlist": ["../../ailleurs", "propre"]})
    settings.load()
    assert patched_state.playlist == ["propre"]


def test_playlist_is_capped(patched_state):
    _write({"playlist": [f"s{i}" for i in range(settings.MAX_PLAYLIST + 50)]})
    settings.load()
    assert len(patched_state.playlist) == settings.MAX_PLAYLIST


def test_saved_playlist_is_a_copy(patched_state):
    """Le payload ne doit pas partager la liste vivante de l'état."""
    patched_state.playlist = ["a"]
    settings.save()
    patched_state.playlist.append("b")
    settings.load()
    assert patched_state.playlist == ["a"]


# ── Robustesse (suite) ───────────────────────────────────────────────────────

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
