# Deauville Festival du Rire — plateforme de programmation

Une plateforme Python pour la programmation du Festival du Rire de Deauville
(du 10 au 13 juin 2027) : artistes, salles et trois types de représentations
(solo, plateau, atelier), avec les règles de planning qu'un CMS générique ne
sait pas faire respecter.

Elle fournit :

- un **modèle** qui refuse toute modification enfreignant une règle ;
- une **ligne de commande** (programme d'une journée, artistes, ce qui se joue en ce moment) ;
- une **API web** (FastAPI) qui sert le site public sur `/` et l'administration sur `/admin/` ;
- deux **stockages** interchangeables : un fichier JSON (par défaut) et une base SQLite (SQLModel).

## Les règles du festival

Le modèle fait respecter ces règles, quel que soit le point d'entrée (CLI, API, tests) :

- le festival dure du 10 au 13 juin 2027, et une journée de festival se termine à 06:00 ;
- une salle ne peut accueillir qu'une représentation à la fois, avec 30 minutes d'écart minimum entre deux représentations ;
- un artiste ne peut pas être sur scène dans deux représentations à moins de 30 minutes d'écart, quel que soit son rôle ;
- une représentation dure de 1 à 360 minutes ;
- un solo a un âge minimum de 0 à 18 ans ;
- un plateau compte au moins 2 numéros distincts, l'animateur n'est pas l'un des numéros, et la durée minimale est de `n×10 + (n−1)×3` minutes ;
- un atelier a un nombre de places limité, et ses participants sont uniques sans tenir compte de la casse ;
- un nom d'artiste ou de salle est non vide, et une salle compte au moins 1 place.

## Installer, lancer, tester

Nécessite Python 3.12+ et [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                   # installe tout

uv run deauville programme 2027-06-11     # programme d'une journée de festival
uv run deauville artists                  # artistes avec leur nombre de spectacles
uv run deauville now --at 2027-06-11T21:30  # en scène + les 3 suivants (défaut : maintenant)
uv run deauville serve                    # http://127.0.0.1:8000/  (admin : /admin/, docs : /docs)

uv run pytest                             # les tests
uv run ruff check . && uv run ruff format --check .
uv build                                  # wheel + sdist dans dist/
```

`uv run python -m deauville <commande>` fonctionne aussi. Le fichier de données
par défaut est `data/festival.json` ; utilise `--data` pour en choisir un autre.
L'extension décide du stockage : `.db`, `.sqlite` ou `.sqlite3` donne SQLite,
tout le reste donne JSON.

```bash
uv run deauville convert data/festival.db            # copie le JSON dans SQLite
uv run deauville --data data/festival.db serve       # sert depuis SQLite
DEAUVILLE_DATA=data/festival.db uv run uvicorn --factory deauville.api:create_app
```

## Utiliser l'API

Le contrat complet des routes (objets, champs, codes d'erreur) est décrit dans
[`API.md`](API.md). Un exemple, avec le serveur lancé :

```bash
curl "http://127.0.0.1:8000/api/now?at=2027-06-11T21:30"
```

La réponse contient `now_playing` (ce qui est en scène) et `up_next` (les 3
prochains spectacles au maximum). La documentation interactive est disponible
sur `/docs`.

## Structure et pourquoi

```
src/deauville/               le paquet (src layout : les tests utilisent le paquet installé)
  __init__.py                ce que propose `import deauville`
  __main__.py                `python -m deauville`
  exceptions.py              les erreurs (une classe par type de règle enfreinte)
  utils.py                   noms, slugs, entiers, dates, jour de festival (sans état)
  venue.py                   Venue
  artist.py                  Artist
  performance.py             Performance (abstraite), Solo, Lineup, Workshop
  festival.py                Festival : la seule porte pour modifier le programme
  storage/
    base.py                  Storage (contrat abstrait)
    json_storage.py          JsonStorage
    sqlite_storage.py        SqliteStorage (SQLModel)
    factory.py               open_storage() : choisit selon l'extension du fichier
  cli.py                     la ligne de commande
  api.py                     l'application FastAPI
tests/                       pytest, un fichier par sujet
data/festival.json           les données
web/public/, web/admin/      le site public et l'administration
API.md                       le contrat de l'API
b1/                          premiers scripts (bloc B1 du projet), conservés pour l'historique
```

**Quels objets, et que sait / vérifie chacun ?**
`Venue` et `Artist` vérifient leurs propres valeurs (nom non vide et sans
espaces superflus, places ≥ 1) et calculent leur slug. Une représentation
vérifie tout ce qui ne dépend que d'elle : durée de 1 à 360, règles propres à
son type (âge de 0 à 18 ; au moins 2 numéros distincts, animateur qui n'est pas
un numéro, durée minimale `n×10 + (n−1)×3` ; places d'un atelier et
participants uniques sans tenir compte de la casse). Comme les constructeurs
vérifient, un objet invalide ne peut pas exister, quelle que soit la personne
qui le construit. Les attributs sont privés, avec des propriétés en lecture
seule.

**Que partagent les trois types, et qu'est-ce qui change ?**
`Performance` est une classe abstraite qui porte ce qui est commun : titre,
salle, début, durée, description, `end`, `id`, `festival_day`,
`is_too_close()`. Chaque sous-classe fournit ce qui change : qui est en scène
(`artist_slugs`), la capacité, un résumé d'une ligne, ses champs sauvegardés et,
au besoin, une vérification de la salle (`check_venue`, utilisée par l'atelier).
Ajouter un quatrième type revient à écrire une sous-classe ; elle s'enregistre
toute seule grâce à son `kind`, donc le chargement n'a pas à changer.

**Où vit une règle pour que personne ne puisse la contourner ?**
Les règles qui concernent un seul objet vivent dans cet objet. Les règles qui
en concernent plusieurs (les références existent, le jour du festival, 30
minutes pour une salle, 30 minutes pour un artiste dans n'importe quel rôle)
vivent dans `Festival`, qui est le seul moyen d'ajouter, remplacer, supprimer
ou enregistrer : il n'existe aucune liste publique où ajouter directement. La
CLI, l'API et les tests passent tous par lui. Chaque modification est tout ou
rien (`_change()` restaure l'état précédent si une règle est enfreinte **ou**
si la sauvegarde échoue), et le festival se sauvegarde lui-même après chaque
modification réussie.

**Comment l'appelant sait-il quelle règle a été enfreinte ?**
Chaque règle lève sa propre sous-classe de `FestivalError`, avec une phrase
qu'un organisateur comprend. Les erreurs de conflit (`VenueBusyError`,
`ArtistBusyError`, `OutsideFestivalError`, `WorkshopFullError`,
`AlreadyExistsError`) dérivent toutes de `ConflictError` ; les autres sont
`NotFoundError`, `InvalidValueError` et `StorageError`. Le modèle ne sait rien
de HTTP : `api.py` associe `NotFoundError` → 404, `ConflictError` → 409,
`InvalidValueError` → 422, et tout le reste → 500. La CLI affiche la phrase et
quitte avec le code 1. L'API ne vérifie que la *forme* d'une requête
(pydantic) ; les règles restent dans le modèle.

**Si les données passaient du JSON à une base, quels fichiers changeraient ?**
Seulement un nouveau fichier de stockage. `Storage` est le contrat (`load()`,
`save()`) ; le festival ne connaît que ce contrat. Cela a été fait pour de
vrai : `storage/sqlite_storage.py` constitue tout le support SQLite, plus deux
lignes qui le choisissent dans `open_storage()`. Le modèle, la CLI et l'API
n'ont pas changé. `load()` reconstruit le festival par ses méthodes publiques,
donc toutes les règles sont revérifiées pour les deux stockages, et un fichier
ou une ligne cassés donnent une phrase `StorageError`, pas une trace d'erreur.

Autres choix : le JSON est écrit dans un fichier temporaire puis renommé, donc
un échec ne laisse jamais un fichier à moitié écrit. Dans l'API, un verrou sert
une requête à la fois, car le festival vit en mémoire et les routes tournent
dans des threads.

## Ce qui est fait

**Le modèle et ses règles**

- Les trois types de représentations (`Solo`, `Lineup`, `Workshop`) sont des sous-classes d'une classe abstraite `Performance`. Chacune vérifie ses propres règles : âge de 0 à 18, au moins 2 numéros distincts avec durée minimale `n×10 + (n−1)×3`, places et participants uniques d'un atelier.
- Les règles qui concernent plusieurs objets sont dans `Festival` : références existantes, jour de festival, 30 minutes d'écart pour une salle, 30 minutes pour un artiste quel que soit son rôle.
- Chaque modification est tout ou rien : en cas de règle enfreinte ou d'échec de sauvegarde, l'état précédent est restauré.
- Chaque règle enfreinte lève sa propre erreur, avec une phrase lisible par un organisateur.

**Les stockages**

- Stockage JSON (par défaut), écrit via un fichier temporaire puis renommé, donc jamais de fichier à moitié écrit.
- Stockage SQLite (SQLModel), choisi automatiquement par l'extension `.db`, `.sqlite` ou `.sqlite3`.
- Commande `convert` pour copier le JSON dans SQLite. Après conversion, les artistes et leurs nombres de spectacles sont identiques depuis les deux stockages.
- Chargement par les méthodes publiques du festival, donc toutes les règles sont revérifiées. Un fichier ou une ligne cassés donnent une phrase `StorageError`, pas une trace d'erreur.

**La ligne de commande**

- `programme <jour>` : le programme d'une journée de festival.
- `artists` : les artistes avec leur nombre de spectacles.
- `now [--at <moment>]` : ce qui est en scène et les 3 spectacles suivants.
- `convert <fichier>` et `serve [--host] [--port]`.
- Erreur affichée en une phrase, code de sortie 1.

**L'API web**

- Les 12 routes de `API.md` sont implémentées : 7 en lecture (festival, salles, artistes, fiche artiste, programme avec filtres `day` et `venue`, représentation, `now`) et 5 en écriture (création d'artiste, création, remplacement et suppression de représentation, ajout d'un participant).
- Codes HTTP cohérents : 404, 409, 422, 500, avec le message de l'erreur du modèle en `detail`.
- Un verrou sert une requête à la fois, parce que le festival vit en mémoire.
- Le site public est servi sur `/` et l'administration sur `/admin/`, avec la documentation interactive sur `/docs`.

**La qualité**

- `ruff check` et `ruff format --check` sont propres, avec annotations de types et docstrings.
- `uv build` produit le wheel et le sdist.
