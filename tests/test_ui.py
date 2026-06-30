"""Tests for MonitorGUI components including shortcut, preview states, and optimizations."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from contextlib import ExitStack

import cv2
import numpy as np
import pytest

from themonitor.posture.rules import PostureScore


@pytest.fixture
def mock_gui_dependencies():
    """Mock out all GUI elements and external dependencies using ExitStack to avoid nested block limits."""
    # Setup mock config
    mock_cfg = MagicMock()
    mock_cfg.posture.camera_index = 0
    mock_cfg.posture.good_angle_threshold_degrees = 20.0
    mock_cfg.posture.fair_angle_threshold_degrees = 35.0
    mock_cfg.posture.eye_angle_threshold_degrees = 15.0
    mock_cfg.posture.neck_forward_angle_threshold_degrees = 25.0
    mock_cfg.posture.require_shoulders_level = True
    mock_cfg.posture.require_forward_head_check = True
    mock_cfg.monitoring.capture_interval_seconds = 4
    mock_cfg.monitoring.bad_posture_alert_seconds = 45
    mock_cfg.monitoring.cooldown_seconds = 300
    mock_cfg.notifications.enabled = True
    mock_cfg.notifications.title = "Posture Alert"
    mock_cfg.notifications.message = "Please sit straight!"

    with ExitStack() as stack:
        # Tkinter window mocks
        stack.enter_context(patch("tkinter.Tk.__init__", return_value=None))
        stack.enter_context(patch("tkinter.Tk.geometry"))
        stack.enter_context(patch("tkinter.Tk.title"))
        stack.enter_context(patch("tkinter.Tk.configure"))
        stack.enter_context(patch("tkinter.Tk.option_add"))
        stack.enter_context(patch("tkinter.Tk.protocol"))
        stack.enter_context(patch("tkinter.Tk.update_idletasks"))
        mock_after = stack.enter_context(patch("tkinter.Tk.after"))
        
        # Widget mocks
        stack.enter_context(patch("tkinter.Label"))
        mock_button = stack.enter_context(patch("tkinter.Button"))
        stack.enter_context(patch("tkinter.Frame"))
        stack.enter_context(patch("tkinter.LabelFrame"))
        mock_canvas = stack.enter_context(patch("tkinter.Canvas"))
        stack.enter_context(patch("tkinter.ttk.Notebook"))
        
        # Messagebox mocks
        mock_showinfo = stack.enter_context(patch("tkinter.messagebox.showinfo"))
        mock_showerror = stack.enter_context(patch("tkinter.messagebox.showerror"))
        mock_askyesno = stack.enter_context(patch("tkinter.messagebox.askyesno"))
        
        # Image/PIL/Config/Daemon/Desktop mocks
        stack.enter_context(patch("themonitor.ui.Image"))
        stack.enter_context(patch("themonitor.ui.ImageTk"))
        mock_load_config = stack.enter_context(patch("themonitor.ui.load_config", return_value=mock_cfg))
        stack.enter_context(patch("themonitor.ui.is_daemon_running", return_value=False))
        stack.enter_context(patch("themonitor.ui.get_desktop_path", return_value=Path("C:\\Mock\\Desktop")))
        
        # Mock PostureRules inside start_preview_flow
        mock_rules = MagicMock()
        mock_rules.evaluate.return_value = (PostureScore.GOOD, {})
        stack.enter_context(patch("themonitor.ui.PostureRules", return_value=mock_rules))

        yield {
            "button": mock_button,
            "canvas": mock_canvas,
            "showinfo": mock_showinfo,
            "showerror": mock_showerror,
            "askyesno": mock_askyesno,
            "after": mock_after,
            "config": mock_cfg,
            "rules": mock_rules,
        }


def test_shortcut_button_state_installed(mock_gui_dependencies):
    """Test that the shortcut button shows 'Shortcut Installed' if the file exists."""
    from themonitor.ui import MonitorGUI
    
    with patch("pathlib.Path.exists", return_value=True):
        app = MonitorGUI()
        # Ensure we check the button text in our mocks or created buttons
        button_calls = mock_gui_dependencies["button"].call_args_list
        texts = [call.kwargs.get("text") for call in button_calls if "text" in call.kwargs]
        assert "Shortcut Installed" in texts
        assert "Create Desktop Shortcut" not in texts


def test_shortcut_button_state_not_installed(mock_gui_dependencies):
    """Test that the shortcut button shows 'Create Desktop Shortcut' if the file doesn't exist."""
    from themonitor.ui import MonitorGUI
    
    with patch("pathlib.Path.exists", return_value=False):
        app = MonitorGUI()
        button_calls = mock_gui_dependencies["button"].call_args_list
        texts = [call.kwargs.get("text") for call in button_calls if "text" in call.kwargs]
        assert "Create Desktop Shortcut" in texts
        assert "Shortcut Installed" not in texts


