"""
Mouse & Keyboard Recorder / Replayer
─────────────────────────────────────
F8    → Démarrer l'enregistrement
F9    → Arrêter et sauvegarder
F10   → Lancer la lecture
Échap → Stopper la lecture
F12   → Quitter
"""

import sys
import time
import threading
from pynput import mouse, keyboard
from pynput.keyboard import Key

from state import state
from recorder import on_click, on_scroll, on_move, on_key_record
from player import play_loop
from overlay import OverlayApp


def on_key_press(key):
    if key == Key.f8:
        if state.recording or state.playing:
            return
        state.events.clear()
        state.recording   = True
        state.start_time  = time.perf_counter()
        state.last_move_t = -1.0

    elif key == Key.f9:
        if not state.recording:
            return
        state.recording = False
        duration = state.events[-1]["t"] if state.events else 0
        threading.Thread(target=_ask_and_save, args=(duration,), daemon=True).start()

    elif key == Key.f10:
        if state.playing or state.recording or not state.events:
            return
        state.playing = True
        state.stop_play.clear()
        state.play_thread = threading.Thread(target=play_loop, daemon=True)
        state.play_thread.start()

    elif key == Key.esc:
        if state.playing:
            state.stop_play.set()

    elif key == Key.f12:
        state.quit.set()
        if state.app:
            state.app.root.after(0, state.app.root.destroy)


def _ask_and_save(duration: float):
    app = state.app
    if app:
        app.root.after(0, lambda: app._show_save_dialog(duration))


def main():
    mouse_listener = mouse.Listener(
        on_click=on_click, on_scroll=on_scroll, on_move=on_move,
    )
    mouse_listener.start()

    kb_listener = keyboard.Listener(
        on_press=lambda k: (on_key_record(k, True), on_key_press(k)),
        on_release=lambda k: on_key_record(k, False),
    )
    kb_listener.start()

    OverlayApp(on_key_press).run()

    kb_listener.stop()
    mouse_listener.stop()
    sys.exit(0)


if __name__ == "__main__":
    main()
