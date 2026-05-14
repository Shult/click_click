import json
import os
from state import state

SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)


def session_path(name: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{name}.json")


def save_session(name: str) -> None:
    with open(session_path(name), "w") as f:
        json.dump(state.events, f, indent=2)


def load_session(name: str) -> bool:
    path = session_path(name)
    if not os.path.exists(path):
        return False
    with open(path) as f:
        state.events = json.load(f)
    state.active_session = name
    return True
