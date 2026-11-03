# Deauville Festival du Rire — programme platform

A Python platform for the programme of the Deauville Festival du Rire
(10–13 June 2027): artists, venues, and three kinds of performances (solo,
lineup, workshop), with the scheduling rules a generic CMS cannot enforce.

It comes with:

- a **model** that refuses any change breaking a rule;
- a **command line** (programme of a day, artists, what is on stage now);
- a **web API** (FastAPI) that serves the public website at `/` and the admin
  at `/admin/`;
- two **storages**: a JSON file (default) and a SQLite database (SQLModel),
  interchangeable.

## Install, run, test

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                   # install everything

uv run deauville programme 2027-06-11     # programme of a festival day
uv run deauville artists                  # artists with their number of shows
uv run deauville now --at 2027-06-11T21:30  # on stage + next 3 (default: now)
uv run deauville serve                    # http://127.0.0.1:8000/  (admin: /admin/, docs: /docs)

uv run pytest                             # the tests
uv run ruff check . && uv run ruff format --check .
uv build                                  # wheel + sdist in dist/
```

`uv run python -m deauville <command>` works too. The default data file is
`data/festival.json`; use `--data` to choose another one. The extension decides
the storage: `.db`, `.sqlite` or `.sqlite3` is SQLite, anything else is JSON.

```bash
uv run deauville convert data/festival.db            # copy the JSON into SQLite
uv run deauville --data data/festival.db serve       # serve from SQLite
DEAUVILLE_DATA=data/festival.db uv run uvicorn --factory deauville.api:create_app
```

## Structure and why

```
src/deauville/               the package (src layout: tests use the installed package)
  __init__.py                what `import deauville` offers
  __main__.py                `python -m deauville`
  exceptions.py              the errors (one class per kind of broken rule)
  utils.py                   names, slugs, integers, dates, festival day (no state)
  venue.py                   Venue
  artist.py                  Artist
  performance.py             Performance (abstract), Solo, Lineup, Workshop
  festival.py                Festival: the only door to change the programme
  storage/
    base.py                  Storage (abstract contract)
    json_storage.py          JsonStorage
    sqlite_storage.py        SqliteStorage (SQLModel)
    factory.py               open_storage(): chooses by file extension
  cli.py                     the command line
  api.py                     the FastAPI application
tests/                       pytest, one file per subject
data/festival.json           the data
web/public/, web/admin/      the website and the admin
API.md                       the API contract
b1/                          early scripts (block B1), kept for history
```

**Which objects, what does each one know and check?**
`Venue` and `Artist` check their own values (non-empty trimmed name, seats ≥ 1)
and compute their slug. A performance checks everything that depends on itself
only: duration 1–360, kind-specific rules (age 0–18; ≥ 2 distinct acts, host not
an act, minimum duration `n×10 + (n−1)×3`; workshop places and case-insensitive
participants). Since the constructors check, a broken object cannot exist,
whoever builds it. Attributes are private, with read-only properties.

**What do the three kinds share, what differs?**
`Performance` is an abstract class holding what is common: title, venue, start,
duration, description, `end`, `id`, `festival_day`, `is_too_close()`. Each
subclass supplies what changes: who is on stage (`artist_slugs`), the capacity,
a one-line summary, its saved fields, and optionally a venue check
(`check_venue`, used by the workshop). Adding a fourth kind means writing one
subclass; it registers itself by its `kind`, so loading needs no change.

**Where does a rule live so nobody can bypass it?**
Rules involving one object live in that object. Rules involving several
(references exist, day of the festival, 30 minutes for a venue, 30 minutes for
an artist in any role) live in `Festival`, which is the only way to add,
replace, remove or register: there is no public list to append to. The CLI,
the API and the tests all call it. Each change is all-or-nothing (`_change()`
restores the previous state if a rule is broken **or** if saving fails), and
the festival saves itself after each successful change.

**How does the caller know which rule was broken?**
Each rule raises its own subclass of `FestivalError` with a sentence an
organiser understands (`VenueBusyError`, `ArtistBusyError`,
`OutsideFestivalError`, `WorkshopFullError`, `AlreadyExistsError`,
`NotFoundError`, `InvalidValueError`, `StorageError`). The model knows nothing
about HTTP: `api.py` maps `NotFoundError` → 404, `ConflictError` → 409,
`InvalidValueError` → 422, anything else → 500. The CLI prints the sentence and
exits with 1. The API only checks the *shape* of a request (pydantic); the
rules stay in the model.

**If the data moved from JSON to a database, which files would change?**
Only a new storage file. `Storage` is the contract (`load()`, `save()`); the
festival only knows that contract. This was done for real: `storage/sqlite_storage.py`
is the whole SQLite support, plus two lines choosing it in `open_storage()`.
The model, the CLI and the API did not change. `load()` rebuilds the festival
through its public methods, so every rule is checked again for both storages,
and a broken file or row gives a `StorageError` sentence, not a traceback.

Other choices: JSON is written to a temporary file then renamed, so a failure
never leaves half a file. In the API, a lock serves one request at a time,
because the festival lives in memory and routes run in threads.

## What is done, and what is not

Done:

- all the rules of the brief, with clear messages and no change on error;
- JSON storage and SQLite storage (extension), `convert` command;
- command line: programme of a day, artists with show counts, now + next 3;
- all the routes of `API.md`, public website and admin served;
- 116 pytest tests (models, festival, storages, CLI, API);
- `ruff check` and `ruff format` clean, type annotations, docstrings,
  `uv build` works.

Not done / limits:

- SQLite `save()` rewrites all the tables in one transaction at each change:
  simple and safe for a festival-sized dataset, not meant for large data.
- No authentication on the admin routes, no concurrent writers on one file
  (one server process is assumed).
- No schema migrations for the SQLite database.
