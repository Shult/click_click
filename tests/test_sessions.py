import json
import re

import pytest

import i18n
import paths
import sessions
from sessions import SessionError


def _msg(key: str, **params) -> str:
    """Message attendu, désigné par sa clé plutôt que par sa formulation.

    Les messages d'erreur sont traduits : les recopier en dur ferait échouer
    ces tests à la première reformulation, et à chaque langue ajoutée.
    """
    return re.escape(i18n.t(key, **params))


# ── Noms de fichiers ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["run", "backup 2026", "a-b_c.1", "é"])
def test_sanitize_accepts_ordinary_names(name):
    assert sessions.sanitize_name(name) == name


@pytest.mark.parametrize("name", ["", "   ", "...", None])
def test_sanitize_rejects_empty(name):
    with pytest.raises(SessionError, match=_msg("error.name_empty")):
        sessions.sanitize_name(name)


@pytest.mark.parametrize("name", ["a/b", "a\\b", "c:", "a?", "a*", 'a"b', "a|b"])
def test_sanitize_rejects_path_characters(name):
    with pytest.raises(SessionError, match=_msg("error.name_invalid")):
        sessions.sanitize_name(name)


@pytest.mark.parametrize("name", ["CON", "nul", "Com1", "LPT9"])
def test_sanitize_rejects_windows_reserved_names(name):
    with pytest.raises(SessionError, match=_msg("error.name_reserved",
                                                name=name)):
        sessions.sanitize_name(name)


def test_sanitize_rejects_overlong_name():
    with pytest.raises(SessionError,
                       match=_msg("error.name_too_long",
                                  max=sessions.MAX_NAME_LEN)):
        sessions.sanitize_name("x" * (sessions.MAX_NAME_LEN + 1))


def test_sanitize_strips_trailing_dot_and_space():
    assert sessions.sanitize_name("  run.  ") == "run"


# ── Compression ──────────────────────────────────────────────────────────────

def test_compress_drops_repeated_positions():
    events = [
        {"type": "move", "x": 10, "y": 10, "t": 0.0},
        {"type": "move", "x": 10, "y": 10, "t": 0.1},
        {"type": "move", "x": 11, "y": 10, "t": 0.2},
        {"type": "move", "x": 11, "y": 10, "t": 0.3},
    ]
    out = sessions.compress(events)
    assert [(e["x"], e["y"]) for e in out] == [(10, 10), (11, 10)]


def test_compress_keeps_every_click_and_scroll():
    events = [
        {"type": "click", "x": 5, "y": 5, "button": "left", "pressed": True, "t": 0.0},
        {"type": "click", "x": 5, "y": 5, "button": "left", "pressed": False, "t": 0.1},
        {"type": "scroll", "x": 5, "y": 5, "dx": 0, "dy": -1, "t": 0.2},
        {"type": "key", "key_type": "char", "key": "a", "pressed": True, "t": 0.3},
    ]
    assert len(sessions.compress(events)) == len(events)


def test_compress_drops_move_redundant_with_preceding_click():
    events = [
        {"type": "click", "x": 5, "y": 5, "button": "left", "pressed": True, "t": 0.0},
        {"type": "move", "x": 5, "y": 5, "t": 0.1},
    ]
    out = sessions.compress(events)
    assert [e["type"] for e in out] == ["click"]


def test_compress_rounds_timestamps_to_milliseconds():
    out = sessions.compress([{"type": "move", "x": 1, "y": 1, "t": 0.1165818999}])
    assert out[0]["t"] == 0.117


def test_compress_does_not_mutate_input():
    events = [{"type": "move", "x": 1, "y": 1, "t": 0.123456}]
    sessions.compress(events)
    assert events[0]["t"] == 0.123456


def test_compress_preserves_timing_of_remaining_events():
    events = [
        {"type": "move", "x": 1, "y": 1, "t": 0.0},
        {"type": "move", "x": 1, "y": 1, "t": 1.0},
        {"type": "click", "x": 1, "y": 1, "button": "left", "pressed": True, "t": 2.0},
    ]
    out = sessions.compress(events)
    assert [e["t"] for e in out] == [0.0, 2.0]


# ── Aller-retour disque ──────────────────────────────────────────────────────

def test_save_then_load_roundtrip(fresh_state):
    events = [
        {"type": "move", "x": 3, "y": 4, "t": 0.0},
        {"type": "click", "x": 3, "y": 4, "button": "left", "pressed": True, "t": 0.5},
        {"type": "click", "x": 3, "y": 4, "button": "left", "pressed": False, "t": 0.6},
    ]
    sessions.save_session("run", events)
    assert sessions.load_session("run") is True
    assert fresh_state.events == events
    assert fresh_state.active_session == "run"


def test_saved_file_carries_metadata():
    sessions.save_session("run", [{"type": "move", "x": 1, "y": 2, "t": 1.5}])
    raw = json.loads(sessions.session_path("run").read_text(encoding="utf-8"))
    assert raw["version"] == sessions.SCHEMA_VERSION
    assert raw["duration"] == 1.5
    assert raw["event_count"] == 1
    assert raw["created_at"]
    assert "screen" in raw


