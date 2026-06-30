"""Desktop notification delivery for TheMonitor."""

import logging
import time
from typing import Optional

try:
    import winotify

    _WINOTIFY_AVAILABLE = True
except ImportError:
    _WINOTIFY_AVAILABLE = False

logger = logging.getLogger(__name__)


class Notifier:
    """Sends Windows desktop notifications with a configurable cooldown."""

    def __init__(
        self,
        enabled: bool = True,
        title: str = "Posture Alert",
        message: str = "You're slouching. Sit upright and align your shoulders.",
        cooldown_seconds: int = 300,
    ) -> None:
        self.enabled: bool = enabled
        self.title: str = title
        self.message: str = message
        self.cooldown_seconds: int = cooldown_seconds
        self._last_notification_time: float = 0.0

    def should_notify(self) -> bool:
        """Return True if notifications are enabled and the cooldown has elapsed."""
        return self.enabled and (
            time.time() - self._last_notification_time >= self.cooldown_seconds
        )

    def notify(self, details: Optional[dict] = None) -> bool:
        """Send a desktop notification if the cooldown has elapsed.

        Args:
            details: Optional extra context (currently unused, reserved for future use).

        Returns:
            True if a notification was sent, False otherwise.
        """
        if not self.should_notify():
            return False

        if not _WINOTIFY_AVAILABLE:
            logger.warning(
                "winotify is not available; notification suppressed."
            )
            return False

        toast = winotify.Notification(
            app_id="TheMonitor",
            title=self.title,
            msg=self.message,
            duration="short",
        )
        toast.show()
        self._last_notification_time = time.time()
        return True

    def reset_cooldown(self) -> None:
        """Reset the cooldown so the next call to ``notify`` fires immediately."""
        self._last_notification_time = 0.0
