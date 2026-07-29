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
| ▶ | **F10** | Lancer la lecture (la session chargée, ou la file d'enchaînement) |
| — | **F11** | Masquer / réafficher l'overlay |
| · | **Échap** | Stopper la lecture |
| × | **F12** | Quitter |

Ces six touches sont réservées : elles ne sont jamais enregistrées dans une session.

### Masquer l'overlay

**F11**, ou le bouton `—` de l'en-tête, escamote l'overlay sans rien arrêter : les raccourcis restent actifs, un enregistrement ou une lecture en cours continue. F11 le fait revenir, au même endroit et toujours au premier plan. Arrêter un enregistrement (F9) le réaffiche de lui-même, pour que la fenêtre de sauvegarde ne flotte pas sans contexte.

L'état masqué **n'est pas conservé** au redémarrage : une application qui se lance invisible ressemble à une application qui ne s'est pas lancée.

> Il n'y a pas (encore) d'icône dans la zone de notification : elle imposerait soit `pystray` + `Pillow`, soit une implémentation `Shell_NotifyIcon` maison dans `winapi.py`. F11 rend le même service sans peser sur la taille de l'exécutable.

### Sessions

Le panneau **📂 Sessions** liste tout ce qui est enregistré sur disque, dans une liste défilable — plus de plafond à dix entrées. Le champ en haut à droite **filtre par nom** (casse ignorée, Échap vide le filtre) ; le compteur sous la liste indique combien de sessions correspondent.

Un **clic** désigne une session, un **double-clic** la charge. Les quatre boutons agissent sur la session désignée :

| Bouton | Effet |
|--------|-------|
| Charger | Charge la session (comme le double-clic) |
| Renommer | Le nom est validé comme à la sauvegarde ; un nom déjà pris est refusé |
| Dupliquer | Copie sous le premier nom libre `nom (2)`, `nom (3)`… métadonnées d'origine conservées |
| Supprimer | **Irréversible** : demande confirmation, efface le fichier sans passer par la corbeille |

La session active apparaît en vert. Si tu la renommes, elle reste active sous son nouveau nom ; si tu la supprimes, l'en-tête revient à `—` mais les évènements déjà chargés restent en mémoire — une lecture en cours n'est pas interrompue et F10 fonctionne toujours.

### File d'enchaînement

Pour jouer plusieurs sessions à la suite, ajoute-les à la **file** en bas du panneau Sessions. `＋ Ajouter la session sélectionnée` l'empile à la fin ; `↑` `↓` la déplacent, `Retirer` l'enlève, `Vider` remet la file à zéro (avec confirmation). Une même session peut y figurer plusieurs fois.

**Dès que la file contient une entrée, elle prend le pas sur la session chargée** : F10 joue la file, dans l'ordre, et l'en-tête de l'overlay affiche `⛓ file : N session(s)` pour que ce soit visible sans ouvrir le panneau. Pour rejouer une session seule, vide la file.

Pendant la lecture, l'en-tête indique la session en cours et sa position : `alma 03 (2/14)`. Les répétitions s'appliquent à **l'enchaînement entier** : 3 répétitions d'une file de 4 sessions, c'est douze lectures. Le délai sert de pause entre deux sessions comme entre deux passes.

La file est **conservée** dans `settings.json` sous forme de liste de noms, et suit les renommages et les suppressions faites depuis l'application. Une entrée dont le fichier a disparu autrement (effacé depuis l'explorateur) apparaît **en rouge** dans la liste et est simplement sautée à la lecture — le reste de l'enchaînement se joue quand même.

Chaque session rend la souris et le clavier avant la suivante : une session mal équilibrée ne peut pas laisser une touche enfoncée pour tout le reste de la file.

### Réglages

| Paramètre | Description |
|-----------|-------------|
| Répétitions | Nombre de fois que la session est jouée. **Clique sur le nombre** pour le taper directement (Entrée valide, Échap annule) ; **∞** rejoue jusqu'à Échap |
| Délai (s) | Pause entre chaque passe, et entre deux sessions d'une file |
| Vitesse | Tempo de la lecture, de **0.25×** à **4×** par paliers (0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4) |
| Skip moves | Ignore les déplacements souris à la lecture |
| Langue | Langue de l'interface — voir ci-dessous |

En mode infini, le statut affiche la passe en cours sur `∞` — `▶ PLAYING (37/∞)`. Une saisie qui n'est pas un entier ≥ 1 est refusée sans rien changer. Le nombre de passes est figé au lancement de la lecture : modifier le réglage en cours de route n'affecte que la lecture suivante.

La vitesse divise les horodatages enregistrés : à 2× une session de 30 s en prend 15. Elle ne s'applique **pas** au délai, qui est une pause voulue et non du rythme enregistré. Comme les répétitions, elle est figée au lancement de la lecture.

