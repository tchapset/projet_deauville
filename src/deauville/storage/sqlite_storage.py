"""The festival in a SQLite database (SQLModel).

:class:`SqliteStorage` is a second implementation of
:class:`~deauville.storage.base.Storage`. It uses the same contract as the JSON
file, so the model, the command line and the API do not change. The rows below
are *storage details*: they never leave this module, and no rule is checked
here. Loading rebuilds the festival through its public methods, so every rule
is checked again exactly as for the JSON file.
"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field, Session, SQLModel, create_engine, delete, select

from ..artist import Artist
from ..exceptions import FestivalError, StorageError
from ..festival import Festival
from ..performance import Performance
from ..venue import Venue
from .base import Storage


class FestivalRow(SQLModel, table=True):
    """The single row holding the name and the days of the festival."""

    id: int = Field(default=1, primary_key=True)
    name: str
    first_day: str
    last_day: str


class VenueRow(SQLModel, table=True):
    slug: str = Field(primary_key=True)
    position: int  # venues keep the order they were added
    name: str
    capacity: int
    address: str = ""


class ArtistRow(SQLModel, table=True):
    slug: str = Field(primary_key=True)
    name: str
    bio: str = ""
    photo_url: str = ""


class PerformanceRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    kind: str
    title: str
    venue: str
    start: str
    duration_minutes: int
    description: str = ""
    extra: str = "{}"  # JSON: the fields that depend on the kind


_COMMON = ("kind", "title", "venue", "start", "duration_minutes", "description")


class SqliteStorage(Storage):
    """The festival in a SQLite file, such as ``data/festival.db``."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _engine(self) -> Engine:
        return create_engine(f"sqlite:///{self._path}")

    def load(self) -> Festival:
        """Read the database and build the festival, bound to this storage.

        A missing or empty database, or a broken row, gives a
        :class:`StorageError` with a sentence, never a traceback.
        """
        if not self._path.is_file():
            raise StorageError(f"Cannot read the database {self._path}: no such file.")
        engine = self._engine()
        try:
            with Session(engine) as session:
                info = session.get(FestivalRow, 1)
                if info is None:
                    raise StorageError(f"The database {self._path} holds no festival.")
                venues = session.exec(
                    select(VenueRow).order_by(VenueRow.position)  # type: ignore[arg-type]
                ).all()
                artists = session.exec(select(ArtistRow)).all()
                performances = session.exec(select(PerformanceRow)).all()
        except SQLAlchemyError as error:
            raise StorageError(
                f"The database {self._path} cannot be read: {error.__class__.__name__}."
            ) from error
        finally:
            engine.dispose()
        try:
            festival = Festival(info.name, info.first_day, info.last_day)
            for venue in venues:
                festival.add_venue(Venue(venue.name, venue.capacity, venue.address))
            for artist in artists:
                festival.add_artist(Artist(artist.name, artist.bio, artist.photo_url))
            for row in performances:
                festival.add_performance(Performance.from_dict(self._fields(row)))
        except StorageError:
            raise
        except FestivalError as error:
            raise StorageError(
                f"The database {self._path} is not valid: {error}"
            ) from error
        festival.bind(self)
        return festival

    def save(self, festival: Festival) -> None:
        """Replace the content of the database, in one transaction."""
        engine = self._engine()
        try:
            SQLModel.metadata.create_all(engine)
            with Session(engine) as session:
                for table in (PerformanceRow, ArtistRow, VenueRow, FestivalRow):
                    session.exec(delete(table))  # type: ignore[call-overload]
                session.add(
                    FestivalRow(
                        name=festival.name,
                        first_day=festival.first_day.isoformat(),
                        last_day=festival.last_day.isoformat(),
                    )
                )
                for position, venue in enumerate(festival.venues()):
                    session.add(
                        VenueRow(slug=venue.slug, position=position, **venue.to_dict())
                    )
                for artist in festival.artists():
                    session.add(ArtistRow(slug=artist.slug, **artist.to_dict()))
                for performance in festival.performances():
                    session.add(self._row(performance))
                session.commit()
        except SQLAlchemyError as error:
            raise StorageError(
                f"Cannot write the database {self._path}: {error.__class__.__name__}."
            ) from error
        finally:
            engine.dispose()

    @staticmethod
    def _row(performance: Performance) -> PerformanceRow:
        data = performance.to_dict()
        common = {key: data.pop(key) for key in _COMMON}
        return PerformanceRow(
            id=performance.id, extra=json.dumps(data, ensure_ascii=False), **common
        )

    @staticmethod
    def _fields(row: PerformanceRow) -> dict[str, Any]:
        try:
            extra = json.loads(row.extra)
        except json.JSONDecodeError:
            raise StorageError(f"Broken data in performance '{row.id}'.") from None
        common = {key: getattr(row, key) for key in _COMMON}
        return {**common, **extra}
