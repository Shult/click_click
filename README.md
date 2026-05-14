# Mouse Recorder

Enregistre clics, scroll, mouvements souris et frappes clavier, puis les rejoue autant de fois que tu veux. Interface overlay toujours au premier plan, sessions nommées et persistées dans `./sessions/`.

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

### Réglages

| Paramètre | Description |
|-----------|-------------|
| Répétitions | Nombre de fois que la session est jouée |
| Délai (s) | Pause entre chaque passe |
| Skip moves | Ignore les déplacements souris à la lecture |

## Ce qui est enregistré

- Clics souris (gauche, droit, molette)
- Défilement (scroll)
- Déplacements souris
- Frappes clavier (touches maintenues, combos)
- Drag & drop

## Installation manuelle (optionnel)

Si tu préfères ne pas utiliser `lancer.bat` :

```powershell
# Installer uv si absent
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Installer les dépendances et lancer
uv sync
uv run python mouse_recorder.py
```
