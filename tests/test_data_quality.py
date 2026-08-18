"""
Tests for coursepath/data_quality.py

Run with: pytest tests/test_data_quality.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coursepath.data_quality import (
    _signal_would_take_again,
    SIGNAL_WEIGHTS,
    score_course,
    breakdown,
    quality_label,
    plan_quality_summary,
    _signal_manually_reviewed,
    _signal_descriptors,
    _signal_extended_topics,
    _signal_professor_rating,
    _signal_grade_distribution,
    _signal_sis_verified,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: course records at different quality tiers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def minimal_course():
    """Bare minimum: just the fields every course has."""
    return {
        "units": 4,
        "professor_rating": 3.5,
        "difficulty": 3.0,
        "topics": {"python": 0.5, "statistics": 0.5},
    }

@pytest.fixture
def partial_course():
    """RMP-annotated, some descriptors, not manually reviewed."""
    return {
        "units": 4,
        "professor_rating": 4.2,
        "num_ratings": 8,
        "difficulty": 3.0,
        "topics": {"python": 0.5, "statistics": 0.3, "algorithm": 0.2},
        "descriptors": ["data analysis in Python", "intro statistics", "Jupyter notebooks"],
        "manually_reviewed": False,
        "sis_verified": False,
    }

@pytest.fixture
def full_course():
    """Fully annotated, human-reviewed course."""
    return {
        "units": 4,
        "professor_rating": 4.8,
        "num_ratings": 25,
        "difficulty": 3.0,
        "would_take_again": 92.0,
        "rmp_difficulty": 2.9,
        "topics": {"python": 0.4, "statistics": 0.3, "algorithm": 0.2, "data_analysis": 0.1},
        "descriptors": [
            "data wrangling in Python",
            "exploratory data analysis",
            "statistical inference",
            "Pandas and NumPy workflows",
            "visualization with Matplotlib",
        ],
        "manually_reviewed": True,
        "sis_verified": True,
        "grade_dist": {"A+": 12, "A": 45, "A-": 30, "B+": 20, "B": 15},
    }


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL_WEIGHTS invariant
# ─────────────────────────────────────────────────────────────────────────────

def test_signal_weights_sum_to_one():
    assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9

def test_signal_weights_all_positive():
    for k, v in SIGNAL_WEIGHTS.items():
        assert v > 0, f"Weight for '{k}' must be positive"


# ─────────────────────────────────────────────────────────────────────────────
# Individual signal functions
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalManuallyReviewed:
    def test_true(self):
        assert _signal_manually_reviewed({"manually_reviewed": True}) == 1.0
    def test_false(self):
        assert _signal_manually_reviewed({"manually_reviewed": False}) == 0.0
    def test_missing(self):
        assert _signal_manually_reviewed({}) == 0.0
    def test_non_bool_truthy(self):
        # Only literal True counts
        assert _signal_manually_reviewed({"manually_reviewed": 1}) == 0.0


class TestSignalDescriptors:
    def test_empty(self):
        assert _signal_descriptors({}) == 0.0
    def test_none(self):
        assert _signal_descriptors({"descriptors": []}) == 0.0
    def test_one(self):
        assert _signal_descriptors({"descriptors": ["x"]}) == 0.3
    def test_three(self):
        assert _signal_descriptors({"descriptors": ["a", "b", "c"]}) == 0.7
    def test_five(self):
        assert _signal_descriptors({"descriptors": list("abcde")}) == 1.0
    def test_ten(self):
        assert _signal_descriptors({"descriptors": list("abcdefghij")}) == 1.0


class TestSignalExtendedTopics:
    def test_empty(self):
        assert _signal_extended_topics({}) == 0.0
    def test_one(self):
        assert _signal_extended_topics({"topics": {"python": 0.5}}) == 0.0
    def test_two(self):
        assert _signal_extended_topics({"topics": {"a": 0.5, "b": 0.5}}) == 0.4
    def test_four(self):
        t = {"a": 0.3, "b": 0.3, "c": 0.2, "d": 0.2}
        assert _signal_extended_topics({"topics": t}) == 0.7
    def test_six(self):
        t = {str(i): 0.1 for i in range(6)}
        assert _signal_extended_topics({"topics": t}) == 1.0


class TestSignalProfessorRating:
    def test_missing_rating(self):
        assert _signal_professor_rating({}) == 0.0
    def test_rating_no_num_ratings(self):
        # Rating exists but num_ratings absent would give partial credit
        assert _signal_professor_rating({"professor_rating": 4.0}) == 0.5
    def test_one_rating(self):
        assert _signal_professor_rating({"professor_rating": 4.0, "num_ratings": 1}) == 0.4
    def test_five_ratings(self):
        assert _signal_professor_rating({"professor_rating": 4.0, "num_ratings": 5}) == 0.7
    def test_twenty_ratings(self):
        assert _signal_professor_rating({"professor_rating": 4.0, "num_ratings": 20}) == 1.0
    def test_hundred_ratings(self):
        assert _signal_professor_rating({"professor_rating": 4.0, "num_ratings": 100}) == 1.0


class TestSignalGradeDistribution:
    def test_missing(self):
        assert _signal_grade_distribution({}) == 0.0
    def test_empty_dict(self):
        assert _signal_grade_distribution({"grade_dist": {}}) == 0.0
    def test_one_entry(self):
        assert _signal_grade_distribution({"grade_dist": {"A": 10}}) == 0.3
    def test_three_entries(self):
        assert _signal_grade_distribution({"grade_dist": {"A": 10, "B": 5, "C": 2}}) == 0.6
    def test_five_entries(self):
        d = {"A+": 5, "A": 10, "A-": 8, "B+": 6, "B": 4}
        assert _signal_grade_distribution({"grade_dist": d}) == 1.0


class TestSignalSisVerified:
    def test_true(self):
        assert _signal_sis_verified({"sis_verified": True}) == 1.0
    def test_false(self):
        assert _signal_sis_verified({"sis_verified": False}) == 0.0
    def test_missing(self):
        assert _signal_sis_verified({}) == 0.0


class TestSignalWouldTakeAgain:
    def test_missing(self):
        assert _signal_would_take_again({}) == 0.0
    def test_none(self):
        assert _signal_would_take_again({"would_take_again": None}) == 0.0
    def test_below_60(self):
        assert _signal_would_take_again({"would_take_again": 45.0}) == 0.4
    def test_between_60_and_80(self):
        assert _signal_would_take_again({"would_take_again": 72.0}) == 0.7
    def test_above_80(self):
        assert _signal_would_take_again({"would_take_again": 92.0}) == 1.0
    def test_exactly_80(self):
        assert _signal_would_take_again({"would_take_again": 80.0}) == 1.0
    def test_exactly_60(self):
        assert _signal_would_take_again({"would_take_again": 60.0}) == 0.7


# ─────────────────────────────────────────────────────────────────────────────
# score_course
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreCourse:

    def test_minimal_course_low_score(self, minimal_course):
        score = score_course(minimal_course)
        # No manual review, no descriptors, only 2 topics, rating but no num_ratings
        # = 0 + 0 + 0.4*0.15 + 0.5*0.15 + 0 + 0 = 0.135
        assert score < 0.30

    def test_full_course_high_score(self, full_course):
        score = score_course(full_course)
        assert score >= 0.80

    def test_score_in_range(self, minimal_course, partial_course, full_course):
        for course in [minimal_course, partial_course, full_course]:
            s = score_course(course)
            assert 0.0 <= s <= 1.0

    def test_score_is_rounded(self, full_course):
        score = score_course(full_course)
        assert score == round(score, 4)

    def test_full_beats_partial_beats_minimal(self, minimal_course, partial_course, full_course):
        assert score_course(full_course) > score_course(partial_course)
        assert score_course(partial_course) > score_course(minimal_course)

    def test_manually_reviewed_makes_biggest_difference(self, partial_course):
        without = score_course(partial_course)
        with_review = dict(partial_course)
        with_review["manually_reviewed"] = True
        with_ = score_course(with_review)
        delta = with_ - without
        assert abs(delta - 0.25) < 1e-9


# ─────────────────────────────────────────────────────────────────────────────
# breakdown
# ─────────────────────────────────────────────────────────────────────────────

class TestBreakdown:

    def test_returns_all_signals(self, minimal_course):
        bd = breakdown(minimal_course)
        assert set(bd.keys()) == set(SIGNAL_WEIGHTS.keys())

    def test_values_in_range(self, full_course):
        bd = breakdown(full_course)
        for k, v in bd.items():
            assert 0.0 <= v <= 1.0, f"Signal '{k}' out of range: {v}"

    def test_full_course_all_signals_high(self, full_course):
        bd = breakdown(full_course)
        # All signals should be >0 for a fully annotated course
        for k, v in bd.items():
            assert v > 0, f"Expected signal '{k}' > 0 for full course"


# ─────────────────────────────────────────────────────────────────────────────
# quality_label
# ─────────────────────────────────────────────────────────────────────────────

class TestQualityLabel:
    @pytest.mark.parametrize("score,expected", [
        (0.00, "minimal"),
        (0.24, "minimal"),
        (0.25, "low"),
        (0.49, "low"),
        (0.50, "medium"),
        (0.79, "medium"),
        (0.80, "high"),
        (1.00, "high"),
    ])
    def test_boundaries(self, score, expected):
        assert quality_label(score) == expected


# ─────────────────────────────────────────────────────────────────────────────
# plan_quality_summary
# ─────────────────────────────────────────────────────────────────────────────

class TestPlanQualitySummary:

    @pytest.fixture
    def mock_courses(self, minimal_course, full_course):
        return {
            "COURSE A": {**minimal_course, "data_quality": score_course(minimal_course)},
            "COURSE B": {**full_course,    "data_quality": score_course(full_course)},
        }

    def test_empty_course_names(self, mock_courses):
        result = plan_quality_summary([], mock_courses)
        assert result["mean"] == 0.0
        assert result["min"]  == 0.0
        assert result["low_confidence"] == []
        assert result["label"] == "minimal"

    def test_unknown_courses_ignored(self, mock_courses):
        result = plan_quality_summary(["FAKE 999"], mock_courses)
        assert result["mean"] == 0.0

    def test_mean_computed_correctly(self, mock_courses):
        result = plan_quality_summary(["COURSE A", "COURSE B"], mock_courses)
        expected_mean = (
            mock_courses["COURSE A"]["data_quality"] +
            mock_courses["COURSE B"]["data_quality"]
        ) / 2
        assert abs(result["mean"] - round(expected_mean, 4)) < 1e-4

    def test_low_confidence_flagged(self, mock_courses):
        result = plan_quality_summary(["COURSE A", "COURSE B"], mock_courses)
        assert "COURSE A" in result["low_confidence"]
        assert "COURSE B" not in result["low_confidence"]

    def test_label_matches_mean(self, mock_courses):
        result = plan_quality_summary(["COURSE A", "COURSE B"], mock_courses)
        assert result["label"] == quality_label(result["mean"])

    def test_falls_back_to_scoring_if_no_data_quality_field(self, minimal_course):
        courses = {"COURSE X": minimal_course}  # no "data_quality" key
        result = plan_quality_summary(["COURSE X"], courses)
        assert 0.0 <= result["mean"] <= 1.0
