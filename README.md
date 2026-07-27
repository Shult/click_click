# ClickClick

Enregistre clics, scroll, mouvements souris et frappes clavier, puis les rejoue autant de fois que tu veux. Interface overlay toujours au premier plan, sessions nommées et persistées sur disque.

## Lancement rapide

Double-clique sur **`lancer.bat`** — il installe tout automatiquement à la première ouverture.

> Nécessite Windows 10/11. Aucune installation manuelle requise.

## Interface

L'overlay s'affiche en haut à droite de l'écran. Il reste visible par-dessus toutes les fenêtres.

Pendant la **lecture**, l'overlay devient transparent et les clics passent au travers — tu interagis normalement avec ton application.

| Bouton | Raccourci | Action |
|--------|-----------|--------|
| ⏺ | **F8** | Démarrer l'enregistrement |
| ⏹ | **F9** | Arrêter et sauvegarder |
| ▶ | **F10** | Lancer la lecture |
| — | **Échap** | Stopper la lecture |
| — | **F12** | Quitter |

Ces cinq touches sont réservées : elles ne sont jamais enregistrées dans une session.

### Réglages

| Paramètre | Description |
|-----------|-------------|
| Répétitions | Nombre de fois que la session est jouée. **Clique sur le nombre** pour le taper directement (Entrée valide, Échap annule) ; **∞** rejoue jusqu'à Échap |
| Délai (s) | Pause entre chaque passe |
| Skip moves | Ignore les déplacements souris à la lecture |

En mode infini, le statut affiche la passe en cours sur `∞` — `▶ PLAYING (37/∞)`. Une saisie qui n'est pas un entier ≥ 1 est refusée sans rien changer. Le nombre de passes est figé au lancement de la lecture : modifier le réglage en cours de route n'affecte que la lecture suivante.

Ces réglages, le tri de la liste des sessions et la position de l'overlay sont **conservés d'un lancement à l'autre** (`settings.json`). Un fichier absent, illisible ou incohérent est ignoré sans bruit : l'application repart sur ses valeurs par défaut.

## Ce qui est enregistré

- Clics souris (gauche, droit, molette)
- Défilement (scroll)
- Déplacements souris (échantillonnés à 60 Hz)
- Frappes clavier (touches maintenues, combos)
- Drag & drop

Arrêter l'enregistrement pendant un maintien de touche ou un drag referme automatiquement l'appui : une session est toujours équilibrée, et le replay ne peut pas laisser une touche enfoncée.

## Où sont les fichiers

Tout est stocké **à côté de l'exécutable** (ou du dossier source en développement), quel que soit le répertoire depuis lequel l'application est lancée :

```
ClickClick.exe
sessions/          ← une session par fichier .json
settings.json      ← réglages de lecture, tri, position de la fenêtre
clickclick.log     ← journal, rotatif (4 × 1 Mo)
```

Si ce dossier est en lecture seule, tout bascule vers `%LOCALAPPDATA%\ClickClick`. La variable d'environnement `CLICKCLICK_HOME` force un emplacement.

En cas de problème, le journal est le premier endroit à regarder : l'application est empaquetée sans console, donc rien ne s'affiche à l'écran.

## Format de session

```jsonc
{
  "version": 2,
  "app": "ClickClick",
  "created_at": "2026-07-27T12:34:56+00:00",
  "duration": 36.0,
  "event_count": 6126,
  "screen": { "x": -1080, "y": 0, "w": 4920, "h": 1920, "monitors": 3 },
  "events": [ { "type": "move", "x": 1696, "y": 610, "t": 0.117 }, ... ]
}
```

Les sessions **v1** (un tableau d'évènements nu, sans métadonnées) restent lisibles telles quelles ; elles sont réécrites en v2 à la prochaine sauvegarde.

Les coordonnées sont **absolues**. `screen` retient la géométrie du bureau au moment de l'enregistrement : si elle diffère au chargement, l'overlay affiche `⚠ (écran différent)` et le replay sera décalé. Les positions rejouées sont contraintes au bureau virtuel courant.

À l'écriture, les déplacements qui répètent la position précédente sont supprimés et les horodatages arrondis à la milliseconde — sans perte pour le replay, pour environ deux tiers de taille en moins.

## Développement

```powershell
uv sync
uv run python mouse_recorder.py
uv run pytest
```

| Module | Rôle |
|--------|------|
| `mouse_recorder.py` | Point d'entrée, raccourcis globaux |
| `overlay.py` | Interface Tkinter |
| `recorder.py` | Capture des évènements |
| `player.py` | Replay et relâchement de sécurité |
| `sessions.py` | Sérialisation, compression, compatibilité v1 |
| `settings.py` | Préférences persistées |
| `paths.py` | Résolution des emplacements de fichiers |
| `winapi.py` | DPI, timer, géométrie des écrans, click-through |
| `logs.py` | Journalisation et capture des exceptions |

### Construire l'exécutable

```powershell
uv run pyinstaller ClickClick.spec
```

> L'exécutable n'est pas signé et pose un hook clavier global : Windows SmartScreen et la plupart des antivirus le signaleront. UPX est désactivé dans le `.spec` pour limiter les faux positifs, mais seule une signature de code règle vraiment le problème.
