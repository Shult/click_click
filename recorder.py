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


def start() -> None:
    """Amorce une session.

    `start_time` est posé avant `recording` : dans l'ordre inverse, un
    évènement souris arrivant entre les deux affectations horodaterait avec
    la borne de l'enregistrement précédent.
    """
    state.events.clear()
    state.held_keys.clear()
    state.held_buttons.clear()
    state.last_move_t = -1.0
    state.start_time = time.perf_counter()
    state.recording = True


def stop() -> None:
    """Arrête l'enregistrement et referme les appuis restés ouverts.

    Une session doit être équilibrée : sans relâchement correspondant, le
    replay laisse la touche ou le bouton enfoncé au niveau du système.
    """
    state.recording = False
    t = ts()
    x, y = state.last_pos

    for data in state.held_keys.values():
        state.events.append({"type": "key", "pressed": False, "t": t, **data})
    state.held_keys.clear()

    for name in state.held_buttons:
        state.events.append({
            "type": "click", "x": x, "y": y,
            "button": name, "pressed": False, "t": t,
        })
    state.held_buttons.clear()


def on_click(x, y, button, pressed):
    if not state.recording:
        return
    state.last_pos = (x, y)
    state.events.append({
        "type": "click", "x": x, "y": y,
        "button": button.name, "pressed": pressed, "t": ts(),
    })
    if pressed:
        state.held_buttons[button.name] = True
    else:
        state.held_buttons.pop(button.name, None)


def on_scroll(x, y, dx, dy):
    if state.recording:
        state.last_pos = (x, y)
        state.events.append({
            "type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy, "t": ts(),
        })


def on_move(x, y):
    if not state.recording:
        return
    state.last_pos = (x, y)
    now = ts()
    if now - state.last_move_t >= MOVE_INTERVAL:
        state.events.append({"type": "move", "x": x, "y": y, "t": now})
        state.last_move_t = now


def on_key_record(key, pressed: bool):
    if not state.recording or key in HOTKEYS:
        return
    data = key_to_data(key)
    state.events.append({"type": "key", "pressed": pressed, "t": ts(), **data})
    ident = (data["key_type"], data["key"])
    if pressed:
        state.held_keys[ident] = data
    else:
        state.held_keys.pop(ident, None)
