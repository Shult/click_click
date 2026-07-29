"""Mise à jour de l'application depuis les releases GitHub.

Au démarrage, un fil d'arrière-plan interroge la dernière release du dépôt et
compare son tag à la version courante. Si une version plus récente existe,
l'interface le signale ; l'installation ne part que sur un clic de
l'utilisateur — jamais toute seule.

Le remplacement exploite une particularité de Windows : un exécutable en cours
d'exécution ne peut pas être écrasé, mais il peut être **renommé**. La séquence
est donc : télécharger `ClickClick.new.exe` à côté de l'exe, renommer l'exe
courant en `ClickClick.old.exe`, mettre le nouveau à sa place, relancer. La
nouvelle instance efface le `.old` à son démarrage (`cleanup_old`).

Tout passe par la bibliothèque standard (`urllib`) : une dépendance HTTP
pèserait sur l'exécutable pour deux requêtes. Un téléchargement fait par
l'application ne porte pas la marque du web, donc pas d'écran SmartScreen à
l'installation d'une mise à jour.

La vérification se coupe avec `"update_check": false` dans settings.json, et
n'a lieu que dans l'exécutable empaqueté : en développement, le source est le
dépôt lui-même, il n'y a rien à remplacer.
"""

import hashlib
import json
import logging
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from version import __version__

log = logging.getLogger(__name__)

REPO = "Shult/click_click"
ASSET_NAME = "ClickClick.exe"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
TIMEOUT = 8.0
CHUNK = 64 * 1024

# L'API GitHub refuse les requêtes sans User-Agent.
_HEADERS = {
    "User-Agent": f"ClickClick/{__version__}",
    "Accept": "application/vnd.github+json",
}


# ── Versions ─────────────────────────────────────────────────────────────────

def parse_tag(tag) -> Optional[tuple]:
    """`"v1.2.0"` ou `"1.2.0"` → `(1, 2, 0)`. None si le tag n'y ressemble pas."""
    if not isinstance(tag, str):
        return None
    tag = tag.strip().lstrip("vV")
    try:
        parts = tuple(int(p) for p in tag.split("."))
    except ValueError:
        return None
    return parts or None

def is_newer(tag, current: str = __version__) -> bool:
    """Vrai si `tag` désigne une version plus récente que `current`.

    Les longueurs différentes sont complétées par des zéros : `v1.2` et
    `v1.2.0` sont la même version, pas une mise à jour l'une de l'autre.
    """
    remote, local = parse_tag(tag), parse_tag(current)
    if remote is None or local is None:
        return False
    width = max(len(remote), len(local))
    pad = lambda v: v + (0,) * (width - len(v))  # noqa: E731
    return pad(remote) > pad(local)


# ── Détection ────────────────────────────────────────────────────────────────

