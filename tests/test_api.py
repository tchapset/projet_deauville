import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from deauville import Festival, JsonStorage, StorageError
from deauville.api import create_app

DATA = Path(__file__).parent.parent / "data" / "festival.json"
AFTER_HOURS = "le-kiosque-2027-06-12-0100"
IMPROV = "la-cabane-2027-06-11-1030"  # workshop, 3 of 12 registered

SOLO = {
    "kind": "solo",
    "title": "Morning Warm-up",
    "venue": "la-cabane",
    "start": "2027-06-10T10:00",
    "duration_minutes": 60,
    "artist": "sacha-diallo",
    "min_age": 12,
}


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """A copy of the data file: tests never touch the real one."""
    copy = tmp_path / "festival.json"
    shutil.copy(DATA, copy)
    return copy


@pytest.fixture
def client(data_file: Path) -> TestClient:
    return TestClient(create_app(data_file))


def saved(data_file: Path) -> Festival:
    """Reload the file, to check that a change reached the disk."""
    return JsonStorage(data_file).load()


# --- read -------------------------------------------------------------------


def test_festival(client):
    data = client.get("/api/festival").json()
    assert data["first_day"] == "2027-06-10"
    assert data["days"] == ["2027-06-10", "2027-06-11", "2027-06-12", "2027-06-13"]


def test_venues_in_the_order_they_were_added(client):
    venues = client.get("/api/venues").json()
    assert venues[0] == {
        "slug": "grand-casino",
        "name": "Grand Casino",
        "capacity": 650,
        "address": venues[0]["address"],
    }
    assert len(venues) == 4


def test_artists_sorted_by_slug(client):
    artists = client.get("/api/artists").json()
    assert len(artists) == 12
    assert artists[0]["slug"] == "elodie-marchal"
    assert set(artists[0]) == {"slug", "name", "bio", "photo_url"}


def test_artist_with_performances(client):
    artist = client.get("/api/artists/hugo-lemaire").json()
    assert artist["name"] == "Hugo Lemaire"
    starts = [p["start"] for p in artist["performances"]]
    assert len(starts) == 4 and starts == sorted(starts)


def test_unknown_artist(client):
    response = client.get("/api/artists/nobody")
    assert response.status_code == 404
    assert "nobody" in response.json()["detail"]


def test_programme_filters(client):
    day = client.get("/api/programme", params={"day": "2027-06-11"}).json()
    assert day[0]["title"] == "Improv for Beginners"
    assert day[-1]["id"] == AFTER_HOURS  # 01:00 on the 12th is still the 11th
    assert {p["festival_day"] for p in day} == {"2027-06-11"}
    venue = client.get("/api/programme", params={"venue": "le-kiosque"}).json()
    assert {p["venue"] for p in venue} == {"le-kiosque"}
    assert len(client.get("/api/programme").json()) == 23


def test_programme_bad_filters(client):
    assert client.get("/api/programme", params={"day": "June 11"}).status_code == 422
    assert client.get("/api/programme", params={"venue": "x"}).status_code == 404


def test_performance_fields(client):
    after = client.get(f"/api/performances/{AFTER_HOURS}").json()
    assert after["kind"] == "lineup"
    assert after["end"] == "2027-06-12T02:00"
    assert after["festival_day"] == "2027-06-11"
    assert after["venue_name"] == "Le Kiosque"
    assert after["capacity"] == 120
    assert after["summary"].startswith("hosted by Tom Vasseur")
    assert [a["slug"] for a in after["artists"]][0] == "tom-vasseur"
    assert "places_left" not in after


def test_workshop_places_left(client):
    improv = client.get(f"/api/performances/{IMPROV}").json()
    assert improv["capacity"] == 12 and improv["places_left"] == 9


def test_unknown_performance(client):
    assert client.get("/api/performances/nope").status_code == 404


def test_now(client):
    data = client.get("/api/now", params={"at": "2027-06-11T21:00"}).json()
    assert data["at"] == "2027-06-11T21:00"
    assert [p["title"] for p in data["now_playing"]] == ["Tall Tales"]
    assert len(data["up_next"]) == 3


def test_now_without_at_and_bad_at(client):
    data = client.get("/api/now").json()  # the festival is in 2027
    assert data["now_playing"] == []
    assert client.get("/api/now", params={"at": "tonight"}).status_code == 422


