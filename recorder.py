import time
from pynput.keyboard import Key, KeyCode
from state import state

MOVE_INTERVAL = 1 / 60
HOTKEYS = {Key.f8, Key.f9, Key.f10, Key.f12, Key.esc}


def key_to_data(key) -> dict:
    if isinstance(key, Key):
        return {"key_type": "special", "key": key.name}
    if hasattr(key, "char") and key.char:
        return {"key_type": "char", "key": key.char}
    return {"key_type": "vk", "key": key.vk}


def data_to_key(data: dict):
    if data["key_type"] == "special":
        return Key[data["key"]]
    if data["key_type"] == "char":
        return KeyCode.from_char(data["key"])
    return KeyCode.from_vk(data["key"])


def ts() -> float:
    return time.perf_counter() - state.start_time


def on_click(x, y, button, pressed):
    if state.recording:
        state.events.append({
            "type": "click", "x": x, "y": y,
            "button": button.name, "pressed": pressed, "t": ts(),
        })


def on_scroll(x, y, dx, dy):
    if state.recording:
        state.events.append({
            "type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy, "t": ts(),
        })


def on_move(x, y):
    if state.recording:
        now = ts()
        if now - state.last_move_t >= MOVE_INTERVAL:
            state.events.append({"type": "move", "x": x, "y": y, "t": now})
            state.last_move_t = now


def on_key_record(key, pressed: bool):
    if state.recording and key not in HOTKEYS:
        state.events.append({
            "type": "key", "pressed": pressed, "t": ts(), **key_to_data(key),
        })
