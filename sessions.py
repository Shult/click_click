"""Lecture et écriture des sessions.

Format v2 : un objet avec métadonnées (durée, date, géométrie des écrans) et
la liste d'évènements sous la clé `events`. Les sessions v1 — un tableau
d'évènements nu — restent lisibles telles quelles.
"""

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import paths
import winapi
from state import state

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2
MAX_NAME_LEN = 100

_INVALID_CHARS = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
_RESERVED_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


class SessionError(Exception):
    """Erreur exploitable telle quelle dans l'interface."""


# ── Nommage ──────────────────────────────────────────────────────────────────

def sanitize_name(name: str) -> str:
    """Valide un nom de session saisi par l'utilisateur.

    Le nom devient un nom de fichier : sans contrôle, une saisie contenant `/`
    ou `:` lève une OSError au fond de la pile d'écriture, invisible en mode
    fenêtré.
    """
    name = (name or "").strip().rstrip(". ")
    if not name:
        raise SessionError("Nom vide")
    if len(name) > MAX_NAME_LEN:
        raise SessionError(f"Nom trop long ({MAX_NAME_LEN} caractères max)")
    if any(c in _INVALID_CHARS for c in name):
        raise SessionError('Caractères interdits : < > : " / \\ | ? *')
    if name.upper() in _RESERVED_NAMES:
        raise SessionError(f"« {name} » est un nom réservé par Windows")
    return name


def session_path(name: str) -> Path:
    return paths.sessions_dir() / f"{name}.json"


def _free_name(base: str) -> str:
    """Premier « base (n) » disponible, sans dépasser la longueur maximale."""
    for n in range(2, 1000):
        suffix = f" ({n})"
        candidate = base[:MAX_NAME_LEN - len(suffix)].rstrip() + suffix
        if not session_path(candidate).exists():
            return candidate
    raise SessionError("Trop de copies de cette session")


# ── Compression ──────────────────────────────────────────────────────────────

def compress(events: list) -> list:
    """Allège la liste sans changer ce qui est rejoué.

    Un enregistrement échantillonne la souris à 60 Hz, y compris à l'arrêt :
    sur des sessions réelles, près d'un tiers des déplacements répètent la
    position précédente. Les supprimer ne change rien au replay, puisque le
    curseur y est déjà.
    """
    out = []
    last_pos = None

    for e in events:
        e = dict(e)
        if "t" in e:
            e["t"] = round(float(e["t"]), 3)

        if e.get("type") in ("move", "click", "scroll"):
            pos = (int(e["x"]), int(e["y"]))
            e["x"], e["y"] = pos
            if e["type"] == "move" and pos == last_pos:
                continue
            last_pos = pos

        out.append(e)

    return out


# ── Écriture ─────────────────────────────────────────────────────────────────

def build_payload(events: list) -> dict:
    events = compress(events)
    return {
        "version": SCHEMA_VERSION,
        "app": paths.APP_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration": round(events[-1]["t"], 3) if events else 0.0,
        "event_count": len(events),
        "screen": winapi.virtual_screen(),
        "events": events,
    }


def save_session(name: str, events: list | None = None) -> Path:
    """Écrit la session. Le nom doit déjà avoir passé `sanitize_name`."""
    events = state.events if events is None else events
    payload = build_payload(events)
    path = session_path(name)

    # Écriture en deux temps : une interruption en cours d'écriture laisserait
    # sinon un JSON tronqué à la place d'une session valide.
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise SessionError(f"Écriture impossible : {exc.strerror or exc}") from exc

    log.info(
        "session « %s » enregistrée : %d évènements, %.2fs, %d ko",
        name, payload["event_count"], payload["duration"],
        path.stat().st_size // 1024,
    )
    return path


# ── Lecture ──────────────────────────────────────────────────────────────────

def parse(raw) -> dict:
    """Normalise le contenu d'un fichier en payload v2."""
    if isinstance(raw, list):
        # v1 : tableau d'évènements nu, sans métadonnées.
        return {
            "version": 1,
            "events": raw,
            "duration": raw[-1]["t"] if raw else 0.0,
            "event_count": len(raw),
            "screen": None,
            "created_at": None,
        }
    if isinstance(raw, dict) and isinstance(raw.get("events"), list):
        raw.setdefault("version", SCHEMA_VERSION)
        raw.setdefault("screen", None)
        raw.setdefault("created_at", None)
        raw.setdefault("event_count", len(raw["events"]))
        raw.setdefault(
            "duration", raw["events"][-1]["t"] if raw["events"] else 0.0
        )
        return raw
    raise SessionError("Format de session non reconnu")


