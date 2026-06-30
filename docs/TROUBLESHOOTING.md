# Troubleshooting

This page captures common problems and the first checks to perform when Monitor is implemented and running.

## Webcam Not Detected

Symptoms:

- The daemon cannot open the camera.
- Posture checks never start.

Checks:

- Confirm another app is not already using the webcam.
- Verify the OS camera privacy settings allow desktop apps.
- Try a different camera index if the machine has multiple cameras.

## Notifications Do Not Appear

Symptoms:

- The daemon detects bad posture, but the user sees no alert.

Checks:

- Confirm Windows notification permissions are enabled.
- Verify the notifier library is installed correctly.
- Check whether notification cooldowns are blocking repeated alerts.

## Too Many False Positives

Symptoms:

- Alerts appear even when the user feels seated normally.

Checks:

- Increase the bad posture threshold.
- Increase the alert delay.
- Relax shoulder and head-angle rules.
- Relax eye-angle rules if gaze tracking is too strict.
- Make sure the webcam view is stable and centered.

## CPU Usage Feels Too High

Symptoms:

- The app consumes more resources than expected.

Checks:

- Confirm the posture loop is sampling every few seconds instead of streaming continuously.
- Reduce capture frequency.
- Keep image processing work small and local.
- Remove any nonessential checks that are not needed in V1.

## Startup Behavior Is Wrong

Symptoms:

- The app starts when it should not, or does not start when it should.

Checks:

- Review the startup setting in `config.yaml`.
- Confirm the launcher mechanism is Task Scheduler or Startup Folder as documented.
- Check whether the user skipped the first login prompt.

## Logging Is Missing

Symptoms:

- No runtime trace appears when something fails.

Checks:

- Confirm the log directory exists.
- Confirm file logging is enabled.
- Check file permissions for the log path.
- Verify that debug-only habits have not been enabled by default.
