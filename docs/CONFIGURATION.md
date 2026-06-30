# Configuration

Monitor is configured through a single `config.yaml` file so the user can tune posture sensitivity, eye-angle rules, notification behavior, and startup preferences without touching code. You can also view and edit all these settings directly inside the **Configurations** and **Wellness Habits** tabs of the GUI.

## Goals

- Keep defaults sensible for most users.
- Make posture detection thresholds easy to tune.
- Separate runtime settings from implementation details.
- Provide real-time saving and loading of configurations.

## Example Configuration

```yaml
app:
  name: Monitor
  startup_enabled: false

monitoring:
  capture_interval_seconds: 4
  bad_posture_alert_seconds: 45
  cooldown_seconds: 300

posture:
  good_angle_threshold_degrees: 20
  fair_angle_threshold_degrees: 35
  require_shoulders_level: true
  require_forward_head_check: true
  eye_angle_threshold_degrees: 15
  neck_forward_angle_threshold_degrees: 18
  camera_index: 0

notifications:
  enabled: true
  title: "Posture Alert"
  message: "You're slouching. Sit upright and align your shoulders."

startup:
  mode: "ask_on_login"
  launcher: "registry"

logging:
  level: "INFO"
  file: "logs/monitor.log"

habits:
  water:
    enabled: true
    interval_minutes: 60
  stretch:
    enabled: true
    interval_minutes: 90
  eye_break:
    enabled: true
    interval_minutes: 20
  stand_up:
    enabled: true
    interval_minutes: 45
```

## Settings Reference

### app.name

Human-readable application name.

### app.startup_enabled

Whether the app should be allowed to auto-start on login.

### monitoring.capture_interval_seconds

How long (in seconds) the background daemon waits between webcam checks.

### monitoring.bad_posture_alert_seconds

How long poor posture must persist before notifying the user.

### monitoring.cooldown_seconds

Minimum time (in seconds) between repeated alerts.

### posture.good_angle_threshold_degrees

Maximum angle that still counts as good posture.

### posture.fair_angle_threshold_degrees

Angle range used for a transitional or warning state.

### posture.require_shoulders_level

Whether shoulder alignment should be part of the decision.

### posture.require_forward_head_check

Whether forward head position should be part of the decision.

### posture.eye_angle_threshold_degrees

Maximum eye or gaze angle before the view is treated as strained or too forward.

### posture.neck_forward_angle_threshold_degrees

Threshold used to catch the head moving too far forward relative to the shoulders.

### posture.camera_index

Webcam device index used for OpenCV capture (0 is usually the default camera).

### notifications.enabled

Master switch for desktop notifications.

### notifications.title

Title used for alerts.

### notifications.message

Main alert message shown to the user.

### startup.mode

Startup strategy for Windows login.

### startup.launcher

Launcher mechanism used to start the daemon (e.g. `registry`).

### logging.level

Logging verbosity for the application (DEBUG, INFO, WARNING, ERROR).

### logging.file

Log file path for runtime diagnostics.

### habits.water

Settings for the periodic hydration reminder.

- `enabled`: Toggle this reminder.
- `interval_minutes`: Minutes between hydration alerts.

### habits.stretch

Settings for the periodic stretch reminder.

- `enabled`: Toggle this reminder.
- `interval_minutes`: Minutes between stretch alerts.

### habits.eye_break

Settings for the periodic eye rest (20-20-20 rule) reminder.

- `enabled`: Toggle this reminder.
- `interval_minutes`: Minutes between eye break alerts.

### habits.stand_up

Settings for the periodic standing reminder.

- `enabled`: Toggle this reminder.
- `interval_minutes`: Minutes between stand up alerts.