def read_session(name: str) -> dict:
    path = session_path(name)
    try:
        with open(path, encoding="utf-8") as f:
            return parse(json.load(f))
    except FileNotFoundError as exc:
        raise SessionError(f"Session « {name} » introuvable") from exc
    except json.JSONDecodeError as exc:
        raise SessionError(f"Fichier illisible (ligne {exc.lineno})") from exc
    except OSError as exc:
        raise SessionError(f"Lecture impossible : {exc.strerror or exc}") from exc


def screens_differ(recorded: dict | None, current: dict | None) -> bool:
    if not recorded or not current:
        return False
    return any(recorded.get(k) != current.get(k) for k in ("x", "y", "w", "h"))


def load_session(name: str) -> bool:
    """Charge une session dans l'état courant.

    Signale un écart de géométrie d'écran : les coordonnées sont absolues, donc
    une session enregistrée sur une autre résolution rejouera à côté.
    """
    try:
        payload = read_session(name)
    except SessionError:
        log.exception("chargement de « %s » impossible", name)
        return False

    state.events = payload["events"]
    state.active_session = name
    state.session_screen = payload.get("screen")
    state.screen_mismatch = screens_differ(
        state.session_screen, winapi.virtual_screen()
    )
    if state.screen_mismatch:
        log.warning(
            "« %s » enregistrée sur %r, écran actuel %r : le replay sera décalé",
            name, state.session_screen, winapi.virtual_screen(),
        )
    log.info("session « %s » chargée : %d évènements", name, len(state.events))
    return True


# ── Gestion des fichiers de session ──────────────────────────────────────────

def rename_session(old: str, new: str) -> str:
    """Renomme une session et renvoie le nom retenu.

    Le nom passe par `sanitize_name` : il est saisi à la main, donc au même
    titre qu'une sauvegarde il peut contenir de quoi faire échouer l'écriture
    au fond de la pile, là où l'erreur serait invisible.
    """
    name = sanitize_name(new)
    if name == old:
        return name

    src, dst = session_path(old), session_path(name)
    # Sur NTFS, `exists()` répond vrai à une simple différence de casse :
    # « run » → « Run » n'est pas une collision, c'est le même fichier.
    if dst.exists() and name.lower() != old.lower():
        raise SessionError(f"« {name} » existe déjà")

    try:
        os.replace(src, dst)
    except FileNotFoundError as exc:
        raise SessionError(f"Session « {old} » introuvable") from exc
    except OSError as exc:
        raise SessionError(f"Renommage impossible : {exc.strerror or exc}") from exc

    if state.active_session == old:
        state.active_session = name
    log.info("session « %s » renommée en « %s »", old, name)
    return name


def delete_session(name: str) -> None:
    """Supprime le fichier d'une session. Irréversible."""
    try:
        session_path(name).unlink()
    except FileNotFoundError as exc:
        raise SessionError(f"Session « {name} » introuvable") from exc
    except OSError as exc:
        raise SessionError(f"Suppression impossible : {exc.strerror or exc}") from exc

    if state.active_session == name:
        # Les évènements chargés restent en mémoire : ils sont peut-être en
        # cours de lecture, et c'est l'état normal juste après un
        # enregistrement non sauvegardé.
        state.active_session = None
    log.info("session « %s » supprimée", name)


def duplicate_session(name: str) -> str:
    """Copie une session sous le premier nom libre « name (n) »."""
    src = session_path(name)
    if not src.exists():
        raise SessionError(f"Session « {name} » introuvable")

    new = _free_name(name)
    dst = session_path(new)
    tmp = dst.with_name(dst.name + ".tmp")
    try:
        # Copie octet pour octet : relire puis réécrire le JSON régénérerait
        # les métadonnées, et la copie ne serait plus le reflet de l'original.
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise SessionError(f"Copie impossible : {exc.strerror or exc}") from exc

    log.info("session « %s » dupliquée en « %s »", name, new)
    return new


# ── Listage ──────────────────────────────────────────────────────────────────

def filter_names(names: list[str], query: str) -> list[str]:
    """Ne garde que les noms contenant `query`, casse ignorée."""
    q = (query or "").strip().casefold()
    if not q:
        return list(names)
    return [n for n in names if q in n.casefold()]


def list_sessions(by_date: bool = True) -> list[str]:
    try:
        files = [p for p in paths.sessions_dir().iterdir() if p.suffix == ".json"]
    except OSError:
        log.exception("listage du dossier de sessions impossible")
        return []
    if by_date:
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    else:
        files.sort(key=lambda p: p.name.lower())
    return [p.stem for p in files]
