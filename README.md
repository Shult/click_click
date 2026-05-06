# Mouse Recorder

Enregistre clics, scroll et mouvements souris globaux et les rejoue n fois. Les sessions sont nommées et persistées dans `./sessions/`.

## Installation

```powershell
uv venv
uv pip install pynput
```

## Lancement

```powershell
python mouse_recorder.py
```

## Raccourcis clavier

| Touche | Action |
|---|---|
| **F8** | Démarrer l'enregistrement |
| **F9** | Arrêter et sauvegarder (demande un nom) |
| **F10** | Lancer la lecture de la session active |
| **Échap** | Stopper la lecture en cours |
| **F12** | Quitter le programme |

## Commandes CLI

Tape directement dans le terminal pendant que le script tourne.

| Commande | Description |
|---|---|
| `list` | Lister les sessions enregistrées |
| `load <nom>` | Charger une session en mémoire |
| `times <n>` | Nombre de répétitions |
| `delay <s>` | Délai entre chaque passe |
| `skipmoves on/off` | Ignorer les mouvements à la lecture |
| `help` | Afficher l'aide |

## Exemple de workflow

```
> list
  craft_potion              512 evt    23.40s
  farm_route                128 evt     8.10s

> load craft_potion
✔ Session 'craft_potion' chargée

> times 10
  Répétitions : 10

[F10] → Lance la lecture 10x
[Échap] → Stop si besoin
```