# --- write ------------------------------------------------------------------


def test_create_artist(client, data_file):
    response = client.post("/api/artists", json={"name": "  Zoé Petit "})
    assert response.status_code == 201
    assert response.json()["slug"] == "zoe-petit"
    assert response.json()["bio"] == ""
    assert saved(data_file).get_artist("zoe-petit").name == "Zoé Petit"


def test_create_artist_errors(client):
    duplicate = client.post("/api/artists", json={"name": "Nora  Lebrun"})
    assert duplicate.status_code == 409
    assert client.post("/api/artists", json={"name": "   "}).status_code == 422
    missing = client.post("/api/artists", json={"bio": "no name"})
    assert missing.status_code == 422
    assert isinstance(missing.json()["detail"], list)  # FastAPI's own 422


def test_create_solo(client, data_file):
    response = client.post("/api/performances", json=SOLO)
    assert response.status_code == 201
    created = response.json()
    assert created["id"] == "la-cabane-2027-06-10-1000"
    assert created["min_age"] == 12 and created["summary"] == "Sacha Diallo, 12+"
    assert created["id"] in {p.id for p in saved(data_file).performances()}


def test_create_lineup_and_workshop(client):
    lineup = {
        "kind": "lineup",
        "title": "Gala",
        "venue": "grand-casino",
        "start": "2027-06-10T12:00",
        "duration_minutes": 90,
        "host": "karim-benali",
        "acts": ["sacha-diallo", "jeanne-aubry"],
    }
    assert client.post("/api/performances", json=lineup).status_code == 201
    workshop = {
        "kind": "workshop",
        "title": "Clowning",
        "venue": "la-cabane",
        "start": "2027-06-10T10:00",
        "duration_minutes": 90,
        "teacher": "sacha-diallo",
        "max_participants": 8,
    }
    created = client.post("/api/performances", json=workshop).json()
    assert created["places_left"] == 8 and created["participants"] == []


def test_venue_busy_is_409_and_changes_nothing(client, data_file):
    before = data_file.read_text(encoding="utf-8")
    body = {**SOLO, "venue": "le-kiosque", "start": "2027-06-12T02:10"}
    response = client.post("/api/performances", json=body)
    assert response.status_code == 409
    assert "Le Kiosque is busy with After Hours" in response.json()["detail"]
    assert data_file.read_text(encoding="utf-8") == before


def test_artist_busy_is_409(client):
    body = {**SOLO, "artist": "tom-vasseur", "start": "2027-06-12T01:30"}
    response = client.post("/api/performances", json={**body, "venue": "la-cabane"})
    assert response.status_code == 409
    assert "Tom Vasseur" in response.json()["detail"]


def test_outside_the_festival_is_409(client):
    body = {**SOLO, "start": "2027-06-20T10:00"}
    assert client.post("/api/performances", json=body).status_code == 409


def test_invalid_values_are_422_with_a_sentence(client):
    response = client.post("/api/performances", json={**SOLO, "duration_minutes": 0})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert (
        client.post("/api/performances", json={**SOLO, "title": " "}).status_code == 422
    )


def test_unknown_references_are_404(client):
    assert (
        client.post("/api/performances", json={**SOLO, "venue": "x"}).status_code == 404
    )
    assert (
        client.post("/api/performances", json={**SOLO, "artist": "x"}).status_code
        == 404
    )


def test_wrong_shape_is_refused_by_fastapi(client):
    unknown_kind = client.post("/api/performances", json={**SOLO, "kind": "circus"})
    assert unknown_kind.status_code == 422
    assert isinstance(unknown_kind.json()["detail"], list)
    no_artist = {k: v for k, v in SOLO.items() if k != "artist"}
    assert client.post("/api/performances", json=no_artist).status_code == 422


def test_replace_moves_the_performance(client, data_file):
    body = {**SOLO, "title": "Warm-up", "start": "2027-06-10T11:00"}
    created = client.post("/api/performances", json=SOLO).json()
    response = client.put(f"/api/performances/{created['id']}", json=body)
    assert response.status_code == 200
    assert response.json()["id"] == "la-cabane-2027-06-10-1100"
    assert client.get(f"/api/performances/{created['id']}").status_code == 404
    ids = {p.id for p in saved(data_file).performances()}
    assert "la-cabane-2027-06-10-1100" in ids and created["id"] not in ids


