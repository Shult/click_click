"""Accès Win32 regroupé : DPI, résolution du timer, écran virtuel, click-through.

Chaque fonction est tolérante à l'échec : sur une version de Windows qui ne
fournit pas l'API attendue, on retombe sur une valeur par défaut raisonnable
plutôt que de faire planter l'application.
"""

import ctypes
import logging
from contextlib import contextmanager
from ctypes import wintypes

log = logging.getLogger(__name__)

MONITOR_DEFAULTTONEAREST = 2


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SM_CMONITORS = 80

DEFAULT_DPI = 96

try:
    _user32 = ctypes.windll.user32
    _shcore = ctypes.windll.shcore
    _winmm = ctypes.windll.winmm
except (AttributeError, OSError):  # hors Windows : les tests restent importables
    _user32 = _shcore = _winmm = None


def enable_dpi_awareness() -> None:
    """Déclare le processus DPI-aware. À appeler avant toute création de fenêtre.

    Sans ça, sur un écran à 125 % ou 150 %, Windows virtualise les coordonnées
    rendues à l'application alors que les hooks d'entrée rapportent des pixels
    physiques : l'overlay est mal placé et les positions enregistrées ne
    correspondent pas à celles rejouées.
    """
    if _user32 is None:
        return
    # Per-monitor v2 (Windows 10 1703+), puis replis successifs.
    try:
        if _user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except AttributeError:
        pass
    try:
        _shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except (AttributeError, OSError):
        pass
    try:
        _user32.SetProcessDPIAware()
    except AttributeError:
        log.warning("no DPI API available, coordinates may be virtualized")


def system_dpi() -> int:
    if _user32 is None:
        return DEFAULT_DPI
    try:
        return int(_user32.GetDpiForSystem()) or DEFAULT_DPI
    except AttributeError:
        return DEFAULT_DPI


def virtual_screen() -> dict:
    """Rectangle englobant tous les écrans, en pixels physiques."""
    if _user32 is None:
        return {"x": 0, "y": 0, "w": 0, "h": 0, "monitors": 0}
    g = _user32.GetSystemMetrics
    return {
        "x": int(g(SM_XVIRTUALSCREEN)),
        "y": int(g(SM_YVIRTUALSCREEN)),
        "w": int(g(SM_CXVIRTUALSCREEN)),
        "h": int(g(SM_CYVIRTUALSCREEN)),
        "monitors": int(g(SM_CMONITORS)),
    }


def clamp_to_screen(x, y, vs: dict) -> tuple[int, int]:
    """Contraint un point au bureau virtuel.

    Empêche une session enregistrée sur une autre configuration d'écrans
    d'envoyer le curseur hors de portée.
    """
    if not vs or vs["w"] <= 0 or vs["h"] <= 0:
        return int(x), int(y)
    return (
        min(max(int(x), vs["x"]), vs["x"] + vs["w"] - 1),
        min(max(int(y), vs["y"]), vs["y"] + vs["h"] - 1),
    )


def monitor_rect(hwnd: int = 0) -> dict:
    """Zone de travail de l'écran qui porte `hwnd` (barre des tâches exclue).

    Distinct de `virtual_screen` : pour décider où poser une fenêtre, « tient
    dans le bureau » ne suffit pas, il faut « tient sur le même écran ». Sans
    cette distinction, une fenêtre posée au bord droit de l'écran principal
    déborde silencieusement sur l'écran voisin.
    """
    if _user32 is None:
        return virtual_screen()
    try:
        _user32.MonitorFromWindow.restype = ctypes.c_void_p
        _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        _user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p,
                                            ctypes.POINTER(MONITORINFO)]

        hmon = _user32.MonitorFromWindow(wintypes.HWND(hwnd),
                                         MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not _user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return virtual_screen()
        r = info.rcWork
        return {
            "x": int(r.left), "y": int(r.top),
            "w": int(r.right - r.left), "h": int(r.bottom - r.top),
            "monitors": 1,
        }
    except (AttributeError, OSError, ValueError):
        log.exception("window monitor not found, falling back to the desktop")
        return virtual_screen()


def clamp_rect(x: int, y: int, w: int, h: int, vs: dict) -> tuple[int, int]:
    """Ramène une fenêtre w×h entièrement dans le bureau virtuel.

    Renvoie le coin haut-gauche corrigé. Si la fenêtre est plus grande que le
    bureau, on privilégie son bord haut-gauche : mieux vaut déborder en bas à
    droite que rendre la barre de titre inatteignable.
    """
    if not vs or vs["w"] <= 0 or vs["h"] <= 0:
        return int(x), int(y)
    max_x = max(vs["x"], vs["x"] + vs["w"] - w)
    max_y = max(vs["y"], vs["y"] + vs["h"] - h)
    return (
        min(max(int(x), vs["x"]), max_x),
        min(max(int(y), vs["y"]), max_y),
    )


def set_click_through(hwnd: int, enable: bool) -> None:
    if _user32 is None:
        return
    try:
        style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = style | WS_EX_TRANSPARENT if enable else style & ~WS_EX_TRANSPARENT
        _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except OSError:
        log.exception("could not toggle click-through")


@contextmanager
def timer_resolution(ms: int = 1):
    """Relève la résolution du timer système le temps de la lecture.

    Par défaut `time.sleep` et les attentes de `threading.Event` ont un pas de
    ~15,6 ms sous Windows, largement au-dessus de la précision attendue pour
    rejouer des évènements espacés de quelques millisecondes.
    """
    raised = False
    if _winmm is not None:
        try:
            raised = _winmm.timeBeginPeriod(ms) == 0
        except (AttributeError, OSError):
            log.debug("timeBeginPeriod unavailable")
    try:
        yield
    finally:
        if raised:
            try:
                _winmm.timeEndPeriod(ms)
            except (AttributeError, OSError):
                pass
