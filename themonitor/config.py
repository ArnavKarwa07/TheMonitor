"""Configuration loader for TheMonitor.

Loads settings from config.yaml with sensible defaults for every field.
Searches for config in: explicit path -> CWD -> project root.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_LOCATIONS = [
    Path.cwd() / "config.yaml",
    _PROJECT_ROOT / "config.yaml",
]


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------
@dataclass
class AppConfig:
    """Top-level application settings."""

    name: str = "Monitor"
    startup_enabled: bool = False


@dataclass
class MonitoringConfig:
    """Capture loop timing."""

    capture_interval_seconds: int = 4
    bad_posture_alert_seconds: int = 45
    cooldown_seconds: int = 300


@dataclass
class PostureConfig:
    """Posture scoring thresholds."""

    good_angle_threshold_degrees: float = 20.0
    fair_angle_threshold_degrees: float = 35.0
    require_shoulders_level: bool = True
    require_forward_head_check: bool = True
    eye_angle_threshold_degrees: float = 15.0
    neck_forward_angle_threshold_degrees: float = 18.0
    camera_index: int = 0


@dataclass
class NotificationConfig:
    """Notification content and behavior."""

    enabled: bool = True
    title: str = "Posture Alert"
    message: str = "You're slouching. Sit upright and align your shoulders."


@dataclass
class StartupConfig:
    """Windows startup behavior."""

    mode: str = "ask_on_login"
    launcher: str = "registry"


@dataclass
class LoggingConfig:
    """Logging settings."""

    level: str = "INFO"
    file: str = "logs/monitor.log"


@dataclass
class HabitItemConfig:
    """Config for a single habit module."""

    enabled: bool = True
    interval_minutes: int = 60


@dataclass
class HabitsConfig:
    """All habit module settings."""

    water: HabitItemConfig = field(default_factory=HabitItemConfig)
    stretch: HabitItemConfig = field(
        default_factory=lambda: HabitItemConfig(interval_minutes=90)
    )
    eye_break: HabitItemConfig = field(
        default_factory=lambda: HabitItemConfig(interval_minutes=20)
    )
    stand_up: HabitItemConfig = field(
        default_factory=lambda: HabitItemConfig(interval_minutes=45)
    )


@dataclass
class MonitorConfig:
    """Root configuration object for Monitor."""

    app: AppConfig = field(default_factory=AppConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    posture: PostureConfig = field(default_factory=PostureConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    startup: StartupConfig = field(default_factory=StartupConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    habits: HabitsConfig = field(default_factory=HabitsConfig)


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------
def _find_config_file(explicit_path: Optional[str] = None) -> Optional[Path]:
    """Locate the config file. Returns None if not found."""
    if explicit_path:
        p = Path(explicit_path)
        if p.is_file():
            return p
        logger.warning("Config file not found at explicit path: %s", explicit_path)
        return None

    for candidate in _DEFAULT_CONFIG_LOCATIONS:
        if candidate.is_file():
            return candidate

    return None


def _safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _build_habit_item(data: dict[str, Any], key: str, default_minutes: int) -> HabitItemConfig:
    """Build a HabitItemConfig from a nested dict."""
    section = _safe_get(data, "habits", key, default={})
    if not isinstance(section, dict):
        section = {}
    return HabitItemConfig(
        enabled=section.get("enabled", True),
        interval_minutes=section.get("interval_minutes", default_minutes),
    )


def load_config(config_path: Optional[str] = None) -> MonitorConfig:
    """Load configuration from YAML, falling back to defaults for missing keys.

    Args:
        config_path: Optional explicit path to a config file.

    Returns:
        A fully populated MonitorConfig instance.
    """
    found = _find_config_file(config_path)
    if found is None:
        logger.info("No config file found, using all defaults.")
        return MonitorConfig()

    logger.info("Loading config from %s", found)
    with open(found, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    app_raw = raw.get("app", {}) or {}
    mon_raw = raw.get("monitoring", {}) or {}
    pos_raw = raw.get("posture", {}) or {}
    not_raw = raw.get("notifications", {}) or {}
    sta_raw = raw.get("startup", {}) or {}
    log_raw = raw.get("logging", {}) or {}

    config = MonitorConfig(
        app=AppConfig(
            name=app_raw.get("name", "Monitor"),
            startup_enabled=app_raw.get("startup_enabled", False),
        ),
        monitoring=MonitoringConfig(
            capture_interval_seconds=mon_raw.get("capture_interval_seconds", 4),
            bad_posture_alert_seconds=mon_raw.get("bad_posture_alert_seconds", 45),
            cooldown_seconds=mon_raw.get("cooldown_seconds", 300),
        ),
        posture=PostureConfig(
            good_angle_threshold_degrees=pos_raw.get("good_angle_threshold_degrees", 20.0),
            fair_angle_threshold_degrees=pos_raw.get("fair_angle_threshold_degrees", 35.0),
            require_shoulders_level=pos_raw.get("require_shoulders_level", True),
            require_forward_head_check=pos_raw.get("require_forward_head_check", True),
            eye_angle_threshold_degrees=pos_raw.get("eye_angle_threshold_degrees", 15.0),
            neck_forward_angle_threshold_degrees=pos_raw.get(
                "neck_forward_angle_threshold_degrees", 18.0
            ),
            camera_index=pos_raw.get("camera_index", 0),
        ),
        notifications=NotificationConfig(
            enabled=not_raw.get("enabled", True),
            title=not_raw.get("title", "Posture Alert"),
            message=not_raw.get(
                "message",
                "You're slouching. Sit upright and align your shoulders.",
            ),
        ),
        startup=StartupConfig(
            mode=sta_raw.get("mode", "ask_on_login"),
            launcher=sta_raw.get("launcher", "registry"),
        ),
        logging=LoggingConfig(
            level=log_raw.get("level", "INFO"),
            file=log_raw.get("file", "logs/monitor.log"),
        ),
        habits=HabitsConfig(
            water=_build_habit_item(raw, "water", 60),
            stretch=_build_habit_item(raw, "stretch", 90),
            eye_break=_build_habit_item(raw, "eye_break", 20),
            stand_up=_build_habit_item(raw, "stand_up", 45),
        ),
    )

    _validate(config)
    return config


def _validate(config: MonitorConfig) -> None:
    """Log warnings for suspect values. Does not raise."""
    if config.monitoring.capture_interval_seconds < 1:
        logger.warning(
            "capture_interval_seconds=%d is very low — CPU usage may spike.",
            config.monitoring.capture_interval_seconds,
        )
    if config.monitoring.bad_posture_alert_seconds < 5:
        logger.warning(
            "bad_posture_alert_seconds=%d is very short — expect frequent alerts.",
            config.monitoring.bad_posture_alert_seconds,
        )
    if config.monitoring.cooldown_seconds < 30:
        logger.warning(
            "cooldown_seconds=%d is very short — notifications may feel spammy.",
            config.monitoring.cooldown_seconds,
        )


def setup_logging(config: LoggingConfig) -> None:
    """Configure the root logger based on config settings."""
    log_dir = Path(config.file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, config.level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(config.file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def save_config(config: MonitorConfig, config_path: Optional[str] = None) -> None:
    """Save the configuration to a YAML file, maintaining structure."""
    found = _find_config_file(config_path) or _DEFAULT_CONFIG_LOCATIONS[0]
    
    from dataclasses import asdict
    data = asdict(config)
    
    with open(found, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
