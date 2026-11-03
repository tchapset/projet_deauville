"""The festival: the only door to change the programme.

Every rule that involves several objects lives here: references that must
exist, days of the festival, 30 minutes between two shows in a venue or for an
artist. The command line, the web API and the tests all call these methods,
so none of them can bypass a rule.

A change is all or nothing: if a rule is broken (or if saving fails), the
festival is left exactly as it was.
"""

import copy
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from .artist import Artist
from .exceptions import (
    AlreadyExistsError,
    ArtistBusyError,
    InvalidValueError,
    NotFoundError,
    OutsideFestivalError,
    VenueBusyError,
)
from .performance import Performance, Workshop
from .utils import clean_name, parse_day
from .venue import Venue

if TYPE_CHECKING:
    from .storage import Storage

VENUE_GAP = timedelta(minutes=30)
"""Time a venue needs between two performances."""
ARTIST_GAP = timedelta(minutes=30)
"""Time an artist needs between two performances, in any venue and any role."""
UP_NEXT = 3


class Festival:
    """An edition of the festival: venues, artists and performances."""

    def __init__(self, name: str, first_day: date | str, last_day: date | str) -> None:
        self._name = clean_name(name, "Festival name")
        self._first_day = parse_day(first_day, "First day")
        self._last_day = parse_day(last_day, "Last day")
        if self._last_day < self._first_day:
            raise InvalidValueError("The last day cannot be before the first day.")
        self._venues: dict[str, Venue] = {}
        self._artists: dict[str, Artist] = {}
        self._performances: dict[str, Performance] = {}
        self._storage: Storage | None = None

    # --- general information ----------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def first_day(self) -> date:
        return self._first_day

    @property
    def last_day(self) -> date:
        return self._last_day

    @property
    def days(self) -> list[date]:
        """Every day of the festival, from the first to the last."""
        count = (self._last_day - self._first_day).days + 1
        return [self._first_day + timedelta(days=i) for i in range(count)]

    def bind(self, storage: "Storage") -> None:
        """Save to ``storage`` after every successful change."""
        self._storage = storage

    # --- reading ----------------------------------------------------------

    def venues(self) -> list[Venue]:
        """Venues, in the order they were added."""
        return list(self._venues.values())

    def artists(self) -> list[Artist]:
        """Artists, in alphabetical order of their slug."""
        return sorted(self._artists.values(), key=lambda artist: artist.slug)

    def performances(
        self, day: date | str | None = None, venue: str | None = None
    ) -> list[Performance]:
        """Performances by start time, then by venue name.

        ``day`` keeps one festival day, ``venue`` (a slug) keeps one venue.
        """
        wanted_day = parse_day(day) if day is not None else None
        if venue is not None:
            self.get_venue(venue)
        found = [
            performance
            for performance in self._performances.values()
            if (wanted_day is None or performance.festival_day == wanted_day)
            and (venue is None or performance.venue == venue)
        ]
        return sorted(found, key=self._order)

    def get_venue(self, slug: str) -> Venue:
        try:
            return self._venues[slug]
        except KeyError:
            raise NotFoundError(f"Unknown venue '{slug}'.") from None

    def get_artist(self, slug: str) -> Artist:
        try:
            return self._artists[slug]
        except KeyError:
            raise NotFoundError(f"Unknown artist '{slug}'.") from None

    def get_performance(self, performance_id: str) -> Performance:
        try:
            return self._performances[performance_id]
        except KeyError:
            raise NotFoundError(f"Unknown performance '{performance_id}'.") from None

    def performances_of(self, artist_slug: str) -> list[Performance]:
        """Performances where the artist is on stage, in programme order."""
        self.get_artist(artist_slug)
        found = [
            performance
            for performance in self._performances.values()
            if artist_slug in performance.artist_slugs
        ]
        return sorted(found, key=self._order)

    def show_counts(self) -> list[tuple[Artist, int]]:
        """Every artist with the number of performances they are on stage in."""
        return [
            (artist, len(self.performances_of(artist.slug)))
            for artist in self.artists()
        ]

    def now(self, at: datetime) -> tuple[list[Performance], list[Performance]]:
        """What is on stage at ``at``, and the next 3 performances."""
        ordered = self.performances()
        playing = [p for p in ordered if p.start <= at < p.end]
        coming = [p for p in ordered if p.start > at]
        return playing, coming[:UP_NEXT]

    def names(self) -> dict[str, str]:
        """Artist names by slug, for the summaries of the programme."""
        return {slug: artist.name for slug, artist in self._artists.items()}

    def capacity_of(self, performance: Performance) -> int:
        return performance.capacity(self.get_venue(performance.venue))

    # --- changing ---------------------------------------------------------

    def add_venue(self, venue: Venue) -> Venue:
        with self._change():
            if venue.slug in self._venues:
                raise AlreadyExistsError(f"The venue {venue.name} already exists.")
            self._venues[venue.slug] = venue
        return venue

    def add_artist(self, artist: Artist) -> Artist:
        with self._change():
            if artist.slug in self._artists:
                raise AlreadyExistsError(f"The artist {artist.name} already exists.")
            self._artists[artist.slug] = artist
        return artist

    def add_performance(self, performance: Performance) -> Performance:
        with self._change():
            self._check(performance)
            self._performances[performance.id] = performance
        return performance

    def replace_performance(self, performance_id: str, new: Performance) -> Performance:
        """Replace a performance by a new version (moved, renamed...).

        The identifier can change. If the new version breaks a rule, the old
        one stays where it was.
        """
        with self._change():
            self.get_performance(performance_id)
            self._check(new, ignore=performance_id)
            del self._performances[performance_id]
            self._performances[new.id] = new
        return new

    def remove_performance(self, performance_id: str) -> None:
        with self._change():
            self.get_performance(performance_id)
            del self._performances[performance_id]

    def register_participant(self, performance_id: str, name: str) -> Workshop:
        with self._change():
            workshop = self.get_performance(performance_id)
            if not isinstance(workshop, Workshop):
                raise InvalidValueError(
                    f"{workshop.title} is not a workshop: nobody can register to it."
                )
            workshop.register(name, self.get_venue(workshop.venue))
        return workshop

    # --- rules ------------------------------------------------------------

    def _check(self, performance: Performance, ignore: str | None = None) -> None:
        """Raise a FestivalError if the performance breaks a rule."""
        venue = self.get_venue(performance.venue)
        for slug in performance.artist_slugs:
            self.get_artist(slug)
        self._check_day(performance)
        performance.check_venue(venue)
        others = [p for p in self._performances.values() if p.id != ignore]
        self._check_venue_free(performance, venue, others)
        self._check_artists_free(performance, others)

    def _check_day(self, performance: Performance) -> None:
        day = performance.festival_day
        if not self._first_day <= day <= self._last_day:
            raise OutsideFestivalError(
                f"{performance.describe()} belongs to the festival day {day}, "
                f"but the festival runs from {self._first_day} to {self._last_day}."
            )

    def _check_venue_free(
        self, performance: Performance, venue: Venue, others: list[Performance]
    ) -> None:
        for other in others:
            if other.venue == venue.slug and performance.is_too_close(other, VENUE_GAP):
                raise VenueBusyError(
                    f"{venue.name} is busy with {other.describe()}. "
                    f"Leave 30 minutes between two shows."
                )

    def _check_artists_free(
        self, performance: Performance, others: list[Performance]
    ) -> None:
        for other in others:
            if not performance.is_too_close(other, ARTIST_GAP):
                continue
            shared = [s for s in performance.artist_slugs if s in other.artist_slugs]
            if shared:
                artist = self._artists[shared[0]]
                raise ArtistBusyError(
                    f"{artist.name} is already on stage in {other.describe()}. "
                    f"An artist needs 30 minutes between two performances."
                )

    def _order(self, performance: Performance) -> tuple[datetime, str]:
        return performance.start, self._venues[performance.venue].name

    @contextmanager
    def _change(self) -> Iterator[None]:
        """All or nothing: undo everything if a rule or the saving fails."""
        before = (
            dict(self._venues),
            dict(self._artists),
            copy.deepcopy(self._performances),
        )
        try:
            yield
            if self._storage is not None:
                self._storage.save(self)
        except BaseException:
            self._venues, self._artists, self._performances = before
            raise
