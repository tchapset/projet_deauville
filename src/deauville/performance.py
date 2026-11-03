"""The performances of the festival: an abstract kind and its three variants.

Each object checks its own values when it is created, so a broken object can
never exist, whoever builds it (command line, web API, tests, data file).
The rules that involve several objects (conflicts, days of the festival,
references) live in :mod:`deauville.festival`.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any, ClassVar, Self

from .exceptions import AlreadyExistsError, InvalidValueError, WorkshopFullError
from .utils import (
    check_int,
    clean_name,
    festival_day,
    format_moment,
    parse_moment,
    required_field,
)
from .venue import Venue

MIN_DURATION = 1
MAX_DURATION = 360
ACT_BREAK = 10
"""Minutes needed by each act of a lineup."""
HOST_BREAK = 3
"""Minutes needed by the host between two acts."""
MAX_AGE = 18


class Performance(ABC):
    """Something that happens in a venue at a given time.

    This class holds what the three kinds share. Each kind adds its own fields
    and rules, and says who is on stage (:attr:`artist_slugs`).
    """

    kind: ClassVar[str]
    _kinds: ClassVar[dict[str, type["Performance"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "kind", None):
            Performance._kinds[cls.kind] = cls

    def __init__(
        self,
        title: str,
        venue: str,
        start: datetime | str,
        duration_minutes: int,
        description: str = "",
    ) -> None:
        self._title = clean_name(title, "Performance title")
        self._venue = clean_name(venue, "Venue")
        self._start = parse_moment(start, "Start")
        self._duration = check_int(
            duration_minutes, "Duration", MIN_DURATION, MAX_DURATION
        )
        if not isinstance(description, str):
            raise InvalidValueError("Description must be a text.")
        self._description = description.strip()

    # --- what every performance has ---------------------------------------

    @property
    def title(self) -> str:
        return self._title

    @property
    def venue(self) -> str:
        """Slug of the venue."""
        return self._venue

    @property
    def start(self) -> datetime:
        return self._start

    @property
    def duration_minutes(self) -> int:
        return self._duration

    @property
    def description(self) -> str:
        return self._description

    @property
    def end(self) -> datetime:
        return self._start + timedelta(minutes=self._duration)

    @property
    def id(self) -> str:
        """Venue slug + start, e.g. ``le-kiosque-2027-06-12-0100``."""
        return f"{self._venue}-{self._start:%Y-%m-%d-%H%M}"

    @property
    def festival_day(self) -> date:
        """The festival day of the performance (a day ends at 06:00)."""
        return festival_day(self._start)

    def describe(self) -> str:
        """``After Hours (2027-06-12 01:00-02:00)``, used in error messages."""
        return f"{self._title} ({format_moment(self._start)}-{self.end:%H:%M})"

    def is_too_close(self, other: "Performance", gap: timedelta) -> bool:
        """True if the two performances overlap or are closer than ``gap``."""
        return self._start < other.end + gap and other._start < self.end + gap

    # --- what changes with the kind ---------------------------------------

    @property
    @abstractmethod
    def artist_slugs(self) -> tuple[str, ...]:
        """Everyone on stage, in order of appearance."""

    @abstractmethod
    def capacity(self, venue: Venue) -> int:
        """Seats (or places) available for this performance."""

    @abstractmethod
    def summary(self, names: dict[str, str]) -> str:
        """One line for the programme. ``names`` maps a slug to a name."""

    def check_venue(self, venue: Venue) -> None:  # noqa: B027 - optional hook
        """Check the rules that depend on the venue. Does nothing by default."""

    @abstractmethod
    def _extra_fields(self) -> dict[str, Any]:
        """Fields specific to the kind, for the data file."""

    @classmethod
    @abstractmethod
    def _from_fields(cls, data: dict[str, Any]) -> Self:
        """Build the performance from the saved fields."""

    # --- saving and loading -----------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Saved fields only (no ``id``, ``end``, ``summary``...)."""
        return {
            "kind": self.kind,
            "title": self._title,
            "venue": self._venue,
            "start": self._start.isoformat(timespec="minutes"),
            "duration_minutes": self._duration,
            "description": self._description,
            **self._extra_fields(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Performance":
        """Build the right kind of performance from its saved fields."""
        kind = required_field(data, "kind")
        kind_class = cls._kinds.get(kind) if isinstance(kind, str) else None
        if kind_class is None:
            known = ", ".join(sorted(cls._kinds))
            raise InvalidValueError(f"Unknown kind '{kind}' (expected: {known}).")
        return kind_class._from_fields(data)

    @classmethod
    def _common_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": required_field(data, "title"),
            "venue": required_field(data, "venue"),
            "start": required_field(data, "start"),
            "duration_minutes": required_field(data, "duration_minutes"),
            "description": data.get("description", ""),
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r}, {self._title!r})"


