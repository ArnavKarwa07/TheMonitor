"""CLI entry point for Monitor.

Usage:
    monitor start   — launch the background monitoring daemon
    monitor stop    — stop the running daemon
    monitor status  — check if the daemon is running
    monitor startup — manage Windows startup registration
    monitor ui      — launch the graphical user interface
    monitor shortcut— create desktop shortcut for the GUI
"""

import argparse
import os
import subprocess
import sys
import time

from themonitor.daemon import is_daemon_running, read_pid


def _start(args: argparse.Namespace) -> None:
    """Launch the daemon as a detached background process."""
    if is_daemon_running():
        pid = read_pid()
        print(f"Monitor is already running (PID {pid}).")
        return

    # Launch a new Python process running the daemon
    python = sys.executable.replace("python.exe", "pythonw.exe") if sys.platform == "win32" else sys.executable
    # Use the daemon module's run_daemon entry point
    cmd = [python, "-c", "from themonitor.daemon import run_daemon; run_daemon()"]

    # Use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS on Windows
    # so the daemon survives the terminal closing
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )

    try:
        proc = subprocess.Popen(
            cmd,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        # Give the daemon a moment to start and write its PID file
        time.sleep(2.0)

        if is_daemon_running():
            pid = read_pid()
            print(f"Monitor started (PID {pid}).")
        else:
            print(
                "Monitor process launched but may not be running. "
                "Check logs/monitor.log for errors."
            )
    except Exception as e:
        print(f"Failed to start Monitor: {e}")
        sys.exit(1)


def _stop(_args: argparse.Namespace) -> None:
    """Stop the running daemon."""
    if not is_daemon_running():
        print("Monitor is not running.")
        return

    pid = read_pid()
    if pid is None:
        print("Cannot find daemon PID.")
        return

    try:
        if sys.platform == "win32":
            # On Windows, use taskkill for clean termination
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True,
                check=True,
            )
        else:
            import signal
            os.kill(pid, signal.SIGTERM)

        # Wait briefly and verify
        time.sleep(1.0)
        if not is_daemon_running():
            print("Monitor stopped.")
        else:
            print(f"Sent stop signal to PID {pid}. It may take a moment to shut down.")
    except Exception as e:
        print(f"Error stopping Monitor: {e}")
        sys.exit(1)


def _status(_args: argparse.Namespace) -> None:
    """Report daemon status."""
    if is_daemon_running():
        pid = read_pid()
        print(f"Monitor is running (PID {pid}).")
    else:
        print("Monitor is not running.")


def _startup(args: argparse.Namespace) -> None:
    """Manage Windows startup registration."""
    from themonitor.startup.launcher import (
        disable_startup,
        enable_startup,
        is_startup_enabled,
    )

    if args.enable:
        if enable_startup():
            print("Monitor will now start automatically on login.")
        else:
            print("Failed to enable startup. Check logs for details.")
    elif args.disable:
        if disable_startup():
            print("Monitor will no longer start on login.")
        else:
            print("Failed to disable startup. Check logs for details.")
    else:
        # Show current status
        if is_startup_enabled():
            print("Startup: enabled (Monitor will start on login).")
        else:
            print("Startup: disabled.")


def _ui(_args: argparse.Namespace) -> None:
    """Launch the GUI application."""
    from themonitor.ui import run_ui
    run_ui()


def _shortcut(_args: argparse.Namespace) -> None:
    """Create the desktop shortcut."""
    from themonitor.startup.launcher import create_desktop_shortcut
    if create_desktop_shortcut():
        print("Desktop shortcut 'Monitor GUI' created successfully.")
    else:
        print("Failed to create desktop shortcut. Check logs for details.")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="monitor",
        description="Monitor — local-first desktop posture monitoring assistant",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # start
    start_parser = subparsers.add_parser("start", help="Start the monitoring daemon")
    start_parser.add_argument(
        "--config", type=str, default=None, help="Path to config.yaml"
    )
    start_parser.set_defaults(func=_start)

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop the monitoring daemon")
    stop_parser.set_defaults(func=_stop)

    # status
    status_parser = subparsers.add_parser("status", help="Check daemon status")
    status_parser.set_defaults(func=_status)

    # startup
    startup_parser = subparsers.add_parser(
        "startup", help="Manage Windows startup registration"
    )
    startup_group = startup_parser.add_mutually_exclusive_group()
    startup_group.add_argument(
        "--enable", action="store_true", help="Enable auto-start on login"
    )
    startup_group.add_argument(
        "--disable", action="store_true", help="Disable auto-start on login"
    )
    startup_parser.set_defaults(func=_startup)

    # ui
    ui_parser = subparsers.add_parser("ui", help="Start the graphical user interface")
    ui_parser.set_defaults(func=_ui)

    # shortcut
    shortcut_parser = subparsers.add_parser("shortcut", help="Create desktop shortcut for the GUI")
    shortcut_parser.set_defaults(func=_shortcut)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
