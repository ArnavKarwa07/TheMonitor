"""Tests for posture scoring rules.

All tests use synthetic landmark data — no camera or MediaPipe needed.
Angle calculations are verified against known trigonometric values.
"""

import math

import pytest

from themonitor.posture.rules import Landmark, PostureRules, PostureScore


# ---------------------------------------------------------------------------
# Helper: build a full landmarks dict with good-posture defaults
# ---------------------------------------------------------------------------
def _make_landmarks(**overrides: Landmark) -> dict[str, Landmark]:
    """Return a complete landmarks dict with default 'good posture' values.

    Override any specific landmark by keyword argument.
    """
    defaults = {
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
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Shoulder alignment tests
# ---------------------------------------------------------------------------
class TestShoulderAlignment:
    """Tests for check_shoulder_alignment."""

    def test_good(self):
        """Level shoulders → GOOD. Angle ≈ 0°."""
        rules = PostureRules()
        score = rules.check_shoulder_alignment(
            Landmark(0.4, 0.5), Landmark(0.6, 0.5)
        )
        assert score == PostureScore.GOOD

    def test_fair(self):
        """Moderate tilt → FAIR.

        y_diff=0.1, x_diff=0.2 → angle = atan2(0.1, 0.2) ≈ 26.6° → between 20-35.
        """
        rules = PostureRules()
        score = rules.check_shoulder_alignment(
            Landmark(0.4, 0.45), Landmark(0.6, 0.55)
        )
        expected_angle = math.degrees(math.atan2(0.1, 0.2))
        assert 20 < expected_angle < 35, f"Sanity check failed: angle={expected_angle}"
        assert score == PostureScore.FAIR

    def test_bad(self):
        """Severe tilt → BAD.

        y_diff=0.5, x_diff=0.2 → angle = atan2(0.5, 0.2) ≈ 68.2° → > 35.
        """
        rules = PostureRules()
        score = rules.check_shoulder_alignment(
            Landmark(0.4, 0.3), Landmark(0.6, 0.8)
        )
        assert score == PostureScore.BAD


# ---------------------------------------------------------------------------
# Eye angle tests
# ---------------------------------------------------------------------------
class TestEyeAngle:
    """Tests for check_eye_angle."""

    def test_good(self):
        """Level eyes → GOOD. Angle ≈ 0°."""
        rules = PostureRules()
        score = rules.check_eye_angle(
            left_eye_inner=Landmark(0.46, 0.4),
            left_eye_outer=Landmark(0.42, 0.4),
            right_eye_inner=Landmark(0.54, 0.4),
            right_eye_outer=Landmark(0.58, 0.4),
        )
        assert score == PostureScore.GOOD

    def test_bad(self):
        """Tilted eyes → BAD.

        y_diff=0.2, x_diff=0.3 → angle = atan2(0.2, 0.3) ≈ 33.7° → > 15.
        """
        rules = PostureRules()
        score = rules.check_eye_angle(
            left_eye_inner=Landmark(0.46, 0.3),
            left_eye_outer=Landmark(0.35, 0.3),
            right_eye_inner=Landmark(0.54, 0.5),
            right_eye_outer=Landmark(0.65, 0.5),
        )
        assert score == PostureScore.BAD


# ---------------------------------------------------------------------------
# Forward head tests
# ---------------------------------------------------------------------------
class TestForwardHead:
    """Tests for check_forward_head."""

    def test_good(self):
        """Normal posture: nose above ears, ears well above shoulders → GOOD."""
        rules = PostureRules()
        score = rules.check_forward_head(
            nose=Landmark(0.50, 0.30),
            left_ear=Landmark(0.42, 0.32),
            right_ear=Landmark(0.58, 0.32),
            left_shoulder=Landmark(0.40, 0.55),
            right_shoulder=Landmark(0.60, 0.55),
        )
        assert score == PostureScore.GOOD

    def test_bad(self):
        """Nose below ear midpoint AND ears vertically close to shoulders → BAD.

        Ear midpoint y = 0.54, shoulder midpoint y = 0.56.
        Nose y = 0.58 (below ears).
        ear_shoulder_y_diff = 0.56 - 0.54 = 0.02.
        angle = atan2(0.02, ~0.0) ≈ very small → below neck threshold → BAD.
        """
        rules = PostureRules()
        score = rules.check_forward_head(
            nose=Landmark(0.50, 0.58),
            left_ear=Landmark(0.48, 0.54),
            right_ear=Landmark(0.52, 0.54),
            left_shoulder=Landmark(0.40, 0.56),
            right_shoulder=Landmark(0.60, 0.56),
        )
        assert score == PostureScore.BAD


# ---------------------------------------------------------------------------
# Bending back tests
# ---------------------------------------------------------------------------
class TestBendingBack:
    """Tests for check_bending_back."""

    def test_good(self):
        """Standard vertical posture → GOOD."""
        rules = PostureRules()
        score = rules.check_bending_back(
            nose=Landmark(0.5, 0.3),
            left_ear=Landmark(0.42, 0.32),
            right_ear=Landmark(0.58, 0.32),
            left_shoulder=Landmark(0.40, 0.55),
            right_shoulder=Landmark(0.60, 0.55),
        )
        assert score == PostureScore.GOOD

    def test_bad_head_tilt_back(self):
        """Nose significantly above ear midpoint (head tilted back) → BAD."""
        rules = PostureRules()
        score = rules.check_bending_back(
            nose=Landmark(0.5, 0.25),  # nose y is small (higher up)
            left_ear=Landmark(0.42, 0.32),
            right_ear=Landmark(0.58, 0.32),
            left_shoulder=Landmark(0.40, 0.55),
            right_shoulder=Landmark(0.60, 0.55),
        )
        assert score == PostureScore.BAD

    def test_torso_tilt_with_hips(self):
        """Leaning torso backward/forward excessively using hips → BAD."""
        rules = PostureRules()
        # Shoulders are significantly shifted relative to hips
        score = rules.check_bending_back(
            nose=Landmark(0.5, 0.3),
            left_ear=Landmark(0.42, 0.32),
            right_ear=Landmark(0.58, 0.32),
            left_shoulder=Landmark(0.40, 0.55),
            right_shoulder=Landmark(0.60, 0.55),
            left_hip=Landmark(0.2, 0.9),
            right_hip=Landmark(0.4, 0.9),
        )
        assert score == PostureScore.BAD


# ---------------------------------------------------------------------------
# Asymmetric leaning tests
# ---------------------------------------------------------------------------
class TestAsymmetricLean:
    """Tests for check_asymmetric_lean."""

    def test_good(self):
        """Ears aligned over shoulders → GOOD."""
        rules = PostureRules()
        score = rules.check_asymmetric_lean(
            left_ear=Landmark(0.42, 0.32),
            right_ear=Landmark(0.58, 0.32),
            left_shoulder=Landmark(0.40, 0.55),
            right_shoulder=Landmark(0.60, 0.55),
        )
        assert score == PostureScore.GOOD

    def test_bad_lateral_lean(self):
        """Head shifted way to the side relative to shoulders → BAD."""
        rules = PostureRules()
        score = rules.check_asymmetric_lean(
            left_ear=Landmark(0.57, 0.32),
            right_ear=Landmark(0.73, 0.32),
            left_shoulder=Landmark(0.40, 0.55),
            right_shoulder=Landmark(0.60, 0.55),
        )
        assert score == PostureScore.BAD


# ---------------------------------------------------------------------------
# Overall evaluation tests
# ---------------------------------------------------------------------------
class TestEvaluate:
    """Tests for the evaluate method."""

    def test_all_good(self):
        """All checks pass → overall GOOD."""
        rules = PostureRules()
        landmarks = _make_landmarks()
        score, details = rules.evaluate(landmarks)

        assert score == PostureScore.GOOD
        assert all(v == PostureScore.GOOD for v in details.values())

    def test_worst_wins(self):
        """One BAD check → overall BAD even if others are GOOD."""
        rules = PostureRules()
        # Tilt the eyes badly
        landmarks = _make_landmarks(
            left_eye_outer=Landmark(0.35, 0.2),
            right_eye_outer=Landmark(0.65, 0.5),
        )
        score, details = rules.evaluate(landmarks)

        assert score == PostureScore.BAD
        assert details["eye_angle"] == PostureScore.BAD

    def test_skip_shoulder_check(self):
        """With require_shoulders_level=False, 'shoulder' not in details."""
        rules = PostureRules(require_shoulders_level=False)
        landmarks = _make_landmarks()
        _, details = rules.evaluate(landmarks)

        assert "shoulder" not in details
        assert "eye_angle" in details

    def test_skip_forward_head_check(self):
        """With require_forward_head_check=False, 'forward_head' not in details."""
        rules = PostureRules(require_forward_head_check=False)
        landmarks = _make_landmarks()
        _, details = rules.evaluate(landmarks)

        assert "forward_head" not in details
        assert "eye_angle" in details

    def test_all_checks_present_by_default(self):
        """Default rules include all checks."""
        rules = PostureRules()
        landmarks = _make_landmarks()
        _, details = rules.evaluate(landmarks)

        assert "shoulder" in details
        assert "forward_head" in details
        assert "eye_angle" in details
        assert "bending_back" in details
        assert "asymmetric_lean" in details
