"""Background monitoring daemon for TheMonitor.

Owns the main loop: capture frame → analyze posture → notify if sustained bad.
Manages PID file, signal handling, and graceful shutdown.
"""

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from themonitor.config import MonitorConfig, load_config, setup_logging
from themonitor.habits.base import Habit
from themonitor.habits.eye_break import EyeBreakReminder
from themonitor.habits.stretch import StretchReminder
from themonitor.habits.water import WaterReminder
from themonitor.habits.stand_up import StandUpReminder
from themonitor.notifications.notifier import Notifier
from themonitor.posture.detector import PostureDetector
from themonitor.posture.rules import PostureRules, PostureScore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PID file helpers
# ---------------------------------------------------------------------------
_PID_DIR = Path.home() / ".monitor"
_PID_FILE = _PID_DIR / "daemon.pid"


def _write_pid() -> None:
    """Write the current process ID to the PID file."""
    _PID_DIR.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    """Remove the PID file if it exists."""
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def read_pid() -> Optional[int]:
    """Read the daemon PID from the PID file.

    Returns:
        The PID as an int, or None if the file doesn't exist or is invalid.
    """
    try:
        text = _PID_FILE.read_text(encoding="utf-8").strip()
        return int(text)
    except (FileNotFoundError, ValueError):
        return None


def is_daemon_running() -> bool:
    """Check if the daemon process is currently alive."""
    pid = read_pid()
    if pid is None:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            is_active = (exit_code.value == 259)  # STILL_ACTIVE
            ctypes.windll.kernel32.CloseHandle(handle)
            if not is_active:
                _remove_pid()
            return is_active
        else:
            _remove_pid()
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            # Process not found — stale PID file
            _remove_pid()
            return False



# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------
class Daemon:
    """The main monitoring daemon."""

    def __init__(self, config: Optional[MonitorConfig] = None) -> None:
        self._config = config or load_config()
        self._running = False
        self._detector: Optional[PostureDetector] = None
        self._notifier: Optional[Notifier] = None
        self._habits: list[Habit] = []

    def run(self) -> None:
        """Start the daemon main loop. Blocks until stopped."""
        setup_logging(self._config.logging)
        logger.info("Monitor daemon starting (PID %d)", os.getpid())
        _write_pid()

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        # Initialize components
        self._notifier = Notifier(
            enabled=self._config.notifications.enabled,
            title=self._config.notifications.title,
            message=self._config.notifications.message,
            cooldown_seconds=self._config.monitoring.cooldown_seconds,
        )

        rules = PostureRules(
            good_angle_threshold_degrees=self._config.posture.good_angle_threshold_degrees,
            fair_angle_threshold_degrees=self._config.posture.fair_angle_threshold_degrees,
            eye_angle_threshold_degrees=self._config.posture.eye_angle_threshold_degrees,
            neck_forward_angle_threshold_degrees=self._config.posture.neck_forward_angle_threshold_degrees,
            require_shoulders_level=self._config.posture.require_shoulders_level,
            require_forward_head_check=self._config.posture.require_forward_head_check,
        )

        self._detector = PostureDetector(
            rules=rules,
            camera_index=self._config.posture.camera_index,
        )

        # Initialize habit modules
        self._init_habits()

        # Open camera
        if not self._detector.open():
            logger.error("Cannot open webcam. Daemon will exit.")
            _remove_pid()
            sys.exit(1)

        self._running = True
        logger.info(
            "Monitoring started. Checking every %ds, alert after %ds of bad posture.",
            self._config.monitoring.capture_interval_seconds,
            self._config.monitoring.bad_posture_alert_seconds,
        )

        try:
            self._main_loop()
        finally:
            self._shutdown()

    def _main_loop(self) -> None:
        """The core capture-analyze-notify loop."""
        interval = self._config.monitoring.capture_interval_seconds
        alert_threshold = self._config.monitoring.bad_posture_alert_seconds

        while self._running:
            # --- Posture check ---
            result = self._detector.check()

            if result is not None and result.landmarks_found:
                if result.score == PostureScore.BAD:
                    duration = self._detector.bad_posture_duration
                    if duration >= alert_threshold:
                        sent = self._notifier.notify(result.details)
                        if sent:
                            logger.info(
                                "Posture alert sent after %.0fs of bad posture.",
                                duration,
                            )
                            # Reset tracking so we don't spam on the next cycle
                            self._detector.reset_tracking()
                elif result.score == PostureScore.GOOD:
                    pass  # Tracking reset happens inside detector

            # --- Habit checks ---
            now = time.time()
            for habit in self._habits:
                message = habit.check(now)
                if message:
                    self._send_habit_notification(message)

            # Sleep until next check
            time.sleep(interval)

    def _init_habits(self) -> None:
        """Initialize enabled habit modules from config."""
        habits_cfg = self._config.habits

        self._habits = [
            WaterReminder(
                enabled=habits_cfg.water.enabled,
                interval_minutes=habits_cfg.water.interval_minutes,
            ),
            StretchReminder(
                enabled=habits_cfg.stretch.enabled,
                interval_minutes=habits_cfg.stretch.interval_minutes,
            ),
            EyeBreakReminder(
                enabled=habits_cfg.eye_break.enabled,
                interval_minutes=habits_cfg.eye_break.interval_minutes,
            ),
            StandUpReminder(
                enabled=habits_cfg.stand_up.enabled,
                interval_minutes=habits_cfg.stand_up.interval_minutes,
            ),
        ]

        active = [h.__class__.__name__ for h in self._habits if h.is_enabled()]
        if active:
            logger.info("Active habits: %s", ", ".join(active))
        else:
            logger.info("No habits enabled.")

    def _send_habit_notification(self, message: str) -> None:
        """Send a habit reminder notification."""
        if self._notifier is None:
            return
        # Create a temporary notifier with no cooldown for habit messages
        # (habits manage their own timing)
        from themonitor.notifications.notifier import Notifier as _Notifier

        habit_notifier = _Notifier(
            enabled=self._config.notifications.enabled,
            title="Monitor Reminder",
            message=message,
            cooldown_seconds=0,
        )
        habit_notifier.notify()

    def _handle_signal(self, signum: int, _frame: object) -> None:
        """Handle termination signals."""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, shutting down...", sig_name)
        self._running = False

    def _shutdown(self) -> None:
        """Clean up all resources."""
        if self._detector is not None:
            self._detector.close()
        _remove_pid()
        logger.info("Monitor daemon stopped.")


def run_daemon(config_path: Optional[str] = None) -> None:
    """Entry point for starting the daemon."""
    config = load_config(config_path)
    daemon = Daemon(config)
    daemon.run()
