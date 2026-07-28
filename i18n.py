"""Textes de l'interface, dans la langue choisie.

Un dictionnaire par langue, en dur dans ce module : pas de `gettext`, pas de
fichiers `.po` à compiler. L'application est empaquetée par PyInstaller en un
seul exécutable, et des catalogues externes seraient des données à embarquer,
donc à retrouver au démarrage — pour une poignée de chaînes, le rapport n'y est
pas. Un module Python suit l'exécutable tout seul.

L'anglais est la langue de référence : c'est le défaut au premier lancement, et
c'est sur lui que retombe toute clé qu'une traduction n'a pas encore.

Les messages du journal ne passent pas par ici : ils sont écrits en anglais,
en dur, quelle que soit la langue de l'interface. C'est la convention du
métier, et une trace se recoupe d'un poste à l'autre, se colle dans une issue
et se cherche sur le web — trois choses qu'une traduction complique. Les
commentaires du code, eux, restent en français comme le reste du dépôt.

Quand un message de journal doit citer du texte d'interface — un titre de
boîte de dialogue, par exemple —, celui-ci part en **donnée** du message
(`log.exception("dialog action failed (%r)", title)`), jamais dans la phrase.
"""

import logging

log = logging.getLogger(__name__)

DEFAULT = "en"

# Nom de chaque langue dans cette langue : c'est ce que lit quelqu'un qui ne
# comprend pas la langue affichée et cherche à en sortir.
LANGUAGES = {
    "en": "English",
    "fr": "Français",
}

_CATALOG = {
    "en": {
        # ── Overlay ──────────────────────────────────────────────────────────
        "status.idle": "⏸  IDLE",
        "status.recording": "⏺  REC",
        "status.playing": "▶  PLAYING  ({current}/{total})",
        "header.queue": "⛓ queue: {count} session(s)",
        "header.screen_mismatch": "⚠ {name}  (different screen)",
        "panel.sessions": "📂 Sessions",
        "panel.settings": "⚙ Settings",

        # ── Réglages ─────────────────────────────────────────────────────────
        "settings.times": "Repeats",
        "settings.delay": "Delay (s)",
        "settings.speed": "Speed",
        "settings.skip_moves": "Skip moves",
        "settings.language": "Language",

        # ── Panneau Sessions ─────────────────────────────────────────────────
        "sessions.sort_date": "Sort: date",
        "sessions.sort_name": "Sort: A-Z",
        "sessions.load": "Load",
        "sessions.rename": "Rename",
        "sessions.duplicate": "Duplicate",
        "sessions.delete": "Delete",
        "sessions.none": "No session",
        "sessions.no_match": "No name contains “{query}”",
        "sessions.count": "{shown} / {total} session(s)",
        "sessions.select_first": "Select a session first",
        "sessions.duplicated": "Copied as “{name}”",
        "sessions.deleted": "“{name}” deleted",

        # ── File d'enchaînement ──────────────────────────────────────────────
        "queue.title": "⛓ Play queue",
        "queue.add": "＋ Add the selected session",
        "queue.remove": "Remove",
        "queue.clear": "Clear",
        "queue.select_first": "Select a queue entry first",
        "queue.full": "Queue full ({max})",
        "queue.added": "“{name}” added at position {position}",
        "queue.removed": "“{name}” removed from the queue",
        "queue.cleared": "Queue cleared",
        "queue.clear_title": "Clear the queue",
        "queue.clear_message": ("Remove the {count} entries from the queue?\n"
                                "The sessions themselves are left untouched."),

        # ── Boîtes de dialogue ───────────────────────────────────────────────
        "dialog.save_title": "Save session",
        "dialog.save_summary": "{count} evts  •  {duration:.2f}s",
        "dialog.save": "Save",
        "dialog.rename_title": "Rename session",
        "dialog.confirm": "Confirm",
        "dialog.cancel": "Cancel",
        "dialog.delete_title": "Delete session",
        "dialog.delete_message": ("Permanently delete “{name}”?\n"
                                  "The file is erased, with no recycle bin."),
        "dialog.unexpected_error": "Unexpected error, see the log",

        # ── Erreurs de session ───────────────────────────────────────────────
        "error.name_empty": "Empty name",
        "error.name_too_long": "Name too long ({max} characters max)",
        "error.name_invalid": 'Forbidden characters: < > : " / \\ | ? *',
        "error.name_reserved": "“{name}” is a name reserved by Windows",
        "error.name_taken": "“{name}” already exists",
        "error.too_many_copies": "Too many copies of this session",
        "error.unknown_format": "Unrecognised session format",
        "error.session_missing": "Session “{name}” not found",
        "error.unreadable_file": "Unreadable file (line {line})",
        "error.write_failed": "Cannot write: {reason}",
        "error.read_failed": "Cannot read: {reason}",
        "error.rename_failed": "Cannot rename: {reason}",
        "error.delete_failed": "Cannot delete: {reason}",
        "error.copy_failed": "Cannot copy: {reason}",
    },
    "fr": {
        # ── Overlay ──────────────────────────────────────────────────────────
        "status.idle": "⏸  EN ATTENTE",
        "status.recording": "⏺  REC",
        "status.playing": "▶  LECTURE  ({current}/{total})",
        "header.queue": "⛓ file : {count} session(s)",
        "header.screen_mismatch": "⚠ {name}  (écran différent)",
        "panel.sessions": "📂 Sessions",
        "panel.settings": "⚙ Réglages",

        # ── Réglages ─────────────────────────────────────────────────────────
        "settings.times": "Répétitions",
        "settings.delay": "Délai (s)",
        "settings.speed": "Vitesse",
        "settings.skip_moves": "Skip moves",
        "settings.language": "Langue",

        # ── Panneau Sessions ─────────────────────────────────────────────────
        "sessions.sort_date": "Tri : date",
        "sessions.sort_name": "Tri : A-Z",
        "sessions.load": "Charger",
        "sessions.rename": "Renommer",
        "sessions.duplicate": "Dupliquer",
        "sessions.delete": "Supprimer",
        "sessions.none": "Aucune session",
        "sessions.no_match": "Aucun nom ne contient « {query} »",
        "sessions.count": "{shown} / {total} session(s)",
        "sessions.select_first": "Sélectionne d'abord une session",
        "sessions.duplicated": "Copiée en « {name} »",
        "sessions.deleted": "« {name} » supprimée",

        # ── File d'enchaînement ──────────────────────────────────────────────
        "queue.title": "⛓ File d'enchaînement",
        "queue.add": "＋ Ajouter la session sélectionnée",
        "queue.remove": "Retirer",
        "queue.clear": "Vider",
        "queue.select_first": "Sélectionne d'abord une entrée de la file",
        "queue.full": "File pleine ({max})",
        "queue.added": "« {name} » ajoutée en position {position}",
        "queue.removed": "« {name} » retirée de la file",
        "queue.cleared": "File vidée",
        "queue.clear_title": "Vider la file",
        "queue.clear_message": ("Retirer les {count} entrées de la file ?\n"
                                "Les sessions elles-mêmes ne sont pas touchées."),

        # ── Boîtes de dialogue ───────────────────────────────────────────────
        "dialog.save_title": "Sauvegarder la session",
        "dialog.save_summary": "{count} évts  •  {duration:.2f}s",
        "dialog.save": "Enregistrer",
        "dialog.rename_title": "Renommer la session",
        "dialog.confirm": "Valider",
        "dialog.cancel": "Annuler",
        "dialog.delete_title": "Supprimer la session",
        "dialog.delete_message": ("Supprimer définitivement « {name} » ?\n"
                                  "Le fichier est effacé, sans corbeille."),
        "dialog.unexpected_error": "Erreur inattendue, voir le journal",

        # ── Erreurs de session ───────────────────────────────────────────────
        "error.name_empty": "Nom vide",
        "error.name_too_long": "Nom trop long ({max} caractères max)",
        "error.name_invalid": 'Caractères interdits : < > : " / \\ | ? *',
        "error.name_reserved": "« {name} » est un nom réservé par Windows",
        "error.name_taken": "« {name} » existe déjà",
        "error.too_many_copies": "Trop de copies de cette session",
        "error.unknown_format": "Format de session non reconnu",
        "error.session_missing": "Session « {name} » introuvable",
        "error.unreadable_file": "Fichier illisible (ligne {line})",
        "error.write_failed": "Écriture impossible : {reason}",
        "error.read_failed": "Lecture impossible : {reason}",
        "error.rename_failed": "Renommage impossible : {reason}",
        "error.delete_failed": "Suppression impossible : {reason}",
        "error.copy_failed": "Copie impossible : {reason}",
    },
}

