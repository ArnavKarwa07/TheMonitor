"""Startup registration module for TheMonitor."""

from themonitor.startup.launcher import (
    disable_startup,
    enable_startup,
    is_startup_enabled,
)

__all__ = ["enable_startup", "disable_startup", "is_startup_enabled"]
