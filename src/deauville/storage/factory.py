"""Choose the storage that fits a data file."""

from pathlib import Path

from .base import Storage
from .json_storage import JsonStorage
from .sqlite_storage import SqliteStorage


def open_storage(path: str | Path) -> Storage:
    """The storage that fits a path: SQLite for ``.db``/``.sqlite``, else JSON."""
    if Path(path).suffix.lower() in (".db", ".sqlite", ".sqlite3"):
        return SqliteStorage(path)
    return JsonStorage(path)
