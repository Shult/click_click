import time
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Controller as KeyboardController
from state import state
from recorder import data_to_key

_BTN = {"left": Button.left, "right": Button.right, "middle": Button.middle}


def play_loop():
    m  = MouseController()
    kb = KeyboardController()
    evts = (
        [e for e in state.events if e["type"] != "move"]
        if state.play_skip_moves else state.events
    )

    for i in range(state.play_times):
        if state.stop_play.is_set():
            break
        state.play_current = i + 1
        prev_t = 0.0

        for event in evts:
            if state.stop_play.is_set():
                break

            wait = event["t"] - prev_t
            if wait > 0:
                end = time.perf_counter() + wait
                while time.perf_counter() < end:
                    if state.stop_play.is_set():
                        break
                    time.sleep(0.005)
            prev_t = event["t"]

            etype = event["type"]
            if etype == "move":
                m.position = (int(event["x"]), int(event["y"]))
            elif etype == "click":
                m.position = (int(event["x"]), int(event["y"]))
                btn = _BTN.get(event["button"], Button.left)
                (m.press if event["pressed"] else m.release)(btn)
            elif etype == "scroll":
                m.position = (int(event["x"]), int(event["y"]))
                m.scroll(event["dx"], event["dy"])
            elif etype == "key":
                try:
                    key = data_to_key(event)
                    (kb.press if event["pressed"] else kb.release)(key)
                except Exception:
                    pass

        if i < state.play_times - 1 and not state.stop_play.is_set():
            end = time.perf_counter() + state.play_delay
            while time.perf_counter() < end:
                if state.stop_play.is_set():
                    break
                time.sleep(0.05)

    state.playing = False
    state.play_current = 0