def test_replace_onto_a_busy_slot_changes_nothing(client, data_file):
    created = client.post("/api/performances", json=SOLO).json()
    before = data_file.read_text(encoding="utf-8")
    busy = {**SOLO, "venue": "le-kiosque", "start": "2027-06-12T01:30"}
    response = client.put(f"/api/performances/{created['id']}", json=busy)
    assert response.status_code == 409
    assert client.get(f"/api/performances/{created['id']}").status_code == 200
    assert data_file.read_text(encoding="utf-8") == before


def test_replace_may_keep_its_own_slot(client):
    body = {**SOLO, "description": "same slot, new text"}
    created = client.post("/api/performances", json=SOLO).json()
    response = client.put(f"/api/performances/{created['id']}", json=body)
    assert response.status_code == 200 and response.json()["id"] == created["id"]


def test_replace_unknown_performance(client):
    assert client.put("/api/performances/nope", json=SOLO).status_code == 404


def test_delete(client, data_file):
    assert client.delete(f"/api/performances/{AFTER_HOURS}").status_code == 204
    assert client.get(f"/api/performances/{AFTER_HOURS}").status_code == 404
    assert client.delete(f"/api/performances/{AFTER_HOURS}").status_code == 404
    assert len(saved(data_file).performances()) == 22


def test_register_participant(client, data_file):
    url = f"/api/performances/{IMPROV}/participants"
    response = client.post(url, json={"name": " Zoé P. "})
    assert response.status_code == 201
    assert response.json()["places_left"] == 8
    assert "Zoé P." in response.json()["participants"]
    assert "Zoé P." in saved(data_file).get_performance(IMPROV).participants


def test_register_twice_ignores_case(client):
    url = f"/api/performances/{IMPROV}/participants"
    response = client.post(url, json={"name": "camille r."})
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_register_to_a_full_workshop(client):
    small = {
        "kind": "workshop",
        "title": "Tiny",
        "venue": "la-cabane",
        "start": "2027-06-10T10:00",
        "duration_minutes": 60,
        "teacher": "sacha-diallo",
        "max_participants": 1,
    }
    created = client.post("/api/performances", json=small).json()
    url = f"/api/performances/{created['id']}/participants"
    assert client.post(url, json={"name": "A"}).status_code == 201
    full = client.post(url, json={"name": "B"})
    assert full.status_code == 409 and "full" in full.json()["detail"]


def test_register_to_something_that_is_not_a_workshop(client):
    url = f"/api/performances/{AFTER_HOURS}/participants"
    assert client.post(url, json={"name": "A"}).status_code == 422
    assert (
        client.post(
            "/api/performances/nope/participants", json={"name": "A"}
        ).status_code
        == 404
    )


# --- storage failures ---------------------------------------------------------


class FailingStorage(JsonStorage):
    """Loads fine, then cannot write."""

    broken = False

    def save(self, festival):
        if self.broken:
            raise StorageError("Cannot write the data file: disk full.")
        super().save(festival)


def test_saving_failure_is_500_and_changes_nothing(data_file):
    storage = FailingStorage(data_file)
    client = TestClient(create_app(storage=storage))
    storage.broken = True
    response = client.post("/api/performances", json=SOLO)
    assert response.status_code == 500
    assert response.json() == {"detail": "Cannot write the data file: disk full."}
    assert len(client.get("/api/programme").json()) == 23  # rolled back


def test_broken_data_file_stops_the_start(tmp_path):
    broken = tmp_path / "festival.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(StorageError, match="not valid JSON"):
        create_app(broken)
    data = json.loads(DATA.read_text(encoding="utf-8"))
    data["performances"][0]["venue"] = "nowhere"
    broken.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StorageError, match="Unknown venue"):
        create_app(broken)


# --- the websites -------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("/", "<html"),
        ("/style.css", "{"),
        ("/app.js", "fetch"),
        ("/artist.html", "<html"),
        ("/admin/", "<html"),
        ("/admin/admin.js", "fetch"),
        ("/docs", "swagger"),
    ],
)
def test_websites_and_docs_are_served(client, path, text):
    response = client.get(path)
    assert response.status_code == 200
    assert text in response.text.lower()


def test_api_is_not_hidden_by_the_websites(client):
    assert client.get("/api/festival").headers["content-type"] == "application/json"
