"""A place where performances happen."""

from typing import Any, Self

from .exceptions import InvalidValueError
from .utils import check_int, clean_name, required_field, slugify


class Venue:
    """A place where performances happen."""

    def __init__(self, name: str, capacity: int, address: str = "") -> None:
        self._name = clean_name(name, "Venue name")
        self._slug = slugify(self._name)
        self._capacity = check_int(capacity, "Number of seats", 1)
        if not isinstance(address, str):
            raise InvalidValueError("Venue address must be a text.")
        self._address = address.strip()

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def address(self) -> str:
        return self._address

    def to_dict(self) -> dict[str, Any]:
        """Fields saved in the data file."""
        return {
            "name": self._name,
            "capacity": self._capacity,
            "address": self._address,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            required_field(data, "name"),
            required_field(data, "capacity"),
            data.get("address", ""),
        )

    def __repr__(self) -> str:
        return f"Venue({self._name!r}, capacity={self._capacity})"