def test_preview_state_transitions(mock_gui_dependencies):
    """Test the state transitions of the camera preview (inactive -> loading -> active/error)."""
    from themonitor.ui import MonitorGUI
    
    # 1. Init state: inactive
    with patch("pathlib.Path.exists", return_value=False):
        app = MonitorGUI()
    assert app.preview_state == "inactive"
    assert app.preview_active is False
    
    # Mock cv2.VideoCapture failure to test 'error' state
    mock_cap_fail = MagicMock()
    mock_cap_fail.isOpened.return_value = False
    
    with patch("cv2.VideoCapture", return_value=mock_cap_fail):
        app.toggle_preview()
        # Should transition to loading, fail, and end up in error state
        assert app.preview_state == "error"
        assert app.preview_active is False

    # Mock cv2.VideoCapture success to test 'active' state transition
    mock_cap_success = MagicMock()
    mock_cap_success.isOpened.return_value = True
    # mock read returning a valid frame
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap_success.read.return_value = (True, fake_frame)
    
    with patch("cv2.VideoCapture", return_value=mock_cap_success), \
         patch("themonitor.ui.MediaPipeEngine") as mock_mp_class:
        
        mock_mp_engine = MagicMock()
        mock_mp_engine.extract_landmarks.return_value = {"nose": MagicMock()}
        mock_mp_class.return_value = mock_mp_engine
        
        # Toggle preview (currently in error, should start flow)
        app.toggle_preview()
        assert app.preview_state == "active"
        assert app.preview_active is True
        
        # Toggle again to stop preview -> should transition to inactive
        app.toggle_preview()
        assert app.preview_state == "inactive"
        assert app.preview_active is False


def test_performance_optimizations(mock_gui_dependencies):
    """Test frame resizing and frame-skipping optimizations in update_preview_loop."""
    from themonitor.ui import MonitorGUI
    
    with patch("pathlib.Path.exists", return_value=False):
        app = MonitorGUI()
        
    app.preview_active = True
    app.cap = MagicMock()
    
    # Mock frame reading
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    app.cap.read.return_value = (True, fake_frame)
    
    app.mp_engine = MagicMock()
    app.rules = mock_gui_dependencies["rules"]
    app.preview_canvas = MagicMock()
    app.preview_canvas.winfo_exists.return_value = True
    
    # Spy on cv2.resize and cv2.cvtColor
    with patch("cv2.resize", wraps=cv2.resize) as spy_resize, \
         patch("cv2.cvtColor", wraps=cv2.cvtColor) as spy_cvt:
         
        # Frame 1: frame_count = 0 -> frame_count % 5 == 1 (after increment) -> calls extract_landmarks
        app.update_preview_loop()
        assert app.frame_count == 1
        app.mp_engine.extract_landmarks.assert_called_once()
        
        # Verify resize calls manually to avoid array comparison errors in assert_any_call
        calls = spy_resize.call_args_list
        found_320 = False
        found_480 = False
        for args, kwargs in calls:
            if len(args) >= 2:
                size = args[1]
                if size == (320, 240):
                    found_320 = True
                elif size == (480, 360):
                    found_480 = True

        assert found_320, "Should resize to 320x240 for MediaPipe processing"
        assert found_480, "Should resize to 480x360 for displaying"
        
        # Reset mock calls
        app.mp_engine.extract_landmarks.reset_mock()
        spy_resize.reset_mock()
        
        # Frame 2: frame_count = 1 -> frame_count % 5 == 2 -> should skip landmarks extraction
        app.update_preview_loop()
        assert app.frame_count == 2
        app.mp_engine.extract_landmarks.assert_not_called()
        
        # Frame 3, 4, 5: skip landmarks extraction
        for _ in range(3):
            app.update_preview_loop()
        app.mp_engine.extract_landmarks.assert_not_called()
        assert app.frame_count == 5
        
        # Frame 6: frame_count = 5 -> frame_count % 5 == 1 -> should call landmarks extraction again
        app.update_preview_loop()
        assert app.frame_count == 6
        app.mp_engine.extract_landmarks.assert_called_once()


