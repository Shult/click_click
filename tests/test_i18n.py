"""Un libellé manquant ne doit jamais faire tomber la fenêtre qui le porte."""

import pytest

import i18n
import settings


@pytest.fixture(autouse=True)
def patched_state(fresh_state, monkeypatch):
    monkeypatch.setattr(settings, "state", fresh_state)
    return fresh_state


# ── Catalogues ───────────────────────────────────────────────────────────────

def test_english_is_the_default():
    assert i18n.DEFAULT == "en"
    assert i18n.language() == "en"


@pytest.mark.parametrize("code", sorted(i18n.LANGUAGES))
def test_every_language_translates_every_key(code):
    """Une langue incomplète afficherait de l'anglais au milieu du reste."""
    reference = set(i18n._CATALOG[i18n.DEFAULT])
    assert set(i18n._CATALOG[code]) == reference


@pytest.mark.parametrize("code", sorted(i18n.LANGUAGES))
def test_every_language_names_itself(code):
    assert i18n.LANGUAGES[code].strip()


def test_no_text_is_left_empty():
    for code, catalog in i18n._CATALOG.items():
        for key, text in catalog.items():
            assert text.strip(), f"{code}/{key} est vide"


# ── Choix de la langue ───────────────────────────────────────────────────────

def test_set_language_applies_the_choice():
    i18n.set_language("fr")
    assert i18n.language() == "fr"
    assert i18n.t("settings.language") == "Langue"


@pytest.mark.parametrize("code", ["de", "", None, 42, "EN"])
def test_unknown_language_falls_back_to_the_default(code):
    i18n.set_language("fr")
    assert i18n.set_language(code) == i18n.DEFAULT
    assert i18n.language() == i18n.DEFAULT


def test_next_language_cycles_through_all_of_them():
    seen = []
    for _ in range(len(i18n.LANGUAGES)):
        seen.append(i18n.language())
        i18n.set_language(i18n.next_language())
    assert sorted(seen) == sorted(i18n.LANGUAGES)
    assert i18n.language() == i18n.DEFAULT  # revenu au point de départ


def test_language_name_is_written_in_its_own_language():
    i18n.set_language("fr")
    assert i18n.language_name() == "Français"
    assert i18n.language_name("en") == "English"


# ── Traduction ───────────────────────────────────────────────────────────────

def test_parameters_are_substituted():
    assert i18n.t("sessions.count", shown=3, total=12) == "3 / 12 session(s)"


def test_unknown_key_returns_the_key_itself():
    """Laid dans l'interface, mais diagnosticable — et sans exception."""
    assert i18n.t("clé.inexistante") == "clé.inexistante"


def test_missing_translation_falls_back_to_english(monkeypatch):
    monkeypatch.setitem(i18n._CATALOG, "fr", {})
    i18n.set_language("fr")
    assert i18n.t("sessions.load") == i18n._CATALOG["en"]["sessions.load"]


def test_missing_parameter_returns_the_untouched_text():
    assert "{" in i18n.t("sessions.count", shown=3)


def test_extra_parameters_are_ignored():
    assert i18n.t("sessions.none", inutile=1) == i18n.t("sessions.none")


# ── Persistance ──────────────────────────────────────────────────────────────

def test_language_survives_a_roundtrip():
    i18n.set_language("fr")
    settings.save()
    i18n.set_language("en")
    settings.load()
    assert i18n.language() == "fr"


def test_missing_language_falls_back_to_english():
    settings.path().write_text('{"play_delay": 2.0}', encoding="utf-8")
    i18n.set_language("fr")
    settings.load()
    assert i18n.language() == "en"


@pytest.mark.parametrize("value", ["klingon", 3, None, [], {"a": 1}])
def test_unusable_stored_language_falls_back(value):
    import json
    settings.path().write_text(json.dumps({"language": value}),
                               encoding="utf-8")
    settings.load()
    assert i18n.language() == "en"


def test_first_launch_stays_in_english():
    settings.load()  # aucun fichier
    assert i18n.language() == "en"