def exe_path() -> Optional[Path]:
    """Chemin de l'exécutable empaqueté, None en développement."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None

def extract_info(payload) -> Optional[dict]:
    """Isole ce qui nous intéresse dans la réponse `releases/latest`.

    None si la release n'est pas plus récente que la version courante ou ne
    porte pas l'exécutable attendu. Le `digest` (sha256) est une donnée
    récente de l'API : absent, la vérification se rabat sur la taille seule.
    """
    if not isinstance(payload, dict) or not is_newer(payload.get("tag_name")):
        return None
    for asset in payload.get("assets") or []:
        if asset.get("name") != ASSET_NAME:
            continue
        url = asset.get("browser_download_url")
        if not url:
            return None
        digest = asset.get("digest") or ""
        return {
            "version": str(payload["tag_name"]).lstrip("vV"),
            "url": url,
            "size": asset.get("size"),
            "sha256": digest.removeprefix("sha256:") if digest.startswith("sha256:") else None,
        }
    return None

def check_latest() -> Optional[dict]:
    """Interroge GitHub. Bloquant ; None si pas de mise à jour ou pas de réseau.

    L'échec est silencieux (journal en debug) : hors ligne, API limitée ou
    indisponible, l'application démarre comme si de rien n'était.
    """
    req = urllib.request.Request(API_LATEST, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            payload = json.load(resp)
    except Exception as exc:
        log.debug("update check failed: %s", exc)
        return None
    info = extract_info(payload)
    if info:
        log.info("update available: %s (current %s)", info["version"], __version__)
    else:
        log.info("no update available (current %s)", __version__)
    return info

def check_async(on_update: Callable[[dict], None]) -> None:
    """Vérifie en arrière-plan ; `on_update(info)` ne part que s'il y a mieux.

    Le rappel est invoqué depuis le fil de vérification : à l'appelant de
    repasser dans le thread Tk avant de toucher aux widgets.
    """
    def worker():
        info = check_latest()
        if info:
            on_update(info)

    threading.Thread(target=worker, name="update-check", daemon=True).start()


# ── Installation ─────────────────────────────────────────────────────────────

class UpdateError(Exception):
    """Le téléchargement ne correspond pas à ce que la release annonce."""

def download(info: dict, dest: Path) -> None:
    """Télécharge l'exécutable vers `dest`, taille et empreinte vérifiées.

    Un fichier tronqué par une coupure réseau ou altéré en route ne doit
    jamais remplacer un exécutable qui fonctionne.
    """
    req = urllib.request.Request(info["url"], headers={"User-Agent": _HEADERS["User-Agent"]})
    sha = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(dest, "wb") as f:
        while chunk := resp.read(CHUNK):
            sha.update(chunk)
            size += len(chunk)
            f.write(chunk)
    if info.get("size") is not None and size != info["size"]:
        raise UpdateError(f"size mismatch: got {size}, expected {info['size']}")
    if info.get("sha256") and sha.hexdigest() != info["sha256"]:
        raise UpdateError("sha256 mismatch")

def swap(exe: Path, new: Path) -> None:
    """Met `new` à la place de `exe`, l'ancien devenant `<nom>.old.exe`.

    `exe` peut être en cours d'exécution : Windows interdit de l'écraser mais
    pas de le renommer. Si la mise en place échoue, l'ancien reprend son nom —
    l'utilisateur ne doit jamais se retrouver sans exécutable.
    """
    old = exe.with_name(exe.stem + ".old.exe")
    old.unlink(missing_ok=True)
    exe.rename(old)
    try:
        new.rename(exe)
    except OSError:
        old.rename(exe)
        raise

def apply(info: dict) -> None:
    """Télécharge, remplace et relance. Bloquant ; à appeler hors du thread Tk.

    Au retour, la nouvelle instance est lancée : il ne reste à l'appelant qu'à
    quitter proprement celle-ci.
    """
    exe = exe_path()
    if exe is None:
        raise UpdateError("not running from a packaged executable")
    new = exe.with_name(exe.stem + ".new.exe")
    try:
        download(info, new)
    except Exception:
        new.unlink(missing_ok=True)
        raise
    swap(exe, new)
    log.info("updated to %s, restarting", info["version"])
    subprocess.Popen(
        [str(exe)], cwd=str(exe.parent),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )

def cleanup_old() -> None:
    """Efface le `.old.exe` laissé par la mise à jour précédente.

    L'instance remplacée peut encore être en train de se fermer — son fichier
    est verrouillé tant qu'elle vit. Quelques tentatives espacées, en
    arrière-plan pour ne pas retarder le démarrage ; au pire, le prochain
    lancement l'aura.
    """
    exe = exe_path()
    if exe is None:
        return
    old = exe.with_name(exe.stem + ".old.exe")

    def worker():
        for _ in range(6):
            try:
                old.unlink(missing_ok=True)
                return
            except OSError:
                time.sleep(0.5)
        log.debug("could not remove %s, will retry next start", old.name)

    threading.Thread(target=worker, name="update-cleanup", daemon=True).start()
