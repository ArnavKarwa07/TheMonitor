# Monitor

A local-first, ultra-lightweight desktop posture monitoring assistant and GUI. Runs in the background, checks your posture every few seconds via webcam, and gently notifies you only when bad posture persists long enough to matter. It also features a sleek desktop GUI for real-time camera alignment/calibration and wellness habits configuration.

**No cloud. No uploads. No continuous streaming. Just quiet, helpful posture checks.**

## Features

- **Sleek Desktop GUI** for real-time posture calibration (green/yellow/red skeleton overlay), start/stop background monitoring, habits toggles, and parameter settings
- **Posture detection** via MediaPipe Pose with three checks: shoulder alignment, forward head, and eye/head tilt
- **Sustained detection** — alerts only after ~45 seconds of bad posture, not on every minor movement
- **Ultra-lightweight** — background daemon samples one frame every 4 seconds, then sleeps
- **Windows notifications** — silent toast alerts, no sounds, no spam
- **Notification throttling** — 5-minute cooldown between alerts
- **Background daemon** — runs invisibly with CLI and GUI control
- **Windows startup** — optional auto-launch on login via Registry
- **Wellness habits** — water, stretch, eye-break, and stand-up reminders (enabled by default)
- **Fully local** — webcam frames are never stored or uploaded

## Quick Start

```bash
# Clone and install
git clone https://github.com/ArnavKarwa07/TheMonitor.git
cd TheMonitor
pip install -e .

# Launch the GUI (opens calibration, settings, habits, and daemon controls)
monitor ui

# Create desktop shortcut for GUI
monitor shortcut

# CLI - Start monitoring daemon in background
monitor start

# CLI - Check status of background daemon
monitor status

# CLI - Stop background daemon
monitor stop
```

## Installation

Requires Python 3.10+ and a webcam.

```bash
pip install -e .
```

This installs:
- `opencv-python` — webcam capture
- `mediapipe` — pose detection
- `winotify` — Windows toast notifications
- `pyyaml` — configuration
- `Pillow` — image conversion for GUI

For development:
```bash
pip install -e ".[dev]"
```

## CLI Commands

| Command | Description |
|---|---|
| `monitor ui` | Launch the calibration & settings GUI |
| `monitor shortcut` | Create a native Windows Desktop Shortcut for the GUI |
| `monitor start` | Launch the background monitoring daemon |
| `monitor stop` | Stop the running daemon |
| `monitor status` | Check if background monitoring is active |
| `monitor startup --enable` | Auto-start Monitor daemon on Windows login |
| `monitor startup --disable` | Remove auto-start registration |

## Configuration

Edit `config.yaml` to tune behavior, or adjust settings directly in the **Configurations** and **Wellness Habits** tabs of the GUI:

```yaml
monitoring:
  capture_interval_seconds: 4      # How often to check (seconds)
  bad_posture_alert_seconds: 45    # How long bad posture must persist
  cooldown_seconds: 300            # Min time between alerts

posture:
  good_angle_threshold_degrees: 20  # Max angle for "good"
  fair_angle_threshold_degrees: 35  # Max angle for "fair"
  eye_angle_threshold_degrees: 15   # Eye tilt threshold
  require_shoulders_level: true
  require_forward_head_check: true
  camera_index: 0

notifications:
  enabled: true
  title: "Posture Alert"
  message: "You're slouching. Sit upright and align your shoulders."

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

## How It Works

1. The daemon wakes every 4 seconds
2. Captures a single webcam frame
3. MediaPipe extracts body landmarks (shoulders, ears, nose, eyes)
4. Three checks run: shoulder tilt, forward head, eye angle
5. Each check scores as GOOD, FAIR, or BAD
6. BAD posture accumulates — alert fires after 45 seconds sustained
7. GOOD posture resets the timer

## Project Structure

```
themonitor/ (package folder)
├── __init__.py          # Package version
├── __main__.py          # python -m themonitor support
├── cli.py               # CLI entry point (start/stop/status/ui)
├── ui.py                # Tkinter GUI (Calibrate, settings, habits)
├── daemon.py            # Background monitoring loop
├── config.py            # Config loader and saver
├── posture/
│   ├── detector.py      # Orchestrates capture → analyze → track
│   ├── mediapipe_engine.py  # MediaPipe landmark extraction
│   └── rules.py         # Pure-function posture scoring
├── notifications/
│   └── notifier.py      # Windows toast + throttling
├── startup/
│   └── launcher.py      # Registry-based startup & shortcut creation
└── habits/
    ├── base.py           # Abstract habit interface
    ├── water.py          # Hydration reminder
    ├── stretch.py        # Stretch reminder
    ├── eye_break.py      # 20-20-20 rule reminder
    └── stand_up.py       # Stand-up reminder
```

## Testing

```bash
pytest tests/ -v
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — component design and data flow
- [Configuration](docs/CONFIGURATION.md) — full settings reference
- [Troubleshooting](docs/TROUBLESHOOTING.md) — common issues and fixes
- [Todo](docs/TODO.md) — planned work

## License

MIT License.