> Au-delà de 2×, l'application pilotée peut ne plus suivre : un menu qui met 200 ms à s'ouvrir ne s'ouvrira pas plus vite parce que le clic suivant arrive plus tôt. Une session qui échoue à 4× n'est pas forcément mal enregistrée.

### Langue

L'interface est en **anglais par défaut**. Le bouton `Language` du panneau Réglages fait défiler les langues disponibles — actuellement **English** et **Français** — et l'overlay se redessine immédiatement dans la nouvelle langue, panneau ouvert compris. Le choix est conservé dans `settings.json`.

Chaque langue est affichée dans sa propre langue (`Français`, jamais `French`) : c'est le seul libellé qui doive rester lisible pour quelqu'un qui ne comprend pas l'interface qu'il a sous les yeux.

Le journal, lui, est **en anglais** en toutes circonstances : il n'est pas traduit et ne suit pas ce réglage. Une trace se recoupe d'un poste à l'autre, se colle dans une issue et se cherche sur le web — trois choses qu'une traduction complique. Les commentaires du code restent en français.

> Pour ajouter une langue : un dictionnaire de plus dans `i18n.py`, déclaré dans `LANGUAGES`. Un test vérifie qu'aucune clé ne manque — une langue incomplète afficherait de l'anglais au milieu du reste. À défaut, toute clé absente retombe sur l'anglais plutôt que de faire tomber la fenêtre.

### Persistance

Ces réglages, la langue, la file d'enchaînement, le tri de la liste des sessions et la position de l'overlay sont **conservés d'un lancement à l'autre** (`settings.json`). Un fichier absent, illisible ou incohérent est ignoré sans bruit : l'application repart sur ses valeurs par défaut, clé par clé — un `settings.json` écrit par une version antérieure se charge donc sans rien perdre du reste.

```jsonc
{
  "play_times": 0,              // 0 = infini, sinon 1 à 9999
  "play_delay": 3.0,
  "play_speed": 1.5,            // 0.25 à 4
  "play_skip_moves": false,
  "playlist": ["connexion", "routine", "deconnexion"],
  "sort_by_date": true,
  "window_pos": [1670, 20],
  "language": "fr",          // "en" par défaut
  "update_check": true       // vérification des mises à jour au démarrage
}
```

Le fichier se modifie à la main sans risque : chaque valeur douteuse retombe sur son défaut, et un nom de `playlist` qui n'est pas un nom de session valide est écarté.

## Mise à jour

Au démarrage, l'exécutable compare sa version à la [dernière release GitHub](https://github.com/Shult/click_click/releases/latest). S'il existe plus récent, un badge **`⬆ version`** apparaît dans l'en-tête, à côté du numéro de version. Rien ne s'installe tout seul : cliquer sur le badge propose de télécharger et redémarrer, et c'est tout.

À l'installation, l'ancien exécutable est renommé `ClickClick.old.exe` le temps du remplacement, puis effacé au lancement suivant. Sessions, réglages et journal ne bougent pas. En cas d'échec (réseau coupé, téléchargement corrompu), le badge affiche `⚠`, l'application continue avec la version en place, et le détail est dans le journal — un nouveau clic réessaie.

- La vérification est **silencieuse et non bloquante** : hors ligne, l'application démarre comme si de rien n'était.
- Elle ne s'exécute que depuis l'exécutable empaqueté, jamais en développement.
- Pour la couper : `"update_check": false` dans `settings.json`. Aucune autre donnée n'est envoyée — c'est une requête anonyme vers l'API GitHub.
- Le badge est inerte pendant un enregistrement ou une lecture : l'installation redémarre l'application, elle n'interrompra pas une routine en cours.

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
settings.json      ← réglages de lecture, file d'enchaînement, tri, position
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
| `updater.py` | Vérification et installation des mises à jour |
| `i18n.py` | Textes de l'interface, une langue par dictionnaire |
| `paths.py` | Résolution des emplacements de fichiers |
| `winapi.py` | DPI, timer, géométrie des écrans, click-through |
| `logs.py` | Journalisation et capture des exceptions |

### Construire l'exécutable

```powershell
uv run pyinstaller ClickClick.spec
```

> L'exécutable n'est pas signé et pose un hook clavier global : Windows SmartScreen et la plupart des antivirus le signaleront. UPX est désactivé dans le `.spec` pour limiter les faux positifs, mais seule une signature de code règle vraiment le problème. Les mises à jour installées par l'application elle-même ne repassent pas par SmartScreen : un fichier téléchargé par un programme ne porte pas la marque du web.

## Licence

[MIT](LICENSE).
