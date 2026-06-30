"""Habits module for TheMonitor — periodic wellness reminders."""

from themonitor.habits.base import Habit
from themonitor.habits.eye_break import EyeBreakReminder
from themonitor.habits.stretch import StretchReminder
from themonitor.habits.water import WaterReminder
from themonitor.habits.stand_up import StandUpReminder

__all__ = ["Habit", "WaterReminder", "StretchReminder", "EyeBreakReminder", "StandUpReminder"]
