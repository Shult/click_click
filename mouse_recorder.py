"""
ClickClick — Mouse & Keyboard Recorder / Replayer
──────────────────────────────────────────────────
F8    → Démarrer l'enregistrement
F9    → Arrêter et sauvegarder
F10   → Lancer la lecture
F11   → Masquer / réafficher l'overlay
Échap → Stopper la lecture
F12   → Quitter
"""

import logging
import sys
import threading

import logs
import winapi

# Avant toute création de fenêtre : Tkinter fige l'échelle DPI à l'import.
winapi.enable_dpi_awareness()
logs.setup()

from pynput import keyboard, mouse  # noqa: E402
from pynput.keyboard import Key  # noqa: E402

import paths  # noqa: E402
import player  # noqa: E402
import recorder  # noqa: E402
import settings  # noqa: E402
from overlay import OverlayApp  # noqa: E402
from player import play_loop  # noqa: E402
from state import state  # noqa: E402
from version import __version__  # noqa: E402

log = logging.getLogger(__name__)


def on_key_press(key):
    # Pendant une saisie de nom, les touches vont au champ texte.
    if state.modal_open and key != Key.f12:
        return

    if key == Key.f8:
        if state.recording or state.playing:
            return
        recorder.start()

    elif key == Key.f9:
        if not state.recording:
            return
        recorder.stop()
        duration = state.events[-1]["t"] if state.events else 0.0
        # Les écouteurs pynput tournent hors du thread Tk ; toucher aux widgets
        # depuis ici plante par intermittence.
        state.ui_queue.put(lambda app: app.show_save_dialog(duration))

    elif key == Key.f10:
        # Une file d'enchaînement garnie suffit : aucune session n'a besoin
        # d'être chargée en mémoire pour la jouer.
        if state.playing or state.recording or not player.can_play():
            return
        state.playing = True
        state.stop_play.clear()
        state.play_thread = threading.Thread(
            target=play_loop, name="player", daemon=True
        )
        state.play_thread.start()

    elif key == Key.f11:
        # Toucher aux widgets depuis un écouteur pynput plante par
        # intermittence : le basculement part dans la file du thread Tk.
        state.ui_queue.put(lambda app: app.toggle_visible())

    elif key == Key.esc:
        if state.playing:
            state.stop_play.set()

    elif key == Key.f12:
        request_quit()


def request_quit():
    """Demande l'arrêt et laisse la lecture relâcher ce qu'elle tient."""
    state.stop_play.set()
    state.quit.set()
    thread = state.play_thread
    if thread and thread.is_alive():
        thread.join(timeout=2.0)
        if thread.is_alive():
            log.warning("playback thread did not stop in time")


def main():
    log.info("ClickClick %s starting, data in %s", __version__, paths.home())
    settings.load()  # avant l'overlay : il y lit sa position de départ

    mouse_listener = mouse.Listener(
        on_click=recorder.on_click,
        on_scroll=recorder.on_scroll,
        on_move=recorder.on_move,
    )
    mouse_listener.start()

    kb_listener = keyboard.Listener(
        on_press=lambda k: (recorder.on_key_record(k, True), on_key_press(k)),
        on_release=lambda k: recorder.on_key_record(k, False),
    )
    kb_listener.start()

    try:
        OverlayApp(on_key_press).run()
    finally:
        request_quit()
        kb_listener.stop()
        mouse_listener.stop()
        settings.save()  # filet : les réglages sont déjà écrits à chaque change
        log.info("shutdown")

    sys.exit(0)


if __name__ == "__main__":
    main()
