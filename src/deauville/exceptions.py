"""Errors of the festival.

Every broken rule raises a subclass of :class:`FestivalError`. The message is
a sentence a festival organiser can read. The subclass tells the caller *which
kind* of rule was broken, so the web API can choose a status code without the
model knowing anything about HTTP.
"""


class FestivalError(Exception):
    """Base class of every error raised because of a festival rule."""


class NotFoundError(FestivalError):
    """An artist, a venue or a performance does not exist."""


class ConflictError(FestivalError):
    """The request is valid, but clashes with the current state."""


class AlreadyExistsError(ConflictError):
    """An artist or a venue with the same identifier already exists."""


class VenueBusyError(ConflictError):
    """The venue is used by another performance (or too close to it)."""


class ArtistBusyError(ConflictError):
    """The artist is on stage in another performance (or too close to it)."""


class OutsideFestivalError(ConflictError):
    """The performance does not belong to a day of the festival."""


class WorkshopFullError(ConflictError):
    """A workshop has no place left."""


class InvalidValueError(FestivalError):
    """A value breaks a rule: empty name, duration out of range..."""


class StorageError(FestivalError):
    """The data file cannot be read, written, or contains broken data."""
