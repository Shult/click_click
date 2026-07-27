import queue
import threading
from typing import Optional


class State:
    def __init__(self):
        self.events: list                = []
        self.recording: bool             = False
        self.playing: bool               = False
        self.start_time: float           = 0.0
        self.last_move_t: float          = -1.0
        self.last_pos: tuple             = (0, 0)
        self.play_thread: Optional[threading.Thread] = None
        self.active_session: Optional[str] = None
        self.play_times: int             = 1
        self.play_delay: float           = 1.0
        self.play_skip_moves: bool       = False
        self.play_current: int           = 0

        # Préférences d'interface, relues au démarrage (voir settings.py).
        self.sort_by_date: bool          = True
        self.window_pos: Optional[tuple] = None
        self.app                         = None  # OverlayApp, assigné au démarrage
        self.stop_play                   = threading.Event()
        self.quit                        = threading.Event()

        # Appuis en cours pendant l'enregistrement, pour pouvoir clore une
        # session interrompue au milieu d'un maintien de touche ou d'un drag.
        self.held_keys: dict             = {}
        self.held_buttons: dict          = {}

        # Écran sur lequel la session chargée a été enregistrée, et écart
        # constaté avec la configuration actuelle.
        self.session_screen: Optional[dict] = None
        self.screen_mismatch: bool       = False

        # Les écouteurs pynput tournent hors du thread Tk : ils déposent ici
        # les actions à exécuter dans la boucle graphique.
        self.ui_queue: queue.Queue       = queue.Queue()

        # Vrai tant qu'une boîte de dialogue attend une saisie : les raccourcis
        # globaux sont alors neutralisés.
        self.modal_open: bool            = False


state = State()