def test_save_leaves_no_temporary_file():
    sessions.save_session("run", [{"type": "move", "x": 1, "y": 1, "t": 0.0}])
    leftovers = list(paths.sessions_dir().glob("*.tmp"))
    assert leftovers == []


def test_save_overwrites_existing_session():
    sessions.save_session("run", [{"type": "move", "x": 1, "y": 1, "t": 0.0}])
    sessions.save_session("run", [{"type": "move", "x": 9, "y": 9, "t": 0.0}])
    assert sessions.read_session("run")["events"][0]["x"] == 9


# ── Compatibilité v1 ─────────────────────────────────────────────────────────

def test_reads_v1_bare_array(fresh_state):
    events = [{"type": "move", "x": 1, "y": 2, "t": 0.25}]
    sessions.session_path("legacy").write_text(json.dumps(events), encoding="utf-8")

    assert sessions.load_session("legacy") is True
    assert fresh_state.events == events
    assert fresh_state.session_screen is None
    # Écran inconnu : pas d'alerte, on ne peut rien comparer.
    assert fresh_state.screen_mismatch is False


def test_v1_metadata_is_derived():
    events = [{"type": "move", "x": 1, "y": 2, "t": 0.25}]
    payload = sessions.parse(events)
    assert payload["version"] == 1
    assert payload["duration"] == 0.25
    assert payload["event_count"] == 1


def test_parse_rejects_unknown_shape():
    with pytest.raises(SessionError, match=_msg("error.unknown_format")):
        sessions.parse({"events": "pas une liste"})


def test_load_returns_false_on_corrupt_file(fresh_state):
    sessions.session_path("broken").write_text("{ pas du json", encoding="utf-8")
    assert sessions.load_session("broken") is False


def test_load_returns_false_when_missing():
    assert sessions.load_session("inconnue") is False


# ── Détection d'écart d'écran ────────────────────────────────────────────────

def test_screens_differ_on_resolution_change():
    a = {"x": 0, "y": 0, "w": 1920, "h": 1080}
    b = {"x": 0, "y": 0, "w": 2560, "h": 1440}
    assert sessions.screens_differ(a, b) is True
    assert sessions.screens_differ(a, dict(a)) is False


def test_screens_differ_is_silent_when_unknown():
    assert sessions.screens_differ(None, {"x": 0, "y": 0, "w": 1, "h": 1}) is False


def test_load_flags_screen_mismatch(fresh_state, monkeypatch):
    sessions.save_session("run", [{"type": "move", "x": 1, "y": 1, "t": 0.0}])
    monkeypatch.setattr(
        sessions.winapi, "virtual_screen",
        lambda: {"x": 0, "y": 0, "w": 800, "h": 600, "monitors": 1},
    )
    sessions.load_session("run")
    assert fresh_state.screen_mismatch is True


# ── Listage ──────────────────────────────────────────────────────────────────

def test_list_sessions_sorted_alphabetically():
    for name in ("b", "a", "c"):
        sessions.save_session(name, [])
    assert sessions.list_sessions(by_date=False) == ["a", "b", "c"]


def test_list_sessions_ignores_non_json():
    sessions.save_session("run", [])
    (paths.sessions_dir() / "notes.txt").write_text("x", encoding="utf-8")
    assert sessions.list_sessions() == ["run"]


# ── Filtre par nom ───────────────────────────────────────────────────────────

def test_filter_names_matches_a_substring_ignoring_case():
    names = ["Backup 2026", "run", "boucle backup"]
    assert sessions.filter_names(names, "BACK") == ["Backup 2026", "boucle backup"]


def test_filter_names_without_query_keeps_everything():
    names = ["a", "b"]
    assert sessions.filter_names(names, "   ") == names


def test_filter_names_returns_a_copy():
    names = ["a"]
    sessions.filter_names(names, "").append("b")
    assert names == ["a"]


def test_filter_names_tolerates_no_match():
    assert sessions.filter_names(["a", "b"], "zzz") == []


# ── Renommage ────────────────────────────────────────────────────────────────

def test_rename_moves_the_file_and_keeps_the_events():
    events = [{"type": "move", "x": 7, "y": 8, "t": 0.0}]
    sessions.save_session("avant", events)

    assert sessions.rename_session("avant", "après") == "après"

    assert not sessions.session_path("avant").exists()
    assert sessions.read_session("après")["events"] == events


def test_rename_follows_the_active_session(fresh_state):
    sessions.save_session("run", [])
    sessions.load_session("run")
    sessions.rename_session("run", "run2")
    assert fresh_state.active_session == "run2"


def test_rename_leaves_another_active_session_alone(fresh_state):
    sessions.save_session("a", [])
    sessions.save_session("b", [])
    fresh_state.active_session = "b"
    sessions.rename_session("a", "c")
    assert fresh_state.active_session == "b"


def test_rename_validates_the_new_name():
    sessions.save_session("run", [])
    with pytest.raises(SessionError, match=_msg("error.name_invalid")):
        sessions.rename_session("run", "a/b")
    assert sessions.session_path("run").exists()  # rien n'a bougé


