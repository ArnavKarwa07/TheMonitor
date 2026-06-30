"""High-level posture detector that orchestrates the capture-analyze-score pipeline.

Manages webcam lifecycle, MediaPipe processing, posture rule evaluation,
and sustained bad posture tracking.
"""

import logging
import time
import sys
from typing import Optional

import cv2
import numpy as np

from themonitor.posture.mediapipe_engine import MediaPipeEngine
from themonitor.posture.rules import PostureRules, PostureScore

logger = logging.getLogger(__name__)


class PostureResult:
    """Result of a single posture check."""

    __slots__ = ("score", "details", "timestamp", "landmarks_found")

    def __init__(
        self,
        score: PostureScore,
        details: dict[str, PostureScore],
        timestamp: float,
        landmarks_found: bool = True,
    ) -> None:
        self.score = score
        self.details = details
        self.timestamp = timestamp
        self.landmarks_found = landmarks_found

    def __repr__(self) -> str:
        return (
            f"PostureResult(score={self.score.value}, "
            f"details={{{', '.join(f'{k}: {v.value}' for k, v in self.details.items())}}}, "
            f"landmarks_found={self.landmarks_found})"
        )


class PostureDetector:
    """Orchestrates webcam capture, landmark extraction, and posture scoring.

    Tracks how long bad posture has persisted across consecutive checks.
    """

    def __init__(
        self,
        rules: PostureRules,
        camera_index: int = 0,
        model_complexity: int = 0,
    ) -> None:
        self._rules = rules
        self._camera_index = camera_index
        self._model_complexity = model_complexity

        self._engine: Optional[MediaPipeEngine] = None
        self._cap: Optional[cv2.VideoCapture] = None

        # Sustained bad posture tracking
        self._bad_posture_start: Optional[float] = None
        self._last_score: PostureScore = PostureScore.GOOD

    @property
    def bad_posture_duration(self) -> float:
        """Seconds of continuous bad posture. 0 if currently good."""
        if self._bad_posture_start is None:
            return 0.0
        return time.time() - self._bad_posture_start

    @property
    def last_score(self) -> PostureScore:
        """Most recent posture score."""
        return self._last_score

    def open(self) -> bool:
        """Initialize the webcam and MediaPipe engine.

        Returns:
            True if camera opened successfully, False otherwise.
        """
        try:
            self._engine = MediaPipeEngine(model_complexity=self._model_complexity)
            backends: list[tuple[str, int | None]]
            if sys.platform == "win32":
                backends = [("CAP_DSHOW", cv2.CAP_DSHOW), ("default", None)]
            else:
                backends = [("default", None)]

            for backend_name, backend in backends:
                self._cap = (
                    cv2.VideoCapture(self._camera_index, backend)
                    if backend is not None
                    else cv2.VideoCapture(self._camera_index)
                )

                if not self._cap.isOpened():
                    logger.debug(
                        "Camera at index %d did not open with backend %s.",
                        self._camera_index,
                        backend_name,
                    )
                    self._cleanup()
                    continue

                ret, _frame = self._cap.read()
                if not ret:
                    logger.warning(
                        "Camera at index %d opened with backend %s but could not read a frame. "
                        "Another app may be using the webcam, or Windows privacy settings may block access.",
                        self._camera_index,
                        backend_name,
                    )
                    self._cleanup()
                    continue

                logger.info(
                    "Camera opened at index %d using backend %s",
                    self._camera_index,
                    backend_name,
                )
                return True

            logger.error(
                "Failed to open a readable camera at index %d. "
                "Check webcam privacy settings, close other camera apps, or try a different index.",
                self._camera_index,
            )
            return False
        except Exception:
            logger.exception("Error initializing posture detector")
            self._cleanup()
            return False

    def close(self) -> None:
        """Release all resources."""
        self._cleanup()
        logger.info("Posture detector closed.")

    def check(self) -> Optional[PostureResult]:
        """Capture a frame, analyze posture, and update sustained tracking.

        Returns:
            PostureResult if analysis succeeded, None if capture or detection failed.
        """
        if self._cap is None or self._engine is None:
            logger.warning("Posture detector not initialized. Call open() first.")
            return None

        # Capture frame
        ret, frame = self._cap.read()
        if not ret or frame is None:
            logger.warning("Failed to capture frame from webcam.")
            return None

        # Extract landmarks
        landmarks = self._engine.extract_landmarks(frame)
        now = time.time()

        if landmarks is None:
            # No person detected — don't penalize, don't reset
            logger.debug("No pose landmarks detected in frame.")
            return PostureResult(
                score=self._last_score,
                details={},
                timestamp=now,
                landmarks_found=False,
            )

        # Score posture
        score, details = self._rules.evaluate(landmarks)
        self._last_score = score

        # Update sustained bad posture tracking
        self._update_sustained_tracking(score, now)

        result = PostureResult(
            score=score,
            details=details,
            timestamp=now,
            landmarks_found=True,
        )
        logger.debug("Posture check: %s", result)
        return result

    def _update_sustained_tracking(self, score: PostureScore, now: float) -> None:
        """Track how long bad posture has persisted."""
        if score == PostureScore.BAD:
            if self._bad_posture_start is None:
                self._bad_posture_start = now
                logger.debug("Bad posture started at %.1f", now)
        elif score == PostureScore.GOOD:
            # Good posture resets the timer
            if self._bad_posture_start is not None:
                duration = now - self._bad_posture_start
                logger.debug("Bad posture ended after %.1fs", duration)
            self._bad_posture_start = None
        # FAIR: keep accumulating if already bad, don't start new timer

    def reset_tracking(self) -> None:
        """Reset the sustained bad posture timer."""
        self._bad_posture_start = None
        self._last_score = PostureScore.GOOD

    def _cleanup(self) -> None:
        """Release resources without logging."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._engine is not None:
            self._engine.close()
            self._engine = None

    def __enter__(self) -> "PostureDetector":
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
