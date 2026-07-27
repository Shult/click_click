import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paths  # noqa: E402
from state import State  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Isole les écritures disque de chaque test."""
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path))
    monkeypatch.setattr(paths, "_home", None)
    yield tmp_path
    monkeypatch.setattr(paths, "_home", None)


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    """Repart d'un état vierge : le module expose un singleton mutable."""
    import player
    import recorder
    import sessions
    import state as state_module

    new = State()
    for module in (state_module, sessions, recorder, player):
        monkeypatch.setattr(module, "state", new, raising=False)
    return new