def test_rename_refuses_to_overwrite_an_existing_session():
    sessions.save_session("a", [{"type": "move", "x": 1, "y": 1, "t": 0.0}])
    sessions.save_session("b", [{"type": "move", "x": 2, "y": 2, "t": 0.0}])

    with pytest.raises(SessionError, match=_msg("error.name_taken", name="b")):
        sessions.rename_session("a", "b")

    assert sessions.read_session("b")["events"][0]["x"] == 2


def test_rename_accepts_a_change_of_case_only():
    """« run » → « Run » n'est pas une collision, même sur NTFS."""
    sessions.save_session("run", [])
    assert sessions.rename_session("run", "Run") == "Run"
    assert sessions.list_sessions() == ["Run"]


def test_rename_to_the_same_name_is_a_no_op():
    sessions.save_session("run", [])
    assert sessions.rename_session("run", "  run  ") == "run"
    assert sessions.list_sessions() == ["run"]


def test_rename_follows_every_occurrence_in_the_playlist(fresh_state):
    """La file désigne les sessions par leur nom : un renommage la casserait."""
    sessions.save_session("run", [])
    fresh_state.playlist = ["intro", "run", "sortie", "run"]

    sessions.rename_session("run", "course")

    assert fresh_state.playlist == ["intro", "course", "sortie", "course"]


def test_rename_reports_a_missing_session():
    with pytest.raises(SessionError,
                       match=_msg("error.session_missing", name="fantôme")):
        sessions.rename_session("fantôme", "run")


# ── Suppression ──────────────────────────────────────────────────────────────

def test_delete_removes_the_file():
    sessions.save_session("run", [])
    sessions.delete_session("run")
    assert sessions.list_sessions() == []


def test_delete_clears_the_active_session_but_keeps_its_events(fresh_state):
    """La lecture en cours utilise les évènements en mémoire, pas le fichier."""
    events = [{"type": "move", "x": 1, "y": 1, "t": 0.0}]
    sessions.save_session("run", events)
    sessions.load_session("run")

    sessions.delete_session("run")

    assert fresh_state.active_session is None
    assert fresh_state.events == events


def test_delete_leaves_another_active_session_alone(fresh_state):
    sessions.save_session("a", [])
    sessions.save_session("b", [])
    fresh_state.active_session = "b"
    sessions.delete_session("a")
    assert fresh_state.active_session == "b"


def test_delete_removes_every_occurrence_from_the_playlist(fresh_state):
    sessions.save_session("run", [])
    fresh_state.playlist = ["run", "autre", "run"]

    sessions.delete_session("run")

    assert fresh_state.playlist == ["autre"]


def test_delete_keeps_the_playlist_object_alive(fresh_state):
    """La liste est mutée sur place : l'interface en garde la référence."""
    sessions.save_session("run", [])
    queue = fresh_state.playlist
    queue.append("run")

    sessions.delete_session("run")

    assert queue is fresh_state.playlist and queue == []


def test_delete_reports_a_missing_session():
    with pytest.raises(SessionError,
                       match=_msg("error.session_missing", name="fantôme")):
        sessions.delete_session("fantôme")


# ── Duplication ──────────────────────────────────────────────────────────────

def test_duplicate_copies_the_events_under_a_free_name():
    events = [{"type": "click", "x": 4, "y": 5, "button": "left",
               "pressed": True, "t": 0.0}]
    sessions.save_session("run", events)

    assert sessions.duplicate_session("run") == "run (2)"
    assert sessions.read_session("run (2)")["events"] == events


def test_duplicate_preserves_the_original_metadata():
    """Une copie doit être le reflet de l'original, date d'origine comprise."""
    sessions.save_session("run", [{"type": "move", "x": 1, "y": 1, "t": 2.0}])
    source = sessions.read_session("run")

    copy = sessions.read_session(sessions.duplicate_session("run"))

    assert copy["created_at"] == source["created_at"]
    assert copy["duration"] == source["duration"]


def test_duplicate_increments_until_a_name_is_free():
    sessions.save_session("run", [])
    assert sessions.duplicate_session("run") == "run (2)"
    assert sessions.duplicate_session("run") == "run (3)"


def test_duplicate_leaves_no_temporary_file():
    sessions.save_session("run", [])
    sessions.duplicate_session("run")
    assert list(paths.sessions_dir().glob("*.tmp")) == []


def test_duplicate_keeps_the_name_within_the_length_limit():
    long = "x" * sessions.MAX_NAME_LEN
    sessions.save_session(long, [])
    copy = sessions.duplicate_session(long)
    assert len(copy) <= sessions.MAX_NAME_LEN
    assert sessions.session_path(copy).exists()


def test_duplicate_does_not_touch_the_active_session(fresh_state):
    sessions.save_session("run", [])
    fresh_state.active_session = "run"
    sessions.duplicate_session("run")
    assert fresh_state.active_session == "run"


def test_duplicate_reports_a_missing_session():
    with pytest.raises(SessionError,
                       match=_msg("error.session_missing", name="fantôme")):
        sessions.duplicate_session("fantôme")
