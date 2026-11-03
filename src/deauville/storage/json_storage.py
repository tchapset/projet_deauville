"""The festival in a JSON file."""

import json
import os
from pathlib import Path
from typing import Any

from ..artist import Artist
from ..exceptions import FestivalError, StorageError
from ..festival import Festival
from ..performance import Performance
from ..venue import Venue
from .base import Storage


class JsonStorage(Storage):
    """The festival in a JSON file, such as ``data/festival.json``."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Festival:
        """Read the file and build the festival, bound to this storage.

        A missing file, a broken JSON or a broken rule gives a
        :class:`StorageError` with a sentence, never a traceback.
        """
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as error:
            raise StorageError(
                f"Cannot read the data file {self._path}: {error.strerror}."
            ) from error
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise StorageError(
                f"The data file {self._path} is not valid JSON "
                f"(line {error.lineno}, column {error.colno}): {error.msg}."
            ) from error
        try:
            festival = self._build(data)
        except FestivalError as error:
            raise StorageError(
                f"The data file {self._path} is not valid: {error}"
            ) from error
        festival.bind(self)
        return festival

    def save(self, festival: Festival) -> None:
        """Write the whole file at once (a failure never leaves half a file)."""
        data = {
            "name": festival.name,
            "first_day": festival.first_day.isoformat(),
            "last_day": festival.last_day.isoformat(),
            "venues": [venue.to_dict() for venue in festival.venues()],
            "artists": [artist.to_dict() for artist in festival.artists()],
            "performances": [p.to_dict() for p in festival.performances()],
        }
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self._path)
        except OSError as error:
            raise StorageError(
                f"Cannot write the data file {self._path}: {error.strerror}."
            ) from error

    @staticmethod
    def _build(data: Any) -> Festival:
        if not isinstance(data, dict):
            raise StorageError("The file must contain a JSON object.")
        for key in ("name", "first_day", "last_day"):
            if key not in data:
                raise StorageError(f"Missing field '{key}'.")
        festival = Festival(data["name"], data["first_day"], data["last_day"])
        for key, add, build in (
            ("venues", festival.add_venue, Venue.from_dict),
            ("artists", festival.add_artist, Artist.from_dict),
            ("performances", festival.add_performance, Performance.from_dict),
        ):
            items = data.get(key, [])
            if not isinstance(items, list):
                raise StorageError(f"'{key}' must be a list.")
            for item in items:
                add(build(item))
        return festival
