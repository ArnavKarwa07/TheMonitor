"""MediaPipe pose-landmark extraction, isolated from scoring rules."""

from __future__ import annotations

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from pathlib import Path
from typing import Optional
import numpy as np

from themonitor.posture.rules import Landmark

# MediaPipe pose landmark indices we care about.
_LANDMARK_MAP: dict[str, int] = {
    "nose": 0,
    "left_eye_inner": 1,
    "left_eye_outer": 3,
    "right_eye_inner": 4,
    "right_eye_outer": 6,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_hip": 23,
    "right_hip": 24,
}


class MediaPipeEngine:
    """Thin wrapper around MediaPipe Pose for landmark extraction.

    Usage::

        with MediaPipeEngine() as engine:
            landmarks = engine.extract_landmarks(frame_bgr)
    """

    def __init__(self, model_complexity: int = 0) -> None:
        """Initialise MediaPipe Pose.

        Parameters
        ----------
        model_complexity:
            0 (lite), 1 (full), or 2 (heavy).  Default ``0`` for speed.
        """
        # Map model_complexity to model file (we only ship lite for now)
        model_path = str(Path(__file__).resolve().parent / "pose_landmarker_lite.task")
        
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            num_poses=1,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._frame_timestamp_ms = 0

    def extract_landmarks(self, frame_bgr: np.ndarray) -> Optional[dict[str, Landmark]]:
        """Convert a BGR frame into a dict of posture-relevant landmarks.

        Returns ``None`` when MediaPipe fails to detect a pose.
        """
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        self._frame_timestamp_ms += 33  # ~30fps
        results = self._landmarker.detect_for_video(mp_image, self._frame_timestamp_ms)
        
        if not results.pose_landmarks:
            return None
        
        raw = results.pose_landmarks[0]  # First person
        return {
            name: Landmark(x=raw[idx].x, y=raw[idx].y)
            for name, idx in _LANDMARK_MAP.items()
        }

    def close(self) -> None:
        """Release MediaPipe resources."""
        self._landmarker.close()

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> MediaPipeEngine:
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        self.close()
