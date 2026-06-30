"""Windows startup registration via the Windows Registry."""

import logging
import sys
from pathlib import Path

try:
    import winreg

    _WINREG_AVAILABLE = True
except ImportError:
    _WINREG_AVAILABLE = False

logger = logging.getLogger(__name__)

_APP_NAME: str = "Monitor"
_REG_KEY_PATH: str = r"Software\Microsoft\Windows\CurrentVersion\Run"


def enable_startup() -> bool:
    """Register Monitor to run at Windows startup.

    Sets the ``Monitor`` value under
    ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`` to launch
    via ``pythonw.exe -m themonitor start``.

    Returns:
        True on success, False on failure.
    """
    if not _WINREG_AVAILABLE:
        logger.warning("winreg is not available; cannot enable startup.")
        return False

    try:
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        command = f'"{pythonw}" -m themonitor start'

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        logger.info("Startup entry created: %s", command)
        return True
    except OSError:
        logger.exception("Failed to enable startup registration.")
        return False


def disable_startup() -> bool:
    """Remove Monitor from Windows startup.

    Returns:
        True on success or if the entry was already absent, False on failure.
    """
    if not _WINREG_AVAILABLE:
        logger.warning("winreg is not available; cannot disable startup.")
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.DeleteValue(key, _APP_NAME)
        except FileNotFoundError:
            logger.info("Startup entry already absent.")
        winreg.CloseKey(key)
        return True
    except OSError:
        logger.exception("Failed to disable startup registration.")
        return False


def is_startup_enabled() -> bool:
    """Check whether Monitor is registered to run at Windows startup."""
    if not _WINREG_AVAILABLE:
        logger.warning("winreg is not available; cannot query startup status.")
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_QUERY_VALUE,
        )
        try:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        logger.exception("Failed to query startup registration.")
        return False


def get_desktop_path() -> Path:
    """Query the registry for the Desktop path, with fallbacks.

    Queries HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders
    for the "Desktop" value, expands environment variables, and falls back to:
    1. USERPROFILE\\OneDrive\\Desktop
    2. USERPROFILE\\OneDrive - Personal\\Desktop
    3. USERPROFILE\\Desktop
    4. Path.home() / "Desktop"
    """
    import os
    from pathlib import Path

    if _WINREG_AVAILABLE:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
                0,
                winreg.KEY_QUERY_VALUE,
            )
            try:
                val, val_type = winreg.QueryValueEx(key, "Desktop")
                expanded = os.path.expandvars(str(val))
                path = Path(expanded)
                if path.exists() and path.is_dir():
                    return path
            finally:
                winreg.CloseKey(key)
        except OSError:
            logger.debug("Failed to query registry for Desktop path.")

    # Fallbacks
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        up_path = Path(user_profile)
        for fb in [
            up_path / "OneDrive" / "Desktop",
            up_path / "OneDrive - Personal" / "Desktop",
            up_path / "Desktop",
        ]:
            if fb.exists() and fb.is_dir():
                return fb

    return Path.home() / "Desktop"


def create_desktop_shortcut() -> bool:
    """Create a Windows desktop shortcut for the Monitor GUI.
    
    Returns:
        True on success, False on failure.
    """
    import subprocess
    import sys
    from pathlib import Path
    
    try:
        # We target pythonw.exe to run the module silently
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        arguments = "-m themonitor ui"
        
        desktop_path = get_desktop_path()
        logo_path = (Path(__file__).resolve().parent.parent.parent / "logo.ico").resolve()
        
        # Powershell command to build a shortcut
        ps_cmd = (
            f'$DesktopPath = "{desktop_path}"; '
            f'$WshShell = New-Object -ComObject WScript.Shell; '
            f'$Shortcut = $WshShell.CreateShortcut("$DesktopPath\\Monitor GUI.lnk"); '
            f'$Shortcut.TargetPath = "{pythonw}"; '
            f'$Shortcut.Arguments = "{arguments}"; '
            f'$Shortcut.Description = "Monitor Posture Assistant GUI"; '
            f'$Shortcut.WorkingDirectory = "{Path.cwd()}"; '
            f'$Shortcut.IconLocation = "{logo_path}"; '
            f'$Shortcut.Save()'
        )
        
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            check=True,
            capture_output=True
        )
        logger.info("Desktop shortcut 'Monitor GUI.lnk' created.")
        return True
    except Exception:
        logger.exception("Failed to create desktop shortcut.")
        return False

