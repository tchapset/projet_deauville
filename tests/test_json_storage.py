import json
import shutil
from pathlib import Path

import pytest

from deauville import (
    Artist,
    JsonStorage,
    Solo,
    StorageError,
    VenueBusyError,
)

DATA = Path(__file__).parent.parent / "data" / "festival.json"


@pytest.fixture
def data_file(tmp_path) -> Path:
    path = tmp_path / "festival.json"
    shutil.copy(DATA, path)
    return path


def test_the_real_data_file_loads():
    festival = JsonStorage(DATA).load()
    assert len(festival.venues()) == 4
    assert len(festival.artists()) == 12
    assert len(festival.performances()) == 23


def test_every_change_is_saved(data_file):
    festival = JsonStorage(data_file).load()
    festival.add_artist(Artist("  Zoé Test  ", "Bio"))
    saved = json.loads(data_file.read_text(encoding="utf-8"))
    assert "Zoé Test" in [a["name"] for a in saved["artists"]]
    assert JsonStorage(data_file).load().get_artist("zoe-test").bio == "Bio"


def test_a_refused_change_is_not_saved(data_file):
    festival = JsonStorage(data_file).load()
    before = data_file.read_text(encoding="utf-8")
    with pytest.raises(VenueBusyError):
        festival.add_performance(
            Solo("Clash", "le-kiosque", "2027-06-12T01:30", 30, "hugo-lemaire")
        )
    assert data_file.read_text(encoding="utf-8") == before


def test_failed_saving_undoes_the_change(data_file, monkeypatch):
    festival = JsonStorage(data_file).load()

    def broken(*_args, **_kwargs):
        raise StorageError("disk full")

    monkeypatch.setattr(JsonStorage, "save", broken)
    with pytest.raises(StorageError):
        festival.add_artist(Artist("Zoé Test"))
    with pytest.raises(Exception, match="Unknown artist"):
        festival.get_artist("zoe-test")


def test_missing_file(tmp_path):
    with pytest.raises(StorageError, match="Cannot read"):
        JsonStorage(tmp_path / "nope.json").load()


def test_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(StorageError, match="not valid JSON"):
        JsonStorage(path).load()


def test_broken_rule_in_the_file_is_a_clear_error(data_file):
    data = json.loads(data_file.read_text(encoding="utf-8"))
    clash = dict(data["performances"][0])
    clash["title"] = "Clash"
    data["performances"].append(clash)
    data_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StorageError, match="is not valid.*busy"):
        JsonStorage(data_file).load()


@pytest.mark.parametrize("missing", ["name", "first_day"])
def test_missing_field_in_the_file(data_file, missing):
    data = json.loads(data_file.read_text(encoding="utf-8"))
    del data[missing]
    data_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StorageError, match=f"Missing field '{missing}'"):
        JsonStorage(data_file).load()


def test_file_that_is_not_an_object(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(StorageError, match="JSON object"):
        JsonStorage(path).load()
