"""Web API: the routes of ``API.md`` under ``/api``, plus the two websites.

This module only translates HTTP into calls to :class:`~deauville.Festival` and
back. It checks the *shape* of a request (a missing field, a text where a
number is expected) and nothing else: every festival rule lives in the model,
so the API cannot bypass one.

Run it with ``uv run deauville serve``.
"""

import os
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .artist import Artist
from .exceptions import ConflictError, FestivalError, InvalidValueError, NotFoundError
from .festival import Festival
from .performance import Performance, Workshop
from .storage import Storage, open_storage
from .utils import parse_moment
from .venue import Venue

ROOT = Path(__file__).resolve().parents[2]  # repository root (src/deauville/api.py)
DEFAULT_DATA = ROOT / "data" / "festival.json"
DEFAULT_WEB = ROOT / "web"


# --- what a request must look like (shape only, never the rules) -----------


class ArtistBody(BaseModel):
    name: str
    bio: str = ""
    photo_url: str = ""


class ParticipantBody(BaseModel):
    name: str


class _PerformanceBody(BaseModel):
    title: str
    venue: str
    start: str
    duration_minutes: int
    description: str = ""


class SoloBody(_PerformanceBody):
    kind: Literal["solo"]
    artist: str
    min_age: int = 0


class LineupBody(_PerformanceBody):
    kind: Literal["lineup"]
    host: str
    acts: list[str]


class WorkshopBody(_PerformanceBody):
    kind: Literal["workshop"]
    teacher: str
    max_participants: int
    participants: list[str] = Field(default_factory=list)


PerformanceBody = Annotated[
    SoloBody | LineupBody | WorkshopBody, Field(discriminator="kind")
]


# --- what the API answers --------------------------------------------------


def venue_json(venue: Venue) -> dict[str, Any]:
    return {"slug": venue.slug, **venue.to_dict()}


def artist_json(artist: Artist) -> dict[str, Any]:
    return {"slug": artist.slug, **artist.to_dict()}


def performance_json(festival: Festival, performance: Performance) -> dict[str, Any]:
    """Saved fields, plus what the websites need (id, end, names, capacity...)."""
    venue = festival.get_venue(performance.venue)
    data = performance.to_dict()
    data.update(
        id=performance.id,
        venue_name=venue.name,
        end=performance.end.isoformat(timespec="minutes"),
        festival_day=performance.festival_day.isoformat(),
        summary=performance.summary(festival.names()),
        capacity=performance.capacity(venue),
        artists=[
            {"slug": slug, "name": festival.get_artist(slug).name}
            for slug in performance.artist_slugs
        ],
    )
    if isinstance(performance, Workshop):
        data["places_left"] = performance.places_left(venue)
    return data


def _performances_json(
    festival: Festival, performances: list[Performance]
) -> list[dict[str, Any]]:
    return [performance_json(festival, p) for p in performances]


# --- errors -> status codes -------------------------------------------------


def status_of(error: FestivalError) -> int:
    """HTTP status for a festival error (the table of ``API.md``)."""
    if isinstance(error, NotFoundError):
        return 404
    if isinstance(error, ConflictError):
        return 409
    if isinstance(error, InvalidValueError):
        return 422
    return 500


async def festival_error_handler(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, FestivalError)
    return JSONResponse({"detail": str(error)}, status_code=status_of(error))


# --- the application --------------------------------------------------------


def create_app(
    data: str | Path | None = None,
    web_dir: str | Path = DEFAULT_WEB,
    storage: Storage | None = None,
) -> FastAPI:
    """Build the application on a data file (JSON or SQLite) or any storage.

    The data file is ``$DEAUVILLE_DATA`` when ``data`` is not given. A broken
    file raises a :class:`StorageError` here, at start-up, not at the first
    request.
    """
    if storage is None:
        path = data or os.environ.get("DEAUVILLE_DATA") or DEFAULT_DATA
        storage = open_storage(path)
    festival = storage.load()

    # The festival lives in memory and routes run in several threads: one
    # request at a time keeps a read from seeing a half-done change.
    lock = threading.Lock()

    def one_at_a_time() -> Iterator[None]:
        with lock:
            yield

    app = FastAPI(
        title="Deauville Festival du Rire",
        description="Programme of the festival: artists, venues, performances.",
    )
    app.add_exception_handler(FestivalError, festival_error_handler)
    api = APIRouter(prefix="/api", dependencies=[Depends(one_at_a_time)])

    # --- read ---

    @api.get("/festival")
    def get_festival() -> dict[str, Any]:
        return {
            "name": festival.name,
            "first_day": festival.first_day.isoformat(),
            "last_day": festival.last_day.isoformat(),
            "days": [day.isoformat() for day in festival.days],
        }

    @api.get("/venues")
    def list_venues() -> list[dict[str, Any]]:
        return [venue_json(v) for v in festival.venues()]

    @api.get("/artists")
    def list_artists() -> list[dict[str, Any]]:
        return [artist_json(a) for a in festival.artists()]

    @api.get("/artists/{slug}")
    def get_artist(slug: str) -> dict[str, Any]:
        artist = festival.get_artist(slug)
        shows = _performances_json(festival, festival.performances_of(slug))
        return {**artist_json(artist), "performances": shows}

    @api.get("/programme")
    def get_programme(
        day: str | None = None, venue: str | None = None
    ) -> list[dict[str, Any]]:
        found = festival.performances(day=day, venue=venue)
        return _performances_json(festival, found)

    @api.get("/performances/{performance_id}")
    def get_performance(performance_id: str) -> dict[str, Any]:
        return performance_json(festival, festival.get_performance(performance_id))

    @api.get("/now")
    def get_now(at: str | None = None) -> dict[str, Any]:
        moment = (
            parse_moment(at, "at")
            if at
            else datetime.now().replace(second=0, microsecond=0)
        )
        playing, coming = festival.now(moment)
        return {
            "at": moment.isoformat(timespec="minutes"),
            "now_playing": _performances_json(festival, playing),
            "up_next": _performances_json(festival, coming),
        }

    # --- write ---

    @api.post("/artists", status_code=201)
    def create_artist(body: ArtistBody) -> dict[str, Any]:
        artist = festival.add_artist(Artist(body.name, body.bio, body.photo_url))
        return artist_json(artist)

    @api.post("/performances", status_code=201)
    def create_performance(body: PerformanceBody) -> dict[str, Any]:
        performance = festival.add_performance(Performance.from_dict(body.model_dump()))
        return performance_json(festival, performance)

    @api.put("/performances/{performance_id}")
    def replace_performance(
        performance_id: str, body: PerformanceBody
    ) -> dict[str, Any]:
        new = festival.replace_performance(
            performance_id, Performance.from_dict(body.model_dump())
        )
        return performance_json(festival, new)

    @api.delete("/performances/{performance_id}", status_code=204)
    def delete_performance(performance_id: str) -> Response:
        festival.remove_performance(performance_id)
        return Response(status_code=204)

    @api.post("/performances/{performance_id}/participants", status_code=201)
    def register_participant(
        performance_id: str, body: ParticipantBody
    ) -> dict[str, Any]:
        workshop = festival.register_participant(performance_id, body.name)
        return performance_json(festival, workshop)

    app.include_router(api)

    # The websites come last: a mount at "/" would hide the routes after it.
    web = Path(web_dir)
    app.mount("/admin", StaticFiles(directory=web / "admin", html=True), name="admin")
    app.mount("/", StaticFiles(directory=web / "public", html=True), name="public")
    return app
