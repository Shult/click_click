import threading
from typing import Optional


class State:
    def __init__(self):
        self.events: list               = []
        self.recording: bool            = False
        self.playing: bool              = False
        self.start_time: Optional[float] = None
        self.last_move_t: float         = -1.0
        self.play_thread: Optional[threading.Thread] = None
        self.active_session: Optional[str] = None
        self.play_times: int   = 1
        self.play_delay: float = 1.0
        self.play_skip_moves: bool = False
        self.play_current: int  = 0
        self.app               = None  # OverlayApp, assigné au démarrage
        self.stop_play         = threading.Event()
        self.quit              = threading.Event()


state = State()
