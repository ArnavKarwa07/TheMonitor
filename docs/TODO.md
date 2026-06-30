# Todo List

This page tracks the current work for Monitor in a checklist format.

## Done

- [x] Documentation baseline (README, Architecture, Configuration, Troubleshooting)
- [x] Project structure and packaging (`pyproject.toml` with `monitor` script)
- [x] Configuration loader and saver with YAML + defaults + validation
- [x] CLI commands: `start`, `stop`, `status`, `startup`, `ui`, `shortcut`
- [x] Posture detection engine (MediaPipe Pose, `model_complexity=0`)
- [x] Posture rules: shoulder alignment, forward head, eye/head tilt
- [x] Three-state scoring (GOOD, FAIR, BAD)
- [x] Sustained bad posture tracking (~45 seconds)
- [x] Windows desktop notifications via `winotify`
- [x] Notification cooldown (5 minutes default)
- [x] Background daemon with PID file management
- [x] Windows startup registration via Registry (`pythonw.exe -m themonitor start`)
- [x] Proper Application GUI built in Tkinter & OpenCV:
    - [x] Dashboard (Daemon controls, status indicators, live camera preview)
    - [x] Live posture alignment skeleton rendering (Green/Yellow/Red joints and lines)
    - [x] Wellness Habits config management (Toggles and intervals)
    - [x] Settings threshold configs (Toggles and parameter forms)
    - [x] Create desktop shortcut action (`Monitor GUI.lnk`)
- [x] Periodic wellness habits (enabled by default):
    - [x] Drink water reminder
    - [x] Stretch reminder
    - [x] Eye break reminder (20-20-20 rule)
    - [x] Stand-up reminder
- [x] Test suite for config, rules, detector, notifier, habits (pytest)

## Future Ideas

- [ ] Add posture calibration (personalized baseline button in GUI)
- [ ] Add debug snapshot mode (opt-in frame saves for troubleshooting)
- [ ] Improve forward-head detection for side-on camera angles
