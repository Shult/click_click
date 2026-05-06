"""
Mouse Recorder & Replayer
─────────────────────────
F8   → Démarrer l'enregistrement
F9   → Arrêter et sauvegarder
F10  → Lancer la lecture (session active)
Échap → Stopper la lecture
F12  → Quitter

Sessions sauvegardées dans ./sessions/
"""

import json
import time
import threading
import os
import sys
from pynput import mouse, keyboard
from pynput.mouse import Button, Controller
from pynput.keyboard import Key

SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# STATE
# ──────────────────────────────────────────────

events = []
recording = False
playing = False
start_time = None
play_thread = None
stop_play_event = threading.Event()
quit_event = threading.Event()
active_session = None  # nom de la session chargée/enregistrée
play_times = 1
play_delay = 1.0
play_skip_moves = False

btn_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}


# ──────────────────────────────────────────────
# SESSIONS
# ──────────────────────────────────────────────

def session_path(name):
    return os.path.join(SESSIONS_DIR, f"{name}.json")

def list_sessions():
    files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith(".json")]
    if not files:
        print("  (aucune session enregistrée)")
        return
    print(f"  {'Nom':<25} {'Événements':>10}  {'Durée':>8}")
    print("  " + "─" * 48)
    for f in sorted(files):
        name = f[:-5]
        try:
            with open(os.path.join(SESSIONS_DIR, f)) as fp:
                data = json.load(fp)
            count = len(data)
            duration = data[-1]["t"] if data else 0
            print(f"  {name:<25} {count:>10}  {duration:>7.2f}s")
        except Exception:
            print(f"  {name:<25}   (erreur lecture)")

def save_session(name):
    with open(session_path(name), "w") as f:
        json.dump(events, f, indent=2)

def load_session(name):
    global events, active_session
    path = session_path(name)
    if not os.path.exists(path):
        print(f"⚠ Session '{name}' introuvable.")
        return False
    with open(path) as f:
        events = json.load(f)
    active_session = name
    duration = events[-1]["t"] if events else 0
    print(f"✔ Session '{name}' chargée — {len(events)} événements ({duration:.2f}s)")
    return True


# ──────────────────────────────────────────────
# RECORD CALLBACKS
# ──────────────────────────────────────────────

def ts():
    return time.perf_counter() - start_time

def on_click(x, y, button, pressed):
    if recording:
        events.append({"type": "click", "x": x, "y": y,
                        "button": button.name, "pressed": pressed, "t": ts()})

