"""Small helpers shared by the whole model: names, slugs, integers, time."""

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from .exceptions import InvalidValueError

DAY_END = timedelta(hours=6)
"""A festival day ends at 06:00: earlier times belong to the previous day."""


def clean_name(value: object, label: str = "Name") -> str:
    """Return ``value`` without the spaces around it; refuse an empty name."""
    if not isinstance(value, str):
        raise InvalidValueError(f"{label} must be a text.")
    name = value.strip()
    if not name:
        raise InvalidValueError(f"{label} cannot be empty.")
    return name


def slugify(name: str) -> str:
    """Turn a name into a slug: ``"Élodie  Marchal !"`` -> ``"elodie-marchal"``."""
    without_accents = unicodedata.normalize("NFKD", name)
    ascii_text = without_accents.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if not slug:
        raise InvalidValueError(
            f"'{name}' cannot be used as a name: it has no letter or digit."
        )
    return slug


def check_int(value: object, label: str, low: int, high: int | None = None) -> int:
    """Return ``value`` if it is an integer between ``low`` and ``high``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidValueError(f"{label} must be a whole number.")
    if value < low or (high is not None and value > high):
        limits = f"at least {low}" if high is None else f"between {low} and {high}"
        raise InvalidValueError(f"{label} must be {limits} (got {value}).")
    return value


def parse_moment(value: object, label: str = "Date") -> datetime:
    """Read a local moment such as ``"2027-06-11T21:00"`` (no time zone)."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.strip())
        except ValueError:
            raise InvalidValueError(
                f"{label} '{value}' is not a valid moment (expected 2027-06-11T21:00)."
            ) from None
    else:
        raise InvalidValueError(f"{label} must be a text like 2027-06-11T21:00.")
    if moment.tzinfo is not None:
        raise InvalidValueError(f"{label} must be a local time, without time zone.")
    return moment


def parse_day(value: object, label: str = "Day") -> date:
    """Read a day such as ``"2027-06-11"``."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise InvalidValueError(f"{label} must be a text like 2027-06-11.")
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise InvalidValueError(
            f"{label} '{value}' is not a valid day (expected 2027-06-11)."
        ) from None


def festival_day(moment: datetime) -> date:
    """The festival day a moment belongs to (a day ends at 06:00)."""
    return (moment - DAY_END).date()


def format_moment(moment: datetime) -> str:
    """``2027-06-12T01:00`` as ``"2027-06-12 01:00"``."""
    return f"{moment:%Y-%m-%d %H:%M}"


def required_field(data: dict[str, Any], key: str) -> Any:
    """Read a required field of a dict, with a clear error if it is missing."""
    if not isinstance(data, dict):
        raise InvalidValueError("An object with fields was expected.")
    if key not in data:
        raise InvalidValueError(f"Missing field '{key}'.")
    return data[key]
