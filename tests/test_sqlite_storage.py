import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from deauville import (
    Artist,
    JsonStorage,
    Solo,
    SqliteStorage,
    StorageError,
    VenueBusyError,
    open_storage,
)
from deauville.cli import main

DATA = Path(__file__).parent.parent / "data" / "festival.json"


@pytest.fixture
def db_file(tmp_path) -> Path:
    path = tmp_path / "festival.db"
    SqliteStorage(path).save(JsonStorage(DATA).load())
    return path


def test_same_festival_in_json_and_sqlite(db_file):
    from_json = JsonStorage(DATA).load()
    from_db = SqliteStorage(db_file).load()
    assert from_db.name == from_json.name
    assert [v.to_dict() for v in from_db.venues()] == [
        v.to_dict() for v in from_json.venues()
    ]
    assert [a.to_dict() for a in from_db.artists()] == [
        a.to_dict() for a in from_json.artists()
    ]
    assert [p.to_dict() for p in from_db.performances()] == [
        p.to_dict() for p in from_json.performances()
    ]


def test_every_change_is_saved(db_file):
    festival = SqliteStorage(db_file).load()
    festival.add_artist(Artist("  Zoé Test  ", "Bio"))
    assert SqliteStorage(db_file).load().get_artist("zoe-test").bio == "Bio"


def test_a_refused_change_is_not_saved(db_file):
    festival = SqliteStorage(db_file).load()
    with pytest.raises(VenueBusyError):
        festival.add_performance(
            Solo("Clash", "le-kiosque", "2027-06-12T01:30", 30, "hugo-lemaire")
        )
    assert len(SqliteStorage(db_file).load().performances()) == 23


def test_workshop_registration_is_saved(db_file):
    festival = SqliteStorage(db_file).load()
    workshop = next(p for p in festival.performances() if p.kind == "workshop")
    festival.register_participant(workshop.id, "Zoé Nouvelle")
    again = SqliteStorage(db_file).load().get_performance(workshop.id)
    assert "Zoé Nouvelle" in again.participants


def test_missing_file_gives_a_sentence(tmp_path):
    with pytest.raises(StorageError, match="no such file"):
        SqliteStorage(tmp_path / "nothing.db").load()


def test_empty_database_gives_a_sentence(tmp_path):
    path = tmp_path / "empty.db"
    SqliteStorage(path).save(JsonStorage(DATA).load())
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM festivalrow")
    with pytest.raises(StorageError, match="no festival"):
        SqliteStorage(path).load()


def test_broken_row_is_refused_on_load(db_file):
    with sqlite3.connect(db_file) as connection:
        connection.execute("UPDATE venuerow SET capacity = 0 WHERE position = 0")
    with pytest.raises(StorageError, match="not valid"):
        SqliteStorage(db_file).load()


def test_not_a_database_gives_a_sentence(tmp_path):
    path = tmp_path / "bad.db"
    path.write_text("this is not sqlite", encoding="utf-8")
    with pytest.raises(StorageError):
        SqliteStorage(path).load()


def test_open_storage_chooses_by_extension(tmp_path):
    assert isinstance(open_storage(tmp_path / "a.db"), SqliteStorage)
    assert isinstance(open_storage(tmp_path / "a.json"), JsonStorage)


def test_convert_command_then_programme(tmp_path, capsys):
    target = tmp_path / "copy.db"
    assert main(["--data", str(DATA), "convert", str(target)]) == 0
    assert main(["--data", str(target), "artists"]) == 0
    assert "shows" in capsys.readouterr().out
    assert main(["--data", str(DATA), "convert", str(target)]) == 1


def test_api_runs_on_sqlite(db_file):
    from fastapi.testclient import TestClient

    from deauville.api import create_app

    client = TestClient(create_app(db_file))
    assert len(client.get("/api/programme").json()) == 23
    shutil.copy(db_file, db_file.with_name("backup.db"))
    created = client.post("/api/artists", json={"name": "Zoé Test"})
    assert created.status_code == 201
    assert SqliteStorage(db_file).load().get_artist("zoe-test")
    assert json.loads(client.get("/api/artists/zoe-test").text)["name"] == "Zoé Test"
