"""Tests for habit modules.

Uses explicit timestamps for deterministic behavior.
"""

import pytest

from themonitor.habits.eye_break import EyeBreakReminder
from themonitor.habits.stretch import StretchReminder
from themonitor.habits.water import WaterReminder
from themonitor.habits.stand_up import StandUpReminder


# ---------------------------------------------------------------------------
# Water reminder
# ---------------------------------------------------------------------------
def test_water_disabled_returns_none():
    """Disabled habit should never fire."""
    h = WaterReminder(enabled=False)
    assert h.check(1000.0) is None


def test_water_enabled_fires_on_first_check():
    """First check should fire since last_reminder_time starts at 0."""
    h = WaterReminder(enabled=True, interval_minutes=1)
    msg = h.check(100.0)  # 100 - 0 = 100 >= 60
    assert msg is not None
    assert "water" in msg.lower()


def test_water_respects_interval():
    """Should fire at correct intervals and stay silent in between."""
    h = WaterReminder(enabled=True, interval_minutes=1)

    msg1 = h.check(100.0)  # Should fire (100 - 0 >= 60)
    assert msg1 is not None

    msg2 = h.check(110.0)  # Should NOT fire (110 - 100 = 10 < 60)
    assert msg2 is None

    msg3 = h.check(200.0)  # Should fire (200 - 100 = 100 >= 60)
    assert msg3 is not None


# ---------------------------------------------------------------------------
# Stretch reminder
# ---------------------------------------------------------------------------
def test_stretch_disabled_returns_none():
    """Disabled stretch habit should never fire."""
    h = StretchReminder(enabled=False)
    assert h.check(1000.0) is None


def test_stretch_fires():
    """Stretch reminder should fire after interval elapses."""
    h = StretchReminder(enabled=True, interval_minutes=1)
    msg = h.check(100.0)
    assert msg is not None
    assert "stretch" in msg.lower()


# ---------------------------------------------------------------------------
# Eye break reminder
# ---------------------------------------------------------------------------
def test_eye_break_disabled_returns_none():
    """Disabled eye break habit should never fire."""
    h = EyeBreakReminder(enabled=False)
    assert h.check(1000.0) is None


def test_eye_break_fires():
    """Eye break reminder should fire after interval elapses."""
    h = EyeBreakReminder(enabled=True, interval_minutes=1)
    msg = h.check(100.0)
    assert msg is not None
    assert "eyes" in msg.lower()


# ---------------------------------------------------------------------------
# Reset behavior
# ---------------------------------------------------------------------------
def test_habit_reset():
    """After reset(), the next check should fire immediately."""
    h = WaterReminder(enabled=True, interval_minutes=60)

    msg1 = h.check(4000.0)  # Fire first time
    assert msg1 is not None

    msg2 = h.check(4010.0)  # Too soon — should not fire
    assert msg2 is None

    h.reset()

    msg3 = h.check(4010.0)  # After reset, should fire (4010 - 0 >= 3600)
    assert msg3 is not None


# ---------------------------------------------------------------------------
# Stand up reminder
# ---------------------------------------------------------------------------
def test_stand_up_disabled_returns_none():
    """Disabled stand up habit should never fire."""
    h = StandUpReminder(enabled=False)
    assert h.check(1000.0) is None


def test_stand_up_fires():
    """Stand up reminder should fire after interval elapses."""
    h = StandUpReminder(enabled=True, interval_minutes=1)
    msg = h.check(100.0)
    assert msg is not None
    assert "stand up" in msg.lower()


def test_habit_defaults():
    """Verify that habit reminders default to enabled=True in their constructors."""
    assert WaterReminder().is_enabled() is True
    assert StretchReminder().is_enabled() is True
    assert EyeBreakReminder().is_enabled() is True
    assert StandUpReminder().is_enabled() is True

