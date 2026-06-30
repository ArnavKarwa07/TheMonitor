from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from themonitor.startup.launcher import get_desktop_path, create_desktop_shortcut


def test_get_desktop_path_registry_success():
    """Test get_desktop_path when registry query succeeds."""
    with patch("themonitor.startup.launcher._WINREG_AVAILABLE", True), \
         patch("themonitor.startup.launcher.winreg") as mock_winreg, \
         patch("os.path.expandvars", lambda x: x), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.is_dir", return_value=True):
        
        mock_winreg.OpenKey.return_value = MagicMock()
        mock_winreg.QueryValueEx.return_value = ("C:\\Mocked\\Desktop", 1)
        
        path = get_desktop_path()
        assert str(path) == "C:\\Mocked\\Desktop"


def test_get_desktop_path_registry_fails_fallback_onedrive():
    """Test fallback to OneDrive paths when registry query fails."""
    def mock_exists(self):
        return "OneDrive\\Desktop" in str(self)

    def mock_is_dir(self):
        return "OneDrive\\Desktop" in str(self)

    with patch("themonitor.startup.launcher._WINREG_AVAILABLE", False), \
         patch("os.environ", {"USERPROFILE": "C:\\Users\\MockUser"}), \
         patch("pathlib.Path.exists", mock_exists), \
         patch("pathlib.Path.is_dir", mock_is_dir):
        
        path = get_desktop_path()
        assert str(path) == "C:\\Users\\MockUser\\OneDrive\\Desktop"


def test_get_desktop_path_registry_fails_fallback_personal():
    """Test fallback to OneDrive - Personal when registry fails and OneDrive/Desktop does not exist."""
    def mock_exists(self):
        return "OneDrive - Personal\\Desktop" in str(self)

    def mock_is_dir(self):
        return "OneDrive - Personal\\Desktop" in str(self)

    with patch("themonitor.startup.launcher._WINREG_AVAILABLE", False), \
         patch("os.environ", {"USERPROFILE": "C:\\Users\\MockUser"}), \
         patch("pathlib.Path.exists", mock_exists), \
         patch("pathlib.Path.is_dir", mock_is_dir):
        
        path = get_desktop_path()
        assert str(path) == "C:\\Users\\MockUser\\OneDrive - Personal\\Desktop"


def test_get_desktop_path_registry_fails_fallback_local():
    """Test fallback to standard Desktop when others don't exist."""
    def mock_exists(self):
        return "Desktop" in str(self) and "OneDrive" not in str(self)

    def mock_is_dir(self):
        return "Desktop" in str(self) and "OneDrive" not in str(self)

    with patch("themonitor.startup.launcher._WINREG_AVAILABLE", False), \
         patch("os.environ", {"USERPROFILE": "C:\\Users\\MockUser"}), \
         patch("pathlib.Path.exists", mock_exists), \
         patch("pathlib.Path.is_dir", mock_is_dir):
        
        path = get_desktop_path()
        assert str(path) == "C:\\Users\\MockUser\\Desktop"


def test_get_desktop_path_ultimate_fallback():
    """Test fallback to Path.home() / 'Desktop' when no directories exist."""
    with patch("themonitor.startup.launcher._WINREG_AVAILABLE", False), \
         patch("os.environ", {}), \
         patch("pathlib.Path.home", return_value=Path("C:\\Users\\HomeMock")):
        
        path = get_desktop_path()
        assert str(path) == "C:\\Users\\HomeMock\\Desktop"


def test_create_desktop_shortcut_success():
    """Test that create_desktop_shortcut invokes subprocess with correct path."""
    with patch("themonitor.startup.launcher.get_desktop_path", return_value=Path("C:\\Users\\MockUser\\Desktop")), \
         patch("subprocess.run") as mock_run:
        
        res = create_desktop_shortcut()
        assert res is True
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        cmd_list = args[0]
        assert "powershell" in cmd_list
        # verify the command has the mocked desktop path
        assert "C:\\Users\\MockUser\\Desktop" in cmd_list[-1]
        assert "IconLocation" in cmd_list[-1]
        assert "logo.ico" in cmd_list[-1]
