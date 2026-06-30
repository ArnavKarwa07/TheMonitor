"""Stretch reminder habit."""

import logging
from typing import Optional

from themonitor.habits.base import Habit

logger = logging.getLogger(__name__)


class StretchReminder(Habit):
    """Reminds the user to stretch at a configurable interval."""

    def __init__(
        self, enabled: bool = True, interval_minutes: int = 90
    ) -> None:
        self._enabled: bool = enabled
        self.interval_minutes: int = interval_minutes
        self._last_reminder_time: float = 0.0

    def is_enabled(self) -> bool:
        """Whether this habit is active."""
        return self._enabled

    def check(self, current_time: float) -> Optional[str]:
        """Return a stretch message if the interval has elapsed, else None."""
        if not self._enabled:
            return None

        if current_time - self._last_reminder_time >= self.interval_minutes * 60:
            self._last_reminder_time = current_time
            return "Time for a quick stretch. Stand up and move around."

        return None

    def reset(self) -> None:
        """Reset the reminder timer."""
        self._last_reminder_time = 0.0
