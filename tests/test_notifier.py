"""Tests for notification throttling and cooldown."""

from unittest.mock import MagicMock, patch

import pytest

from themonitor.notifications.notifier import Notifier


@pytest.fixture
def _mock_winotify():
    """Patch winotify.Notification to prevent actual desktop toasts."""
    with patch("themonitor.notifications.notifier.winotify") as mock_wn:
        mock_toast = MagicMock()
        mock_wn.Notification.return_value = mock_toast
        yield mock_wn


def test_should_notify_initially():
    """Brand-new notifier should be ready to send immediately."""
    n = Notifier(cooldown_seconds=60)
    assert n.should_notify() is True


def test_notify_sends_and_returns_true(_mock_winotify):
    """First notify() call should succeed."""
    n = Notifier(cooldown_seconds=60)
    assert n.notify() is True


def test_cooldown_prevents_second_notification(_mock_winotify):
    """Immediate second call should be blocked by cooldown."""
    n = Notifier(cooldown_seconds=300)
    assert n.notify() is True
    assert n.notify() is False


def test_cooldown_zero_allows_repeat(_mock_winotify):
    """With cooldown=0, consecutive calls both succeed."""
    n = Notifier(cooldown_seconds=0)
    assert n.notify() is True
    assert n.notify() is True


def test_disabled_notifier():
    """Disabled notifier should never send."""
    n = Notifier(enabled=False)
    assert n.should_notify() is False
    assert n.notify() is False


def test_reset_cooldown(_mock_winotify):
    """reset_cooldown() should allow immediate re-notification."""
    n = Notifier(cooldown_seconds=9999)
    n.notify()
    assert n.should_notify() is False

    n.reset_cooldown()
    assert n.should_notify() is True
