"""Where the festival is kept.

:class:`Storage` is the contract. The rest of the program only knows it, so
moving from a JSON file to a database means writing another subclass and
changing nothing else (the model, the command line and the API stay as they
are).
"""

from abc import ABC, abstractmethod

from ..festival import Festival


class Storage(ABC):
    """Loads and saves a whole festival."""

    @abstractmethod
    def load(self) -> Festival:
        """Read the festival; every rule is checked again."""

    @abstractmethod
    def save(self, festival: Festival) -> None:
        """Write the festival."""
