"""Préférences d'interface, conservées d'un lancement à l'autre.

Les réglages de lecture repartaient à zéro à chaque démarrage : pour une
routine qui rejoue treize fois avec trois secondes de pause, cela imposait de
recliquer les mêmes seize boutons chaque jour.

Un fichier de préférences illisible ou incohérent ne doit jamais empêcher
l'application de démarrer : toute valeur douteuse est remplacée par son
défaut, sans remonter d'erreur à l'appelant.
"""

import json
import logging
import os

import paths
from state import state

log = logging.getLogger(__name__)

FILENAME = "settings.json"

MAX_TIMES = 9999
MAX_DELAY = 3600.0

# Répétitions : « joue jusqu'à Échap ». Zéro plutôt qu'un sentinelle négative
# ou None, pour rester un entier sérialisable tel quel dans settings.json.
INFINITE = 0


def path():
    return paths.home() / FILENAME


# ── Conversions tolérantes ───────────────────────────────────────────────────

def _as_int(value, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def _as_float(value, default: float, lo: float, hi: float) -> float:
    try:
        return round(max(lo, min(hi, float(value))), 1)
    except (TypeError, ValueError):
        return default


def _as_bool(value, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_times(value) -> int:
    """Nombre de répétitions, `INFINITE` compris.

    Une valeur négative n'est pas un compte de passes : elle retombe sur le
    défaut au lieu d'être ramenée dans l'intervalle, où elle deviendrait zéro —
    c'est-à-dire une boucle infinie que l'utilisateur n'a pas demandée.
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    if n == INFINITE:
        return INFINITE
    return min(MAX_TIMES, n) if n > 0 else 1


def _as_pos(value):
    """Attend `[x, y]`. Toute autre forme vaut « pas de position mémorisée »."""
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(n, (int, float)) for n in value)):
        return (int(value[0]), int(value[1]))
    return None


# ── Saisie et affichage des répétitions ──────────────────────────────────────

def parse_times(text) -> int | None:
    """Convertit une saisie clavier en nombre de répétitions.

    Renvoie None si ce n'est pas un entier ≥ 1 ; l'appelant garde alors la
    valeur précédente. Le mode infini ne passe pas par ici : il a son propre
    bouton, taper « 0 » est plus souvent une faute de frappe qu'une intention.
    """
    try:
        n = int(str(text).strip())
    except (TypeError, ValueError):
        return None
    return min(MAX_TIMES, n) if n >= 1 else None


def format_times(n: int) -> str:
    return "∞" if n == INFINITE else str(n)


# ── Entrées / sorties ────────────────────────────────────────────────────────

def load() -> None:
    """Applique les préférences enregistrées à l'état courant."""
    try:
        with open(path(), encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return  # premier lancement
    except (OSError, json.JSONDecodeError):
        log.exception("préférences illisibles, valeurs par défaut conservées")
        return

    if not isinstance(raw, dict):
        log.warning("préférences au mauvais format, valeurs par défaut conservées")
        return

    state.play_times = _as_times(raw.get("play_times"))
    state.play_delay = _as_float(raw.get("play_delay"), 1.0, 0.0, MAX_DELAY)
    state.play_skip_moves = _as_bool(raw.get("play_skip_moves"), False)
    state.sort_by_date = _as_bool(raw.get("sort_by_date"), True)
    state.window_pos = _as_pos(raw.get("window_pos"))

    # Le journal reste en ASCII : stderr hérite de la page de code de la console
    # sous Windows, où « ∞ » lève une UnicodeEncodeError.
    times = "infini" if state.play_times == INFINITE else str(state.play_times)
    log.info(
        "préférences chargées : %s répétition(s), %.1fs de délai, skip_moves=%s",
        times, state.play_delay, state.play_skip_moves,
    )


def save() -> None:
    """Écrit les préférences. Ne lève jamais : ce n'est pas critique."""
    payload = {
        "play_times": state.play_times,
        "play_delay": state.play_delay,
        "play_skip_moves": state.play_skip_moves,
        "sort_by_date": state.sort_by_date,
        "window_pos": list(state.window_pos) if state.window_pos else None,
    }
    target = path()
    tmp = target.with_name(target.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, target)
    except OSError:
        log.exception("préférences non enregistrées")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