def on_scroll(x, y, dx, dy):
    if recording:
        events.append({"type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy, "t": ts()})

def on_move(x, y):
    if recording:
        events.append({"type": "move", "x": x, "y": y, "t": ts()})


# ──────────────────────────────────────────────
# PLAY
# ──────────────────────────────────────────────

def play_loop():
    global playing
    m = Controller()
    evts = [e for e in events if e["type"] != "move"] if play_skip_moves else events

    for i in range(play_times):
        if stop_play_event.is_set():
            break
        print(f"▶ Passe {i + 1}/{play_times}")
        prev_t = 0.0

        for event in evts:
            if stop_play_event.is_set():
                break
            wait = event["t"] - prev_t
            if wait > 0:
                end = time.perf_counter() + wait
                while time.perf_counter() < end:
                    if stop_play_event.is_set():
                        break
                    time.sleep(0.01)
            prev_t = event["t"]

            etype = event["type"]
            x, y = int(event["x"]), int(event["y"])
            if etype == "move":
                m.position = (x, y)
            elif etype == "click":
                m.position = (x, y)
                btn = btn_map.get(event["button"], Button.left)
                (m.press if event["pressed"] else m.release)(btn)
            elif etype == "scroll":
                m.position = (x, y)
                m.scroll(event["dx"], event["dy"])

        if i < play_times - 1 and not stop_play_event.is_set():
            print(f"   Pause {play_delay}s...")
            end = time.perf_counter() + play_delay
            while time.perf_counter() < end:
                if stop_play_event.is_set():
                    break
                time.sleep(0.05)

    playing = False
    print("✔ Lecture terminée." if not stop_play_event.is_set() else "⏹ Lecture stoppée.")


# ──────────────────────────────────────────────
# HOTKEYS
# ──────────────────────────────────────────────

def on_key_press(key):
    global recording, playing, start_time, play_thread, stop_play_event, active_session

    if key == Key.f8:
        if recording:
            print("⚠ Déjà en enregistrement.")
        elif playing:
            print("⚠ Lecture en cours.")
        else:
            events.clear()
            recording = True
            start_time = time.perf_counter()
            print("⏺ Enregistrement démarré — F9 pour arrêter")

    elif key == Key.f9:
        if not recording:
            print("⚠ Pas d'enregistrement en cours.")
            return
        recording = False
        duration = events[-1]["t"] if events else 0
        # Demander le nom dans un thread pour ne pas bloquer le listener
        threading.Thread(target=ask_and_save, args=(duration,), daemon=True).start()

    elif key == Key.f10:
        if playing:
            print("⚠ Lecture déjà en cours.")
        elif recording:
            print("⚠ Arrête l'enregistrement (F9) d'abord.")
        elif not events:
            print("⚠ Aucun événement en mémoire. Enregistre ou charge une session.")
        else:
            playing = True
            stop_play_event.clear()
            play_thread = threading.Thread(target=play_loop, daemon=True)
            play_thread.start()
            label = f"'{active_session}'" if active_session else "session courante"
            print(f"▶ Lecture {label} ({play_times}x, délai {play_delay}s)")

    elif key == Key.esc:
        if playing:
            stop_play_event.set()

    elif key == Key.f12:
        print("\n👋 Au revoir.")
        quit_event.set()


def ask_and_save(duration):
    global active_session
    name = input(f"  Nom de la session ({len(events)} evt, {duration:.2f}s) : ").strip()
    if not name:
        name = f"session_{int(time.time())}"
    save_session(name)
    active_session = name
    print(f"✔ Session '{name}' sauvegardée → {session_path(name)}")


# ──────────────────────────────────────────────
# CLI MENU
# ──────────────────────────────────────────────

def print_help():
    print("\n=== Mouse Recorder ===")
    print("  F8    → Démarrer l'enregistrement")
    print("  F9    → Arrêter et sauvegarder")
    print("  F10   → Lancer la lecture")
    print("  Échap → Stopper la lecture")
    print("  F12   → Quitter")
    print("\nCommandes CLI (tape pendant que le script tourne) :")
    print("  list              — lister les sessions")
    print("  load <nom>        — charger une session")
    print("  times <n>         — répétitions (actuel: {play_times})")
    print("  delay <s>         — délai entre passes (actuel: {play_delay}s)")
    print("  skipmoves on/off  — ignorer les mouvements")
    print("  help              — afficher ce menu")
    print("─" * 40)

def cli_loop():
    global play_times, play_delay, play_skip_moves
    while not quit_event.is_set():
        try:
            cmd = input("").strip()
        except EOFError:
            break
        if not cmd:
            continue
        parts = cmd.split()
        c = parts[0].lower()

        if c == "list":
            list_sessions()
        elif c == "load" and len(parts) >= 2:
            load_session(parts[1])
        elif c == "times" and len(parts) >= 2:
            try:
                play_times = int(parts[1])
                print(f"  Répétitions : {play_times}")
            except ValueError:
                print("⚠ Valeur invalide.")
        elif c == "delay" and len(parts) >= 2:
            try:
                play_delay = float(parts[1])
                print(f"  Délai : {play_delay}s")
            except ValueError:
                print("⚠ Valeur invalide.")
        elif c == "skipmoves" and len(parts) >= 2:
            play_skip_moves = parts[1].lower() == "on"
            print(f"  Skip moves : {'on' if play_skip_moves else 'off'}")
        elif c == "help":
            print_help()
        else:
            print("⚠ Commande inconnue. Tape 'help'.")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    print_help()

    mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll, on_move=on_move)
    mouse_listener.start()

    kb_listener = keyboard.Listener(on_press=on_key_press)
    kb_listener.start()

    cli_thread = threading.Thread(target=cli_loop, daemon=True)
    cli_thread.start()

    quit_event.wait()
    kb_listener.stop()
    mouse_listener.stop()
    sys.exit(0)


if __name__ == "__main__":
    main()