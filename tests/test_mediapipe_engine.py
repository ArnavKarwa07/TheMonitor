from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from themonitor.posture.mediapipe_engine import MediaPipeEngine
from themonitor.posture.rules import Landmark

def test_mediapipe_engine_init_and_close():
    with patch("mediapipe.tasks.python.vision.PoseLandmarker.create_from_options") as mock_create:
        mock_landmarker = MagicMock()
        mock_create.return_value = mock_landmarker
        
        engine = MediaPipeEngine()
        assert engine._frame_timestamp_ms == 0
        
        engine.close()
        mock_landmarker.close.assert_called_once()

def test_mediapipe_engine_context_manager():
    with patch("mediapipe.tasks.python.vision.PoseLandmarker.create_from_options") as mock_create:
        mock_landmarker = MagicMock()
        mock_create.return_value = mock_landmarker
        
        with MediaPipeEngine() as engine:
            assert engine._frame_timestamp_ms == 0
            
        mock_landmarker.close.assert_called_once()

def test_mediapipe_engine_extract_landmarks_no_pose():
    with patch("mediapipe.tasks.python.vision.PoseLandmarker.create_from_options") as mock_create:
        mock_landmarker = MagicMock()
        mock_create.return_value = mock_landmarker
        
        # Mock results with no pose landmarks
        mock_results = MagicMock()
        mock_results.pose_landmarks = []
        mock_landmarker.detect_for_video.return_value = mock_results
        
        engine = MediaPipeEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks = engine.extract_landmarks(frame)
        
        assert landmarks is None
        assert engine._frame_timestamp_ms == 33
        mock_landmarker.detect_for_video.assert_called_once()

def test_mediapipe_engine_extract_landmarks_with_pose():
    with patch("mediapipe.tasks.python.vision.PoseLandmarker.create_from_options") as mock_create:
        mock_landmarker = MagicMock()
        mock_create.return_value = mock_landmarker
        
        # Mock results with pose landmarks
        mock_results = MagicMock()
        mock_landmark_points = [MagicMock(x=0.1 * i, y=0.2 * i) for i in range(33)]
        mock_results.pose_landmarks = [mock_landmark_points]
        mock_landmarker.detect_for_video.return_value = mock_results
        
        engine = MediaPipeEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks = engine.extract_landmarks(frame)
        
        assert landmarks is not None
        assert "nose" in landmarks
        assert isinstance(landmarks["nose"], Landmark)
        assert landmarks["nose"].x == 0.0
        assert landmarks["left_shoulder"].x == pytest.approx(1.1)
        assert landmarks["left_shoulder"].y == pytest.approx(2.2)
