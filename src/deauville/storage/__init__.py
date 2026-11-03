"""Storages of the festival: the contract, a JSON file and a SQLite database."""

from .base import Storage
from .factory import open_storage
from .json_storage import JsonStorage
from .sqlite_storage import SqliteStorage

__all__ = ["JsonStorage", "SqliteStorage", "Storage", "open_storage"]
