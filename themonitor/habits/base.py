"""Abstract base class for periodic wellness habits."""

from abc import ABC, abstractmethod
from typing import Optional


class Habit(ABC):
    """Base class for periodic wellness habits."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether this habit is active."""
        ...

    @abstractmethod
    def check(self, current_time: float) -> Optional[str]:
        """Return notification message if habit should fire, else None."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset the habit timer."""
        ...
