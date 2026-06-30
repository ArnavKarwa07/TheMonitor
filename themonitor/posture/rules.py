"""Pure-function posture scoring — no side effects, no camera dependency."""

from __future__ import annotations

import math
from enum import Enum
from typing import NamedTuple


class Landmark(NamedTuple):
    """A normalised 2-D landmark (0-1 range, origin at top-left)."""

    x: float
    y: float


class PostureScore(Enum):
    """Tri-state posture quality."""

    GOOD = "good"
    FAIR = "fair"
    BAD = "bad"


# Internal ordering so we can pick the *worst* score easily.
SCORE_SEVERITY: dict[PostureScore, int] = {
    PostureScore.GOOD: 0,
    PostureScore.FAIR: 1,
    PostureScore.BAD: 2,
}


class PostureRules:
    """Configuration-driven posture scorer.

    All thresholds are angles in degrees.  Landmarks are expected as
    ``Landmark(x, y)`` with values normalised to [0, 1].
    """

    def __init__(
        self,
        good_angle_threshold_degrees: float = 20.0,
        fair_angle_threshold_degrees: float = 35.0,
        neck_forward_angle_threshold_degrees: float = 18.0,
        eye_angle_threshold_degrees: float = 15.0,
        require_shoulders_level: bool = True,
        require_forward_head_check: bool = True,
    ) -> None:
        self.good_angle_threshold_degrees = good_angle_threshold_degrees
        self.fair_angle_threshold_degrees = fair_angle_threshold_degrees
        self.neck_forward_angle_threshold_degrees = neck_forward_angle_threshold_degrees
        self.eye_angle_threshold_degrees = eye_angle_threshold_degrees
        self.require_shoulders_level = require_shoulders_level
        self.require_forward_head_check = require_forward_head_check

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_shoulder_alignment(
        self,
        left_shoulder: Landmark,
        right_shoulder: Landmark,
    ) -> PostureScore:
        """Score shoulder tilt from horizontal.

        Uses MediaPipe landmarks 11 (left) and 12 (right).
        """
        y_diff = abs(left_shoulder.y - right_shoulder.y)
        x_diff = abs(left_shoulder.x - right_shoulder.x)
        angle_deg = math.degrees(math.atan2(y_diff, x_diff))

        if angle_deg < self.good_angle_threshold_degrees:
            return PostureScore.GOOD
        if angle_deg < self.fair_angle_threshold_degrees:
            return PostureScore.FAIR
        return PostureScore.BAD

    def check_forward_head(
        self,
        nose: Landmark,
        left_ear: Landmark,
        right_ear: Landmark,
        left_shoulder: Landmark,
        right_shoulder: Landmark,
    ) -> PostureScore:
        """Detect forward-head posture via frontal-view proxy.

        Compares the vertical relationship between nose, ear midpoint,
        and shoulder midpoint.
        """
        ear_mid_x = (left_ear.x + right_ear.x) / 2.0
        ear_mid_y = (left_ear.y + right_ear.y) / 2.0

        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2.0
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2.0

        # How far the nose drops below the ear midpoint (positive = below).
        nose_drop = nose.y - ear_mid_y

        # Vertical gap between ears and shoulders
        ear_shoulder_y_diff = shoulder_mid_y - ear_mid_y

        # Scale reference: shoulder width
        shoulder_width = abs(left_shoulder.x - right_shoulder.x)

        # Convert the ear-to-shoulder relationship to an angle relative to shoulder width.
        angle_deg = math.degrees(
            math.atan2(abs(ear_shoulder_y_diff), max(shoulder_width, 1e-9))
        )

        # If the nose is significantly below the ears AND the ears are
        # vertically close to the shoulders, the head is pushed forward.
        if nose_drop > 0 and angle_deg < self.neck_forward_angle_threshold_degrees:
            return PostureScore.BAD

        return PostureScore.GOOD

    def check_eye_angle(
        self,
        left_eye_inner: Landmark,
        left_eye_outer: Landmark,
        right_eye_inner: Landmark,
        right_eye_outer: Landmark,
    ) -> PostureScore:
        """Score head tilt via the eye-line angle.

        Measures the angle of the line from left eye outer (landmark 3)
        to right eye outer (landmark 6) relative to horizontal.
        Binary scoring — GOOD or BAD, no FAIR state.
        """
        y_diff = abs(right_eye_outer.y - left_eye_outer.y)
        x_diff = abs(right_eye_outer.x - left_eye_outer.x)
        angle_deg = math.degrees(math.atan2(y_diff, max(x_diff, 1e-9)))

        if angle_deg < self.eye_angle_threshold_degrees:
            return PostureScore.GOOD
        return PostureScore.BAD

    def check_bending_back(
        self,
        nose: Landmark,
        left_ear: Landmark,
        right_ear: Landmark,
        left_shoulder: Landmark,
        right_shoulder: Landmark,
        left_hip: Landmark | None = None,
        right_hip: Landmark | None = None,
    ) -> PostureScore:
        """Detect leaning too far backward (bending back).

        Uses torso tilt if hips are available, and falls back to a head-tilt
        backward proxy (nose rising above ears) otherwise.
        """
        if left_hip is not None and right_hip is not None:
            hip_mid_x = (left_hip.x + right_hip.x) / 2.0
            hip_mid_y = (left_hip.y + right_hip.y) / 2.0
            shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2.0
            shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2.0

            # Angle of torso relative to vertical
            torso_angle = math.degrees(
                math.atan2(
                    abs(shoulder_mid_x - hip_mid_x),
                    max(abs(hip_mid_y - shoulder_mid_y), 1e-9),
                )
            )
            if torso_angle > 25.0:
                return PostureScore.BAD
            if torso_angle > 18.0:
                return PostureScore.FAIR

        # Fallback/Additional check: head tilted back (nose significantly above ear midpoint)
        ear_mid_y = (left_ear.y + right_ear.y) / 2.0
        shoulder_width = abs(left_shoulder.x - right_shoulder.x)
        nose_drop_ratio = (nose.y - ear_mid_y) / max(shoulder_width, 1e-9)

        if nose_drop_ratio < -0.20:  # Nose is significantly above ears (leaning back)
            return PostureScore.BAD
        if nose_drop_ratio < -0.14:
            return PostureScore.FAIR

        return PostureScore.GOOD

    def check_asymmetric_lean(
        self,
        left_ear: Landmark,
        right_ear: Landmark,
        left_shoulder: Landmark,
        right_shoulder: Landmark,
    ) -> PostureScore:
        """Detect asymmetric side leaning (sitting weirdly).

        Measures horizontal offset of ear midpoint relative to shoulder midpoint,
        normalized by shoulder width.
        """
        ear_mid_x = (left_ear.x + right_ear.x) / 2.0
        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2.0
        shoulder_width = abs(left_shoulder.x - right_shoulder.x)

        lateral_offset = abs(ear_mid_x - shoulder_mid_x) / max(shoulder_width, 1e-9)

        if lateral_offset > 0.22:
            return PostureScore.BAD
        if lateral_offset > 0.14:
            return PostureScore.FAIR
        return PostureScore.GOOD

    # ------------------------------------------------------------------
    # Overall evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        landmarks: dict[str, Landmark],
    ) -> tuple[PostureScore, dict[str, PostureScore]]:
        """Run all enabled checks and return the worst overall score.

        Parameters
        ----------
        landmarks:
            Dict containing posture-relevant landmarks.

        Returns
        -------
        (overall_score, detail_dict)
            ``detail_dict`` maps check name → individual score.
        """
        details: dict[str, PostureScore] = {}

        if self.require_shoulders_level:
            details["shoulder"] = self.check_shoulder_alignment(
                landmarks["left_shoulder"],
                landmarks["right_shoulder"],
            )

        if self.require_forward_head_check:
            details["forward_head"] = self.check_forward_head(
                landmarks["nose"],
                landmarks["left_ear"],
                landmarks["right_ear"],
                landmarks["left_shoulder"],
                landmarks["right_shoulder"],
            )

        details["eye_angle"] = self.check_eye_angle(
            landmarks["left_eye_inner"],
            landmarks["left_eye_outer"],
            landmarks["right_eye_inner"],
            landmarks["right_eye_outer"],
        )

        left_hip = landmarks.get("left_hip")
        right_hip = landmarks.get("right_hip")
        details["bending_back"] = self.check_bending_back(
            landmarks["nose"],
            landmarks["left_ear"],
            landmarks["right_ear"],
            landmarks["left_shoulder"],
            landmarks["right_shoulder"],
            left_hip,
            right_hip,
        )

        details["asymmetric_lean"] = self.check_asymmetric_lean(
            landmarks["left_ear"],
            landmarks["right_ear"],
            landmarks["left_shoulder"],
            landmarks["right_shoulder"],
        )

        # Worst score wins.
        if details:
            overall = max(details.values(), key=lambda s: SCORE_SEVERITY[s])
        else:
            overall = PostureScore.GOOD

        return overall, details