_lang = DEFAULT


# ── Langue courante ──────────────────────────────────────────────────────────

def language() -> str:
    return _lang


def set_language(code) -> str:
    """Choisit la langue et renvoie celle qui a été retenue.

    Un code inconnu — settings.json retouché à la main, langue retirée d'une
    version à l'autre — repart sur le défaut plutôt que de laisser l'interface
    afficher des clés brutes.
    """
    global _lang
    # Le test de type d'abord : une liste ou un dictionnaire n'est pas hachable
    # et ferait lever `in` au lieu de simplement ne pas correspondre.
    if not isinstance(code, str) or code not in LANGUAGES:
        if code is not None:
            log.warning("unknown language %r, falling back to %s", code, DEFAULT)
        code = DEFAULT
    _lang = code
    return _lang


def language_name(code: str | None = None) -> str:
    return LANGUAGES.get(code or _lang, LANGUAGES[DEFAULT])


def next_language() -> str:
    """Langue suivante dans l'ordre de `LANGUAGES`, en boucle.

    Deux langues font un simple va-et-vient ; au-delà, le bouton reste un
    bouton, sans menu déroulant à poser dans un panneau de 220 px.
    """
    codes = list(LANGUAGES)
    return codes[(codes.index(_lang) + 1) % len(codes)]


# ── Traduction ───────────────────────────────────────────────────────────────

def t(key: str, **params) -> str:
    """Texte associé à `key`, paramètres substitués.

    Ne lève jamais : un libellé manquant doit se voir dans l'interface, pas
    faire tomber la fenêtre qui le porte. À défaut de traduction, la clé
    elle-même est affichée — c'est laid, mais c'est diagnosticable.
    """
    text = _CATALOG.get(_lang, {}).get(key)
    if text is None:
        text = _CATALOG[DEFAULT].get(key)
        if text is None:
            log.warning("no text for key %r", key)
            return key
        log.warning("key %r missing from language %r", key, _lang)

    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        log.exception("unexpected parameters for key %r", key)
        return text
