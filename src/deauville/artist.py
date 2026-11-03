"""A comedian, host or teacher."""

from typing import Any, Self

from .exceptions import InvalidValueError
from .utils import clean_name, required_field, slugify


class Artist:
    """A comedian, host or teacher."""

    def __init__(self, name: str, bio: str = "", photo_url: str = "") -> None:
        self._name = clean_name(name, "Artist name")
        self._slug = slugify(self._name)
        if not isinstance(bio, str) or not isinstance(photo_url, str):
            raise InvalidValueError("Artist bio and photo must be texts.")
        self._bio = bio.strip()
        self._photo_url = photo_url.strip()

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def bio(self) -> str:
        return self._bio

    @property
    def photo_url(self) -> str:
        return self._photo_url

    def to_dict(self) -> dict[str, Any]:
        """Fields saved in the data file."""
        return {"name": self._name, "bio": self._bio, "photo_url": self._photo_url}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            required_field(data, "name"), data.get("bio", ""), data.get("photo_url", "")
        )

    def __repr__(self) -> str:
        return f"Artist({self._name!r})"
