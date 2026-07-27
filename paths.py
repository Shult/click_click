"""Emplacements de fichiers de l'application.

Tout est ancré sur un chemin absolu déduit de l'exécutable (ou du source en
dev). Lancée en double-clic, depuis un terminal ou par un launcher tiers,
l'application lit et écrit toujours au même endroit — le répertoire de travail
au démarrage n'a aucune influence.
"""

import os
import sys
from pathlib import Path

APP_NAME = "ClickClick"
ENV_HOME = "CLICKCLICK_HOME"

_home: Path | None = None


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _is_writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".clickclick_write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def home() -> Path:
    """Racine des données : sessions et journal.

    À côté de l'exécutable par défaut (installation portable), repli sur
    %LOCALAPPDATA% si ce dossier est en lecture seule (cas d'un exe déposé
    dans Program Files). CLICKCLICK_HOME force l'emplacement.
    """
    global _home
    if _home is not None:
        return _home

    override = os.environ.get(ENV_HOME)
    if override:
        _home = Path(override).expanduser().resolve()
    else:
        base = _base_dir()
        if _is_writable(base):
            _home = base
        else:
            local = os.environ.get("LOCALAPPDATA")
            _home = (Path(local) if local else Path.home()) / APP_NAME

    _home.mkdir(parents=True, exist_ok=True)
    return _home


def sessions_dir() -> Path:
    d = home() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_file() -> Path:
    return home() / "clickclick.log"