def test_dynamic_canvas_sizing(mock_gui_dependencies):
    """Test that the preview loop and draw_canvas_for_state query canvas dimensions and resize/position correctly."""
    from themonitor.ui import MonitorGUI, ACCENT_RED, FG_MUTED
    
    with patch("pathlib.Path.exists", return_value=False):
        app = MonitorGUI()
        
    app.preview_active = True
    app.cap = MagicMock()
    
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    app.cap.read.return_value = (True, fake_frame)
    
    app.mp_engine = MagicMock()
    app.mp_engine.extract_landmarks.return_value = None  # Force no person detected
    app.rules = mock_gui_dependencies["rules"]
    
    # Configure mock canvas to return 640 for winfo_width() and 480 for winfo_height()
    mock_canvas = MagicMock()
    mock_canvas.winfo_exists.return_value = True
    mock_canvas.winfo_width.return_value = 640
    mock_canvas.winfo_height.return_value = 480
    app.preview_canvas = mock_canvas
    
    with patch("cv2.resize", wraps=cv2.resize) as spy_resize:
        app.update_preview_loop()
        
        # Verify resize was called with (640, 480)
        calls = spy_resize.call_args_list
        found_target = False
        for args, kwargs in calls:
            if len(args) >= 2:
                size = args[1]
                if size == (640, 480):
                    found_target = True
        assert found_target, "Should resize to (640, 480) when canvas dimensions are 640x480"

        # Verify "No person detected" warning overlay is drawn centered at (320, 240)
        # since pose_detected is False by default when no landmarks are found
        # (320, 240) is (640//2, 480//2)
        mock_canvas.create_text.assert_any_call(
            320, 240,
            text="No person detected",
            font=("Segoe UI", 16, "bold"),
            fill=ACCENT_RED,
            justify="center"
        )

    # Test draw_canvas_for_state with 640x480 dimensions
    app.preview_state = "inactive"
    mock_canvas.reset_mock()
    app.draw_canvas_for_state()
    # inactive text at (cx, cy + 60) -> (320, 240 + 60) = (320, 300)
    mock_canvas.create_text.assert_called_with(
        320, 300,
        text="Camera Preview Inactive\nClick 'Start Live Preview' below",
        font=("Segoe UI", 12),
        fill=FG_MUTED,
        justify="center"
    )
    
    app.preview_state = "loading"
    mock_canvas.reset_mock()
    app.draw_canvas_for_state()
    # loading text at (cx, cy) -> (320, 240)
    mock_canvas.create_text.assert_called_with(
        320, 240,
        text="Connecting to camera...",
        font=("Segoe UI", 12),
        fill=FG_MUTED,
        justify="center"
    )
    
    app.preview_state = "error"
    mock_canvas.reset_mock()
    app.draw_canvas_for_state()
    # error text at (cx, cy) -> (320, 240)
    mock_canvas.create_text.assert_called_with(
        320, 240,
        text=(
            "Camera Error / Failed to read frame\n\n"
            "Troubleshooting Steps:\n"
            "1. Close other applications using the camera.\n"
            "2. Check camera privacy settings in Windows.\n"
            "3. Ensure the correct Webcam Index is configured.\n"
            "4. Re-plug the camera if it's external."
        ),
        font=("Segoe UI", 10),
        fill=ACCENT_RED,
        justify="left"
    )


def test_dynamic_canvas_sizing_fallback(mock_gui_dependencies):
    """Test that if canvas dimensions are not ready or invalid, they fall back to 480x360."""
    from themonitor.ui import MonitorGUI
    
    with patch("pathlib.Path.exists", return_value=False):
        app = MonitorGUI()
        
    app.preview_active = True
    app.cap = MagicMock()
    
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    app.cap.read.return_value = (True, fake_frame)
    
    app.mp_engine = MagicMock()
    app.rules = mock_gui_dependencies["rules"]
    
    mock_canvas = MagicMock()
    mock_canvas.winfo_exists.return_value = True
    mock_canvas.winfo_width.return_value = 1
    mock_canvas.winfo_height.return_value = "invalid"
    app.preview_canvas = mock_canvas
    
    with patch("cv2.resize", wraps=cv2.resize) as spy_resize:
        app.update_preview_loop()
        
        calls = spy_resize.call_args_list
        found_fallback = False
        for args, kwargs in calls:
            if len(args) >= 2:
                size = args[1]
                if size == (480, 360):
                    found_fallback = True
        assert found_fallback, "Should fallback to (480, 360) when canvas dimensions are invalid or <= 1"

