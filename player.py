import logging
import time

from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

import sessions
import settings
import winapi
from recorder import data_to_key
from sessions import SessionError
from state import state

log = logging.getLogger(__name__)

_BTN = {"left": Button.left, "right": Button.right, "middle": Button.middle}


def _release_all(m, kb, held_keys: set, held_buttons: set) -> None:
    """Relâche tout ce qui est resté enfoncé.

    Sans ce filet, une lecture interrompue en plein appui (Échap, exception,
    fermeture) laisse la touche ou le bouton physiquement enfoncé au niveau du
    système : l'utilisateur se retrouve avec Ctrl bloqué et doit tuer le
    processus.
    """
    for key in list(held_keys):
        try:
            kb.release(key)
        except Exception:
            log.exception("could not release key %r", key)
    held_keys.clear()

    for btn in list(held_buttons):
        try:
            m.release(btn)
        except Exception:
            log.exception("could not release button %r", btn)
    held_buttons.clear()


def _wait_until(target: float) -> bool:
    """Attend l'instant `target` (échelle perf_counter).

    Renvoie True si l'attente a été interrompue par une demande d'arrêt.
    `Event.wait` rend la main immédiatement quand le drapeau est levé, ce qui
    évite d'échantillonner l'arrêt toutes les quelques millisecondes.
    """
    remaining = target - time.perf_counter()
    if remaining <= 0:
        return state.stop_play.is_set()
    return state.stop_play.wait(remaining)


def _dispatch(event, m, kb, held_keys: set, held_buttons: set, vs: dict) -> None:
    etype = event["type"]

    if etype in ("move", "click", "scroll"):
        m.position = winapi.clamp_to_screen(event["x"], event["y"], vs)

    if etype == "click":
        btn = _BTN.get(event["button"], Button.left)
        try:
            if event["pressed"]:
                m.press(btn)
                held_buttons.add(btn)
            else:
                m.release(btn)
                held_buttons.discard(btn)
        except Exception:
            log.exception("click not replayed: %r", event)

    elif etype == "scroll":
        try:
            m.scroll(event["dx"], event["dy"])
        except Exception:
            log.exception("scroll not replayed: %r", event)

    elif etype == "key":
        try:
            key = data_to_key(event)
        except (KeyError, ValueError):
            log.warning("unknown key in the session: %r", event)
            return
        try:
            if event["pressed"]:
                kb.press(key)
                held_keys.add(key)
            else:
                kb.release(key)
                held_keys.discard(key)
        except Exception:
            log.exception("key not replayed: %r", event)


def can_play() -> bool:
    """Vrai s'il y a quelque chose à jouer : une session chargée ou une file."""
    return bool(state.events or state.playlist)


def _filtered(evts: list) -> list:
    if state.play_skip_moves:
        return [e for e in evts if e["type"] != "move"]
    return evts


def sequence() -> list[tuple[str, list]]:
    """Ce qui va être joué, dans l'ordre : la file, sinon la session chargée.

    Tout est lu avant la première injection. Découvrir qu'une session manque au
    milieu d'un enchaînement, souris et clavier déjà pris en main, est bien pire
    que de l'apprendre avant d'avoir commencé — et relire le disque à chaque
    passe d'une boucle infinie n'aurait aucun intérêt.
    """
    if not state.playlist:
        return [(state.active_session or "—", _filtered(state.events))]

    out = []
    for name in state.playlist:
        try:
            payload = sessions.read_session(name)
        except SessionError:
            # Une session absente ne doit pas annuler tout l'enchaînement.
            log.exception("session %r skipped in the queue", name)
            continue
        out.append((name, _filtered(payload["events"])))
    return out


def play_loop():
    m = MouseController()
    kb = KeyboardController()
    held_keys: set = set()
    held_buttons: set = set()
    vs = winapi.virtual_screen()
    steps = sequence()

    # Relevés une seule fois : toucher aux réglages pendant une lecture ne doit
    # pas changer le nombre de passes ni le tempo en cours de route.
    times = state.play_times
    # Une vitesse nulle diviserait par zéro et tuerait la passe ; les réglages
    # ne peuvent pas la produire, mais un settings.json retouché à la main si.
    speed = state.play_speed if state.play_speed > 0 else 1.0
    state.play_steps = len(steps)
    i = 0

    try:
        with winapi.timer_resolution():
            while steps and (times == settings.INFINITE or i < times):
                if state.stop_play.is_set():
                    break
                state.play_current = i + 1
                interrupted = False

                for step, (name, evts) in enumerate(steps, start=1):
                    # Même pause qu'entre deux passes : ce que l'utilisateur
                    # règle, c'est le temps laissé à l'application visée pour
                    # se remettre en place.
                    if step > 1 and state.stop_play.wait(state.play_delay):
                        interrupted = True
                        break
                    state.play_step, state.play_session = step, name

                    # Horloge absolue calée sur le début de la session. En
                    # attendant des deltas successifs, les erreurs d'arrondi
                    # s'accumulent et une longue session dérive de plusieurs
                    # secondes. La vitesse divise l'horodatage d'origine, elle ne
                    # se cumule donc pas non plus d'un évènement au suivant.
                    t0 = time.perf_counter()

                    for event in evts:
                        if _wait_until(t0 + event["t"] / speed):
                            interrupted = True
                            break
                        _dispatch(event, m, kb, held_keys, held_buttons, vs)

                    # Chaque session rend la souris et le clavier avant la
                    # suivante : une session déséquilibrée ne doit pas laisser un
                    # Ctrl enfoncé pendant tout le reste de l'enchaînement.
                    _release_all(m, kb, held_keys, held_buttons)
                    if interrupted:
                        break

                if interrupted:
                    break

                last = times != settings.INFINITE and i == times - 1
                if not last and state.stop_play.wait(state.play_delay):
                    break
                i += 1
    except Exception:
        log.exception("playback stopped on an error")
    finally:
        # Ce bloc doit s'exécuter quoi qu'il arrive : `playing` resté à True
        # laisse l'overlay en mode click-through, donc définitivement
        # inutilisable à la souris.
        _release_all(m, kb, held_keys, held_buttons)
        state.playing = False
        state.play_current = 0
        state.play_step = state.play_steps = 0
        state.play_session = None