class Solo(Performance):
    """One artist alone on stage, for an audience of a minimum age."""

    kind = "solo"

    def __init__(
        self,
        title: str,
        venue: str,
        start: datetime | str,
        duration_minutes: int,
        artist: str,
        min_age: int = 0,
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        self._artist = clean_name(artist, "Artist")
        self._min_age = check_int(min_age, "Minimum age", 0, MAX_AGE)

    @property
    def artist(self) -> str:
        return self._artist

    @property
    def min_age(self) -> int:
        return self._min_age

    @property
    def artist_slugs(self) -> tuple[str, ...]:
        return (self._artist,)

    def capacity(self, venue: Venue) -> int:
        return venue.capacity

    def summary(self, names: dict[str, str]) -> str:
        who = names.get(self._artist, self._artist)
        age = "all ages" if self._min_age == 0 else f"{self._min_age}+"
        return f"{who}, {age}"

    def _extra_fields(self) -> dict[str, Any]:
        return {"artist": self._artist, "min_age": self._min_age}

    @classmethod
    def _from_fields(cls, data: dict[str, Any]) -> Self:
        return cls(
            **cls._common_fields(data),
            artist=required_field(data, "artist"),
            min_age=data.get("min_age", 0),
        )


class Lineup(Performance):
    """A host, then acts one after another."""

    kind = "lineup"

    def __init__(
        self,
        title: str,
        venue: str,
        start: datetime | str,
        duration_minutes: int,
        host: str,
        acts: list[str] | tuple[str, ...],
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        self._host = clean_name(host, "Host")
        if not isinstance(acts, (list, tuple)):
            raise InvalidValueError("Acts must be a list of artists.")
        self._acts = tuple(clean_name(act, "Act") for act in acts)
        if len(self._acts) < 2:
            raise InvalidValueError("A lineup needs at least 2 acts.")
        if len(set(self._acts)) != len(self._acts):
            raise InvalidValueError("An artist can appear only once in a lineup.")
        if self._host in self._acts:
            raise InvalidValueError("The host of a lineup cannot also be an act.")
        needed = self.minimum_duration(len(self._acts))
        if self._duration < needed:
            raise InvalidValueError(
                f"A lineup of {len(self._acts)} acts needs at least "
                f"{needed} minutes (got {self._duration})."
            )

    @staticmethod
    def minimum_duration(act_count: int) -> int:
        """10 minutes per act, 3 minutes for the host between two acts."""
        return act_count * ACT_BREAK + (act_count - 1) * HOST_BREAK

    @property
    def host(self) -> str:
        return self._host

    @property
    def acts(self) -> tuple[str, ...]:
        return self._acts

    @property
    def artist_slugs(self) -> tuple[str, ...]:
        return (self._host, *self._acts)

    def capacity(self, venue: Venue) -> int:
        return venue.capacity

    def summary(self, names: dict[str, str]) -> str:
        host = names.get(self._host, self._host)
        acts = ", ".join(names.get(act, act) for act in self._acts)
        return f"hosted by {host}, with {acts}"

    def _extra_fields(self) -> dict[str, Any]:
        return {"host": self._host, "acts": list(self._acts)}

    @classmethod
    def _from_fields(cls, data: dict[str, Any]) -> Self:
        return cls(
            **cls._common_fields(data),
            host=required_field(data, "host"),
            acts=required_field(data, "acts"),
        )


class Workshop(Performance):
    """A teacher and participants who register by name, until it is full."""

    kind = "workshop"

    def __init__(
        self,
        title: str,
        venue: str,
        start: datetime | str,
        duration_minutes: int,
        teacher: str,
        max_participants: int,
        participants: list[str] | tuple[str, ...] = (),
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        self._teacher = clean_name(teacher, "Teacher")
        self._max_participants = check_int(
            max_participants, "Maximum number of participants", 1
        )
        if not isinstance(participants, (list, tuple)):
            raise InvalidValueError("Participants must be a list of names.")
        self._participants: list[str] = []
        for name in participants:
            self._add_name(name)

    @property
    def teacher(self) -> str:
        return self._teacher

    @property
    def max_participants(self) -> int:
        return self._max_participants

    @property
    def participants(self) -> tuple[str, ...]:
        return tuple(self._participants)

    @property
    def artist_slugs(self) -> tuple[str, ...]:
        return (self._teacher,)

    def capacity(self, venue: Venue) -> int:
        """``min(max_participants, venue seats)``."""
        return min(self._max_participants, venue.capacity)

    def places_left(self, venue: Venue) -> int:
        return self.capacity(venue) - len(self._participants)

    def check_venue(self, venue: Venue) -> None:
        if len(self._participants) > self.capacity(venue):
            raise WorkshopFullError(
                f"{self._title} has {len(self._participants)} participants "
                f"but only {self.capacity(venue)} places in {venue.name}."
            )

    def register(self, name: str, venue: Venue) -> None:
        """Register a participant. Nothing changes if the workshop is full."""
        clean = clean_name(name, "Participant name")
        if self._is_registered(clean):
            raise AlreadyExistsError(f"{clean} is already registered to {self._title}.")
        if self.places_left(venue) <= 0:
            raise WorkshopFullError(f"{self._title} is full.")
        self._participants.append(clean)

    def _is_registered(self, name: str) -> bool:
        return name.casefold() in (p.casefold() for p in self._participants)

    def _add_name(self, name: object) -> None:
        clean = clean_name(name, "Participant name")
        if self._is_registered(clean):
            raise InvalidValueError(f"{clean} is registered twice to {self._title}.")
        self._participants.append(clean)

    def summary(self, names: dict[str, str]) -> str:
        teacher = names.get(self._teacher, self._teacher)
        return f"taught by {teacher}"

    def _extra_fields(self) -> dict[str, Any]:
        return {
            "teacher": self._teacher,
            "max_participants": self._max_participants,
            "participants": list(self._participants),
        }

    @classmethod
    def _from_fields(cls, data: dict[str, Any]) -> Self:
        return cls(
            **cls._common_fields(data),
            teacher=required_field(data, "teacher"),
            max_participants=required_field(data, "max_participants"),
            participants=data.get("participants", []),
        )
