"""Tests for configuration loading and defaults."""

import logging

import pytest

from themonitor.config import MonitorConfig, load_config


def test_load_defaults_when_no_file():
    """Config with nonexistent path should return all defaults."""
    cfg = load_config("/nonexistent/path/config.yaml")

    assert cfg.monitoring.capture_interval_seconds == 4
    assert cfg.monitoring.bad_posture_alert_seconds == 45
    assert cfg.monitoring.cooldown_seconds == 300
    assert cfg.posture.good_angle_threshold_degrees == 20.0
    assert cfg.posture.fair_angle_threshold_degrees == 35.0
    assert cfg.posture.eye_angle_threshold_degrees == 15.0
    assert cfg.posture.require_shoulders_level is True
    assert cfg.posture.require_forward_head_check is True
    assert cfg.notifications.enabled is True
    assert cfg.notifications.title == "Posture Alert"
    assert cfg.startup.launcher == "registry"
    assert cfg.habits.water.enabled is True
    assert cfg.habits.water.interval_minutes == 60
    assert cfg.habits.stand_up.enabled is True
    assert cfg.habits.stand_up.interval_minutes == 45


def test_load_from_yaml(tmp_path):
    """Custom YAML values override defaults; missing keys fall back."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """\
monitoring:
  capture_interval_seconds: 10
  bad_posture_alert_seconds: 60
posture:
  good_angle_threshold_degrees: 25
notifications:
  title: "Custom Title"
""",
        encoding="utf-8",
    )

    cfg = load_config(str(config_file))

    # Custom values
    assert cfg.monitoring.capture_interval_seconds == 10
    assert cfg.monitoring.bad_posture_alert_seconds == 60
    assert cfg.posture.good_angle_threshold_degrees == 25.0
    assert cfg.notifications.title == "Custom Title"

    # Defaults for missing keys
    assert cfg.monitoring.cooldown_seconds == 300
    assert cfg.posture.fair_angle_threshold_degrees == 35.0
    assert cfg.notifications.enabled is True


def test_partial_yaml(tmp_path):
    """YAML with only one section; other sections use defaults."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """\
monitoring:
  capture_interval_seconds: 7
""",
        encoding="utf-8",
    )

    cfg = load_config(str(config_file))

    assert cfg.monitoring.capture_interval_seconds == 7
    assert cfg.posture.good_angle_threshold_degrees == 20.0
    assert cfg.notifications.enabled is True
    assert cfg.habits.stretch.interval_minutes == 90


def test_empty_yaml(tmp_path):
    """Empty YAML file should produce all defaults."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("", encoding="utf-8")

    cfg = load_config(str(config_file))

    assert cfg.monitoring.capture_interval_seconds == 4
    assert cfg.posture.good_angle_threshold_degrees == 20.0
    assert cfg.notifications.enabled is True


def test_validation_warnings(tmp_path, caplog):
    """Suspect values should log warnings."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """\
monitoring:
  capture_interval_seconds: 0
  bad_posture_alert_seconds: 2
  cooldown_seconds: 10
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        cfg = load_config(str(config_file))

    assert cfg.monitoring.capture_interval_seconds == 0
    assert "capture_interval_seconds" in caplog.text
    assert "bad_posture_alert_seconds" in caplog.text
    assert "cooldown_seconds" in caplog.text
