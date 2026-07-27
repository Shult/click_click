import logging
import time

from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

import settings
import winapi
from recorder import data_to_key
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
            log.exception("relâchement impossible pour la touche %r", key)
    held_keys.clear()

    for btn in list(held_buttons):
        try:
            m.release(btn)
        except Exception:
            log.exception("relâchement impossible pour le bouton %r", btn)
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
            log.exception("clic non rejoué : %r", event)

    elif etype == "scroll":
        try:
            m.scroll(event["dx"], event["dy"])
        except Exception:
            log.exception("scroll non rejoué : %r", event)

    elif etype == "key":
        try:
            key = data_to_key(event)
        except (KeyError, ValueError):
            log.warning("touche inconnue dans la session : %r", event)
            return
        try:
            if event["pressed"]:
                kb.press(key)
                held_keys.add(key)
            else:
                kb.release(key)
                held_keys.discard(key)
        except Exception:
            log.exception("touche non rejouée : %r", event)


def play_loop():
    m = MouseController()
    kb = KeyboardController()
    held_keys: set = set()
    held_buttons: set = set()
    vs = winapi.virtual_screen()

    evts = (
        [e for e in state.events if e["type"] != "move"]
        if state.play_skip_moves else state.events
    )

    # Relevés une seule fois : toucher aux réglages pendant une lecture ne doit
    # pas changer le nombre de passes ni le tempo en cours de route.
    times = state.play_times
    # Une vitesse nulle diviserait par zéro et tuerait la passe ; les réglages
    # ne peuvent pas la produire, mais un settings.json retouché à la main si.
    speed = state.play_speed if state.play_speed > 0 else 1.0
    i = 0

    try:
        with winapi.timer_resolution():
            while times == settings.INFINITE or i < times:
                if state.stop_play.is_set():
                    break
                state.play_current = i + 1

                # Horloge absolue calée sur le début de la passe. En attendant
                # des deltas successifs, les erreurs d'arrondi s'accumulent et
                # une longue session dérive de plusieurs secondes. La vitesse
                # divise l'horodatage d'origine, elle ne se cumule donc pas non
                # plus d'un évènement au suivant.
                t0 = time.perf_counter()
                interrupted = False

                for event in evts:
                    if _wait_until(t0 + event["t"] / speed):
                        interrupted = True
                        break
                    _dispatch(event, m, kb, held_keys, held_buttons, vs)

                if interrupted:
                    break

                last = times != settings.INFINITE and i == times - 1
                if not last and state.stop_play.wait(state.play_delay):
                    break
                i += 1
    except Exception:
        log.exception("la lecture s'est interrompue sur une erreur")
    finally:
        # Ces trois lignes doivent s'exécuter quoi qu'il arrive : `playing`
        # resté à True laisse l'overlay en mode click-through, donc
        # définitivement inutilisable à la souris.
        _release_all(m, kb, held_keys, held_buttons)
        state.playing = False
        state.play_current = 0
