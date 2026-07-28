"""Journalisation.

L'application est empaquetée en mode fenêtré (`console=False`) : sans journal,
toute exception est parfaitement invisible pour l'utilisateur. Tout ce qui
échoue doit laisser une trace sur disque.
"""

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

import paths

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)

    try:
        handler = RotatingFileHandler(
            paths.log_file(), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
    except OSError:
        pass  # disque plein ou dossier verrouillé : on continue sans journal

    if sys.stderr is not None:  # absent quand l'exe est lancé sans console
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(stream)

    _install_excepthooks()


def _install_excepthooks() -> None:
    """Capture aussi ce qui remonte hors des blocs try : threads compris.

    Les écouteurs pynput et le thread de lecture tournent en arrière-plan ;
    sans ces hooks leurs exceptions disparaissent silencieusement.
    """
    log = logging.getLogger("unhandled")

    def on_exception(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("unhandled exception", exc_info=(exc_type, exc, tb))

    def on_thread_exception(args):
        if issubclass(args.exc_type, SystemExit):
            return
        log.critical(
            "unhandled exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = on_exception
    threading.excepthook = on_thread_exception
