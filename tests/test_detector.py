"""Tests for sustained posture tracking in the PostureDetector.

All tests use mocked camera and MediaPipe — no real webcam needed.
"""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def mock_time():
    """Mock time.time to return incrementing values for deterministic testing."""
    current_time = [1000.0]
    def get_time():
        val = current_time[0]
        current_time[0] += 1.0
        return val
    with patch("themonitor.posture.detector.time.time", side_effect=get_time):
        yield

from themonitor.posture.detector import PostureDetector
from themonitor.posture.rules import Landmark, PostureRules, PostureScore


# ---------------------------------------------------------------------------
# Synthetic landmark data
# ---------------------------------------------------------------------------
_GOOD_LANDMARKS: dict[str, Landmark] = {
    "nose": Landmark(0.50, 0.30),
    "left_ear": Landmark(0.42, 0.32),
    "right_ear": Landmark(0.58, 0.32),
    "left_shoulder": Landmark(0.40, 0.55),
    "right_shoulder": Landmark(0.60, 0.55),
    "left_eye_inner": Landmark(0.46, 0.28),
    "left_eye_outer": Landmark(0.42, 0.28),
    "right_eye_inner": Landmark(0.54, 0.28),
    "right_eye_outer": Landmark(0.58, 0.28),
}

# Badly tilted eyes → overall BAD
_BAD_LANDMARKS: dict[str, Landmark] = {
    **_GOOD_LANDMARKS,
    "left_eye_outer": Landmark(0.35, 0.2),
    "right_eye_outer": Landmark(0.65, 0.5),
}

# FAIR shoulders (angle ~26.6°) with good eyes → overall FAIR
_FAIR_LANDMARKS: dict[str, Landmark] = {
    **_GOOD_LANDMARKS,
    "left_shoulder": Landmark(0.4, 0.45),
    "right_shoulder": Landmark(0.6, 0.55),
}

_FAKE_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_detector(rules: PostureRules | None = None) -> PostureDetector:
    """Create a PostureDetector with mocked camera and engine."""
    rules = rules or PostureRules()
    detector = PostureDetector(rules=rules)
    detector._cap = MagicMock()
    detector._cap.read.return_value = (True, _FAKE_FRAME)
    detector._engine = MagicMock()
    return detector


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_bad_posture_starts_tracking():
    """First bad-posture check should start the sustained timer."""
    detector = _make_detector()
    detector._engine.extract_landmarks.return_value = _BAD_LANDMARKS

    result = detector.check()

    assert result is not None
    assert result.score == PostureScore.BAD
    assert detector.bad_posture_duration > 0


def test_good_posture_resets_tracking():
    """Good posture after bad should reset the sustained timer."""
    detector = _make_detector()

    # Start with bad posture
    detector._engine.extract_landmarks.return_value = _BAD_LANDMARKS
    detector.check()
    assert detector.bad_posture_duration > 0

    # Switch to good posture
    detector._engine.extract_landmarks.return_value = _GOOD_LANDMARKS
    detector.check()
    assert detector.bad_posture_duration == 0.0


def test_fair_posture_does_not_reset():
    """FAIR posture should not reset the timer started by BAD."""
    detector = _make_detector()

    # Start with bad posture
    detector._engine.extract_landmarks.return_value = _BAD_LANDMARKS
    detector.check()
    assert detector.bad_posture_duration > 0

    # Switch to fair posture — should keep accumulating
    detector._engine.extract_landmarks.return_value = _FAIR_LANDMARKS
    detector.check()
    assert detector.bad_posture_duration > 0


def test_sustained_bad_posture_accumulates():
    """Multiple bad-posture checks should accumulate duration."""
    detector = _make_detector()
    detector._engine.extract_landmarks.return_value = _BAD_LANDMARKS

    detector.check()
    d1 = detector.bad_posture_duration

    time.sleep(0.05)
    detector.check()
    d2 = detector.bad_posture_duration

    assert d2 > d1


def test_no_landmarks_keeps_last_score():
    """No pose detected should preserve the last score."""
    detector = _make_detector()

    # Start with good posture
    detector._engine.extract_landmarks.return_value = _GOOD_LANDMARKS
    detector.check()
    assert detector.last_score == PostureScore.GOOD

    # No landmarks detected
    detector._engine.extract_landmarks.return_value = None
    result = detector.check()

    assert result is not None
    assert result.landmarks_found is False
    assert detector.last_score == PostureScore.GOOD


def test_reset_tracking():
    """reset_tracking() should clear duration and set score to GOOD."""
    detector = _make_detector()

    # Accumulate some bad posture
    detector._engine.extract_landmarks.return_value = _BAD_LANDMARKS
    detector.check()
    assert detector.bad_posture_duration > 0

    detector.reset_tracking()
    assert detector.bad_posture_duration == 0.0
    assert detector.last_score == PostureScore.GOOD


def test_camera_failure_returns_none():
    """Camera read failure should return None."""
    detector = _make_detector()
    detector._cap.read.return_value = (False, None)

    result = detector.check()
    assert result is None


def test_detector_open_success():
    """Test successful initialization of detector, engine, and camera."""
    from themonitor.posture.rules import PostureRules
    rules = PostureRules()
    detector = PostureDetector(rules=rules)
    
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, _FAKE_FRAME)
    
    with patch("cv2.VideoCapture", return_value=mock_cap), \
         patch("themonitor.posture.detector.MediaPipeEngine") as mock_engine_cls:
        
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        
        opened = detector.open()
        assert opened is True
        assert detector._cap == mock_cap
        assert detector._engine == mock_engine


def test_detector_open_camera_fail():
    """Test detector initialization when VideoCapture fails to open."""
    from themonitor.posture.rules import PostureRules
    rules = PostureRules()
    detector = PostureDetector(rules=rules)
    
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    
    with patch("cv2.VideoCapture", return_value=mock_cap), \
         patch("themonitor.posture.detector.MediaPipeEngine"):
        
        opened = detector.open()
        assert opened is False
        assert detector._cap is None


def test_detector_open_read_fail():
    """Test detector initialization when camera opens but frame read fails."""
    from themonitor.posture.rules import PostureRules
    rules = PostureRules()
    detector = PostureDetector(rules=rules)
    
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (False, None)
    
    with patch("cv2.VideoCapture", return_value=mock_cap), \
         patch("themonitor.posture.detector.MediaPipeEngine"):
        
        opened = detector.open()
        assert opened is False
        assert detector._cap is None


def test_detector_close():
    """Test closing detector releases all resources."""
    detector = _make_detector()
    cap = detector._cap
    engine = detector._engine
    
    detector.close()
    
    cap.release.assert_called_once()
    engine.close.assert_called_once()
    assert detector._cap is None
    assert detector._engine is None


def test_detector_context_manager():
    """Test context manager lifecycle."""
    from themonitor.posture.rules import PostureRules
    rules = PostureRules()
    detector = PostureDetector(rules=rules)
    
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, _FAKE_FRAME)
    
    with patch("cv2.VideoCapture", return_value=mock_cap), \
         patch("themonitor.posture.detector.MediaPipeEngine") as mock_engine_cls:
        
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        
        with detector as det:
            assert det == detector
            assert detector._cap == mock_cap
            
        mock_cap.release.assert_called_once()
        mock_engine.close.assert_called_once()


def test_detector_check_uninitialized():
    """Test check() before open() returns None."""
    from themonitor.posture.rules import PostureRules
    rules = PostureRules()
    detector = PostureDetector(rules=rules)
    
    result = detector.check()
    assert result is None
