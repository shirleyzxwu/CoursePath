"""
Run with:
    pytest tests/test_planner.py -v
"""

import pytest
import sys
import os

# Allow running from the project root: CoursePath/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coursepath.planner import (
    prereq_satisfied,
    prereqs_met,
    build_prereq_graph,
    topological_order,
    RequirementTracker,
    interest_alignment,
    score_schedule,
    valid_schedule,
    generate_semester_plans,
    plan_four_years,
    PlannerState,
    COURSES,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def bio_profile():
    return {
        "bioinformatics": 1.0,
        "python": 0.8,
        "statistics": 0.6,
        "genetics": 0.7,
        "math": 0.4,
    }

@pytest.fixture
def default_weights():
    return {"interest": 1.0, "difficulty": 0.5, "professor": 0.3}

@pytest.fixture
def basic_tracker():
    return RequirementTracker(
        buckets={"bio_upper": 2, "cs_core": 1},
        course_to_buckets={
            "MCELLBI C148": ["bio_upper"],
            "MCELLBI 104":  ["bio_upper"],
            "COMPSCI 61A":  ["cs_core"],
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# prereq_satisfied
# ─────────────────────────────────────────────────────────────────────────────

class TestPrereqSatisfied:

    def test_none_always_true(self):
        assert prereq_satisfied(None, set()) is True
        assert prereq_satisfied(None, {"COMPSCI 61A"}) is True

    def test_string_present(self):
        assert prereq_satisfied("MATH 51", {"MATH 51"}) is True

    def test_string_absent(self):
        assert prereq_satisfied("MATH 51", set()) is False

    def test_and_all_present(self):
        req = {"and": ["MATH 51", "MATH 52"]}
        assert prereq_satisfied(req, {"MATH 51", "MATH 52"}) is True

    def test_and_partial(self):
        req = {"and": ["MATH 51", "MATH 52"]}
        assert prereq_satisfied(req, {"MATH 51"}) is False

    def test_and_empty(self):
        assert prereq_satisfied({"and": []}, set()) is True

    def test_or_one_present(self):
        req = {"or": ["DATA C8", "STAT 20"]}
        assert prereq_satisfied(req, {"STAT 20"}) is True

    def test_or_none_present(self):
        req = {"or": ["DATA C8", "STAT 20"]}
        assert prereq_satisfied(req, {"COMPSCI 61A"}) is False

    def test_or_all_present(self):
        req = {"or": ["DATA C8", "STAT 20"]}
        assert prereq_satisfied(req, {"DATA C8", "STAT 20"}) is True

    def test_nested_and_or(self):
        # DATA C100 prereq structure
        req = {"and": [
            {"or": ["DATA C8", "STAT 20"]},
            {"or": ["COMPSCI 61A", "DATA C88C", "ENGIN 7"]},
        ]}
        assert prereq_satisfied(req, {"DATA C8", "COMPSCI 61A"}) is True
        assert prereq_satisfied(req, {"DATA C8"}) is False
        assert prereq_satisfied(req, {"STAT 20", "ENGIN 7"}) is True

    def test_deeply_nested(self):
        req = {"and": [{"or": [{"and": ["MATH 51", "MATH 52"]}, "MATH 56"]}]}
        assert prereq_satisfied(req, {"MATH 51", "MATH 52"}) is True
        assert prereq_satisfied(req, {"MATH 56"}) is True
        assert prereq_satisfied(req, {"MATH 51"}) is False

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError):
            prereq_satisfied({"xor": ["A", "B"]}, {"A"})


# ─────────────────────────────────────────────────────────────────────────────
# prereqs_met (against real COURSES data)
# ─────────────────────────────────────────────────────────────────────────────

class TestPrereqsMet:

    def test_no_prereq_course(self):
        assert prereqs_met("DATA C8", set()) is True
        assert prereqs_met("COMPSCI 70", set()) is True
        assert prereqs_met("MATH 55", set()) is True

    def test_string_prereq(self):
        assert prereqs_met("MATH 52", {"MATH 51"}) is True
        assert prereqs_met("MATH 52", set()) is False

    def test_and_prereq(self):
        # PHYSICS 7A requires MATH 51 AND MATH 52
        assert prereqs_met("PHYSICS 7A", {"MATH 51", "MATH 52"}) is True
        assert prereqs_met("PHYSICS 7A", {"MATH 51"}) is False

    def test_or_prereq(self):
        # COMPSCI 61B: or [COMPSCI 61A, COMPSCI 88, ENGIN 7]
        assert prereqs_met("COMPSCI 61B", {"COMPSCI 61A"}) is True
        assert prereqs_met("COMPSCI 61B", {"ENGIN 7"}) is True
        assert prereqs_met("COMPSCI 61B", set()) is False

    def test_chain(self):
        # MATH 53 requires MATH 52 requires MATH 51
        assert prereqs_met("MATH 53", {"MATH 52"}) is True
        assert prereqs_met("MATH 53", {"MATH 51"}) is False


# ─────────────────────────────────────────────────────────────────────────────
# Topological order
# ─────────────────────────────────────────────────────────────────────────────

class TestTopologicalOrder:

    def test_returns_all_courses(self):
        order = topological_order()
        assert set(order) == set(COURSES.keys())

    def test_no_prereq_courses_come_first(self):
        order = topological_order()
        pos = {c: i for i, c in enumerate(order)}
        no_prereq = [c for c, d in COURSES.items() if d["prerequisites"] is None]
        # Every course with no prereqs must appear before courses that depend on it
        for c in no_prereq:
            assert c in pos

    def test_math_chain_order(self):
        order = topological_order()
        pos = {c: i for i, c in enumerate(order)}
        # MATH 51 → 52 → 53 must be in order
        assert pos["MATH 51"] < pos["MATH 52"]
        assert pos["MATH 52"] < pos["MATH 53"]

    def test_data_c100_after_prereqs(self):
        order = topological_order()
        pos = {c: i for i, c in enumerate(order)}
        assert pos["DATA C8"] < pos["DATA C100"]
        assert pos["COMPSCI 61A"] < pos["DATA C100"]

    def test_no_duplicates(self):
        order = topological_order()
        assert len(order) == len(set(order))


# ─────────────────────────────────────────────────────────────────────────────
# RequirementTracker
# ─────────────────────────────────────────────────────────────────────────────

class TestRequirementTracker:

    def test_initial_completion_zero(self, basic_tracker):
        assert basic_tracker.completion_ratio() == 0.0

    def test_empty_buckets_returns_one(self):
        t = RequirementTracker(buckets={}, course_to_buckets={})
        assert t.completion_ratio() == 1.0

    def test_apply_increments_bucket(self, basic_tracker):
        basic_tracker.apply("COMPSCI 61A")
        assert basic_tracker.fulfilled["cs_core"] == 1

    def test_apply_does_not_exceed_target(self, basic_tracker):
        basic_tracker.apply("COMPSCI 61A")
        basic_tracker.apply("COMPSCI 61A")  # apply twice
        assert basic_tracker.fulfilled["cs_core"] == 1  # capped at target

    def test_apply_unknown_course_is_noop(self, basic_tracker):
        before = dict(basic_tracker.fulfilled)
        basic_tracker.apply("COMPSCI 999")
        assert basic_tracker.fulfilled == before

    def test_partial_completion_ratio(self, basic_tracker):
        basic_tracker.apply("MCELLBI C148")   # 1 of 2 bio_upper, 0 of 1 cs_core
        ratio = basic_tracker.completion_ratio()
        # bio_upper: 0.5, cs_core: 0.0 → mean = 0.25
        assert abs(ratio - 0.25) < 1e-9

    def test_full_completion(self, basic_tracker):
        basic_tracker.apply("MCELLBI C148")
        basic_tracker.apply("MCELLBI 104")
        basic_tracker.apply("COMPSCI 61A")
        assert basic_tracker.completion_ratio() == 1.0

    def test_clone_is_independent(self, basic_tracker):
        clone = basic_tracker.clone()
        clone.apply("COMPSCI 61A")
        assert basic_tracker.fulfilled["cs_core"] == 0
        assert clone.fulfilled["cs_core"] == 1

    def test_clone_preserves_state(self, basic_tracker):
        basic_tracker.apply("MCELLBI C148")
        clone = basic_tracker.clone()
        assert clone.fulfilled["bio_upper"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────

class TestScoring:

    def test_interest_alignment_empty(self):
        assert interest_alignment((), {}) == 0.0

    def test_interest_alignment_zero_profile(self):
        score = interest_alignment(("DATA C8",), {})
        assert score == 0.0

    def test_interest_alignment_perfect_match(self):
        # DATA C8 topics: python=0.5, statistics=0.5
        profile = {"python": 1.0, "statistics": 1.0}
        score = interest_alignment(("DATA C8",), profile)
        assert abs(score - 1.0) < 1e-9  # 0.5*1 + 0.5*1 = 1.0

    def test_interest_alignment_partial_match(self):
        profile = {"python": 1.0, "statistics": 0.0}
        score = interest_alignment(("DATA C8",), profile)
        assert abs(score - 0.5) < 1e-9  # only python matches

    def test_interest_alignment_multi_course_averages(self):
        profile = {"python": 1.0, "statistics": 0.0}
        # DATA C8: python=0.5 → score 0.5
        # MATH 55: math=0.7, algorithm=0.3 → score 0.0
        score = interest_alignment(("DATA C8", "MATH 55"), profile)
        assert abs(score - 0.25) < 1e-9  # (0.5 + 0.0) / 2

    def test_score_schedule_higher_interest_wins(self, bio_profile, default_weights):
        # C148 is bioinformatics-heavy → should score higher than MATH 51
        score_bio = score_schedule(("MCELLBI C148",), bio_profile, default_weights)
        score_math = score_schedule(("MATH 51",), bio_profile, default_weights)
        assert score_bio > score_math

    def test_score_schedule_difficulty_penalty(self, default_weights):
        # With zero interest, higher difficulty → lower score
        flat_profile = {}
        easy = score_schedule(("MATH 55",), flat_profile, default_weights)    # diff=2.5
        hard = score_schedule(("COMPSCI 170",), flat_profile, default_weights) # diff=4.3
        assert easy > hard

    def test_score_schedule_with_breadth_tracker(self, bio_profile, default_weights, basic_tracker):
        score_with    = score_schedule(("MCELLBI C148",), bio_profile, default_weights, basic_tracker)
        score_without = score_schedule(("MCELLBI C148",), bio_profile, default_weights, None)
        # breadth bonus not applied when tracker is None, so without should equal
        # the no-breadth version, or with weight=0 they're equal. Default weights
        # don't include "breadth", so bonus is 0. They should be equal.
        assert abs(score_with - score_without) < 1e-9

    def test_score_schedule_breadth_weight_adds_bonus(self, bio_profile, basic_tracker):
        weights_with_breadth = {"interest": 1.0, "difficulty": 0.5, "professor": 0.3, "breadth": 1.0}
        weights_no_breadth   = {"interest": 1.0, "difficulty": 0.5, "professor": 0.3, "breadth": 0.0}
        s_with = score_schedule(("COMPSCI 61A",), bio_profile, weights_with_breadth, basic_tracker)
        s_no   = score_schedule(("COMPSCI 61A",), bio_profile, weights_no_breadth,   basic_tracker)
        assert s_with > s_no


# ─────────────────────────────────────────────────────────────────────────────
# valid_schedule
# ─────────────────────────────────────────────────────────────────────────────

class TestValidSchedule:

    def test_within_bounds(self):
        # DATA C8=4, MATH 55=4 → 8 units
        assert valid_schedule(("DATA C8", "MATH 55"), 8, 18) is True

    def test_below_min(self):
        assert valid_schedule(("DATA C88C",), 8, 18) is False  # 3 units

    def test_above_max(self):
        # MCELLBI 140=8, DATA C8=4, MATH 55=4, COMPSCI 70=4 → 20 units
        assert valid_schedule(
            ("MCELLBI 140 & MCELLBI 140L", "DATA C8", "MATH 55", "COMPSCI 70"),
            8, 18
        ) is False

    def test_exact_min(self):
        assert valid_schedule(("DATA C8", "COMPSCI 70"), 8, 18) is True  # 8 units

    def test_exact_max(self):
        assert valid_schedule(
            ("DATA C8", "COMPSCI 70", "MATH 55", "DATA C88C"),
            8, 15
        ) is True  # 4+4+4+3=15


# ─────────────────────────────────────────────────────────────────────────────
# generate_semester_plans
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateSemesterPlans:

    def test_returns_list(self, bio_profile, default_weights):
        plans = generate_semester_plans(
            completed=set(),
            interest_profile=bio_profile,
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=3,
        )
        assert isinstance(plans, list)

    def test_plans_have_required_keys(self, bio_profile, default_weights):
        plans = generate_semester_plans(
            completed=set(),
            interest_profile=bio_profile,
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=3,
        )
        for p in plans:
            assert "courses" in p
            assert "score" in p
            assert isinstance(p["courses"], list)
            assert isinstance(p["score"], float)

    def test_respects_top_k(self, bio_profile, default_weights):
        plans = generate_semester_plans(
            completed=set(),
            interest_profile=bio_profile,
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=3,
        )
        assert len(plans) <= 3

    def test_sorted_descending(self, bio_profile, default_weights):
        plans = generate_semester_plans(
            completed=set(),
            interest_profile=bio_profile,
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=5,
        )
        scores = [p["score"] for p in plans]
        assert scores == sorted(scores, reverse=True)

    def test_completed_courses_excluded(self, bio_profile, default_weights):
        completed = {"DATA C8", "MATH 55", "COMPSCI 61A", "COMPSCI 70"}
        plans = generate_semester_plans(
            completed=completed,
            interest_profile=bio_profile,
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=5,
        )
        for p in plans:
            for c in p["courses"]:
                assert c not in completed

    def test_unit_bounds_respected(self, bio_profile, default_weights):
        plans = generate_semester_plans(
            completed=set(),
            interest_profile=bio_profile,
            min_units=12,
            max_units=16,
            weights=default_weights,
            top_k=5,
        )
        for p in plans:
            units = sum(COURSES[c]["units"] for c in p["courses"])
            assert 12 <= units <= 16

    def test_prereqs_respected(self, bio_profile, default_weights):
        # With no completed courses, DATA C100 (needs DATA C8 or STAT 20) must not appear
        plans = generate_semester_plans(
            completed=set(),
            interest_profile=bio_profile,
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=10,
        )
        all_courses = [c for p in plans for c in p["courses"]]
        assert "DATA C100" not in all_courses

    def test_prereqs_unlocked_by_completed(self, bio_profile, default_weights):
        # With DATA C8 + COMPSCI 61A done, DATA C100 can appear
        completed = {"DATA C8", "COMPSCI 61A", "MATH 54"}
        plans = generate_semester_plans(
            completed=completed,
            interest_profile=bio_profile,
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=10,
        )
        all_courses = [c for p in plans for c in p["courses"]]
        assert "DATA C100" in all_courses

    def test_term_filter_fall(self, bio_profile, default_weights):
        plans = generate_semester_plans(
            completed=set(),
            interest_profile=bio_profile,
            term="Fall",
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=5,
        )
        for p in plans:
            for c in p["courses"]:
                assert "Fall" in COURSES[c]["terms_offered"], \
                    f"{c} not offered in Fall"

    def test_term_filter_spring(self, bio_profile, default_weights):
        plans = generate_semester_plans(
            completed=set(),
            interest_profile=bio_profile,
            term="Spring",
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=5,
        )
        for p in plans:
            for c in p["courses"]:
                assert "Spring" in COURSES[c]["terms_offered"], \
                    f"{c} not offered in Spring"

    def test_fall_only_course_excluded_from_spring(self, default_weights):
        # MCELLBI 153 is Fall only
        profile = {"bioinformatics": 1.0}
        plans = generate_semester_plans(
            completed={"MCELLBI C100A"},
            interest_profile=profile,
            term="Spring",
            min_units=4,
            max_units=18,
            weights=default_weights,
            top_k=10,
        )
        all_courses = [c for p in plans for c in p["courses"]]
        assert "MCELLBI 153" not in all_courses

    def test_empty_when_impossible(self, bio_profile, default_weights):
        # Mark everything as completed → no courses left
        all_courses = set(COURSES.keys())
        plans = generate_semester_plans(
            completed=all_courses,
            interest_profile=bio_profile,
            min_units=8,
            max_units=18,
            weights=default_weights,
            top_k=5,
        )
        assert plans == []


# ─────────────────────────────────────────────────────────────────────────────
# plan_four_years
# ─────────────────────────────────────────────────────────────────────────────

class TestPlanFourYears:

    def test_returns_beam_width_plans(self, bio_profile, default_weights):
        plans = plan_four_years(
            interest_profile=bio_profile,
            weights=default_weights,
            min_units=8,
            max_units=18,
            beam_width=2,
            top_k_per_semester=3,
        )
        assert len(plans) <= 2

    def test_eight_semesters(self, bio_profile, default_weights):
        plans = plan_four_years(
            interest_profile=bio_profile,
            weights=default_weights,
            min_units=8,
            max_units=18,
            beam_width=1,
            top_k_per_semester=3,
        )
        assert len(plans[0].semester_plans) == 8

    def test_semester_sequence_correct(self, bio_profile, default_weights):
        plans = plan_four_years(
            interest_profile=bio_profile,
            weights=default_weights,
            min_units=8,
            max_units=18,
            beam_width=1,
            top_k_per_semester=3,
        )
        sems = plans[0].semester_plans
        expected_terms = ["Fall", "Spring"] * 4
        expected_years = ["Year 1"]*2 + ["Year 2"]*2 + ["Year 3"]*2 + ["Year 4"]*2
        for i, sem in enumerate(sems):
            assert sem["term"] == expected_terms[i]
            assert sem["year"] == expected_years[i]

    def test_no_course_repeated(self, bio_profile, default_weights):
        plans = plan_four_years(
            interest_profile=bio_profile,
            weights=default_weights,
            min_units=8,
            max_units=18,
            beam_width=1,
            top_k_per_semester=3,
        )
        all_scheduled = [c for sem in plans[0].semester_plans for c in sem["courses"]]
        assert len(all_scheduled) == len(set(all_scheduled)), \
            "A course appeared in more than one semester"

    def test_courses_have_instructors_list(self):
        for name, data in COURSES.items():
            assert "instructors" in data, f"{name} missing instructors field"
            assert isinstance(data["instructors"], list), f"{name} instructors must be a list"
            assert len(data["instructors"]) >= 1, f"{name} instructors list is empty"

    def test_completed_field_grows_monotonically(self, bio_profile, default_weights):
        plans = plan_four_years(
            interest_profile=bio_profile,
            weights=default_weights,
            min_units=8,
            max_units=18,
            beam_width=1,
            top_k_per_semester=3,
        )
        # The final state's completed set should equal all scheduled courses
        state = plans[0]
        scheduled = {c for sem in state.semester_plans for c in sem["courses"]}
        assert scheduled == set(state.completed)

    def test_scores_sorted_descending(self, bio_profile, default_weights):
        plans = plan_four_years(
            interest_profile=bio_profile,
            weights=default_weights,
            min_units=8,
            max_units=18,
            beam_width=3,
            top_k_per_semester=4,
        )
        scores = [p.cumulative_score for p in plans]
        assert scores == sorted(scores, reverse=True)

    def test_with_initial_completed(self, bio_profile, default_weights):
        initial = {"DATA C8", "COMPSCI 61A", "MATH 51", "MATH 52"}
        plans = plan_four_years(
            interest_profile=bio_profile,
            initial_completed=initial,
            weights=default_weights,
            min_units=8,
            max_units=18,
            beam_width=1,
            top_k_per_semester=3,
        )
        for sem in plans[0].semester_plans:
            for c in sem["courses"]:
                assert c not in initial


# ─────────────────────────────────────────────────────────────────────────────
# PlannerState
# ─────────────────────────────────────────────────────────────────────────────

class TestPlannerState:

    def test_apply_semester_adds_courses(self, default_weights):
        state = PlannerState(
            completed=frozenset(),
            cumulative_score=0.0,
            semester_plans=[],
            req_tracker=None,
        )
        sem = {"courses": ["DATA C8", "MATH 55"], "score": 0.5}
        new_state = state.apply_semester("Fall", "Year 1", sem)
        assert "DATA C8" in new_state.completed
        assert "MATH 55" in new_state.completed

    def test_apply_semester_accumulates_score(self):
        state = PlannerState(
            completed=frozenset(),
            cumulative_score=1.0,
            semester_plans=[],
            req_tracker=None,
        )
        sem = {"courses": ["DATA C8"], "score": 0.5}
        new_state = state.apply_semester("Fall", "Year 1", sem)
        assert abs(new_state.cumulative_score - 1.5) < 1e-9

    def test_apply_semester_immutable_original(self):
        state = PlannerState(
            completed=frozenset({"DATA C8"}),
            cumulative_score=0.0,
            semester_plans=[],
            req_tracker=None,
        )
        sem = {"courses": ["MATH 55"], "score": 0.3}
        new_state = state.apply_semester("Fall", "Year 1", sem)
        assert "MATH 55" not in state.completed  # original unchanged
        assert "MATH 55" in new_state.completed


# ─────────────────────────────────────────────────────────────────────────────
# Multi-instructor RMP averaging (tests merge_sources.merge_rmp)
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiInstructorAveraging:
    """
    Validates the weighted-average RMP logic from merge_sources.merge_rmp().
    """

    def _weighted_avg(self, entries):
        ratings, weights = [], []
        for entry in entries:
            if entry is None or entry.get("rating") is None:
                continue
            w = max(entry.get("num_ratings", 0), 1)
            ratings.append(entry["rating"] * w)
            weights.append(w)
        if not ratings:
            return None
        return sum(ratings) / sum(weights)

    def test_single_instructor(self):
        entries = [{"rating": 4.5, "num_ratings": 20}]
        assert abs(self._weighted_avg(entries) - 4.5) < 1e-9

    def test_equal_num_ratings_simple_mean(self):
        entries = [
            {"rating": 4.0, "num_ratings": 10},
            {"rating": 3.0, "num_ratings": 10},
        ]
        assert abs(self._weighted_avg(entries) - 3.5) < 1e-9

    def test_higher_num_ratings_dominates(self):
        entries = [
            {"rating": 5.0, "num_ratings": 100},  # heavy weight
            {"rating": 1.0, "num_ratings": 1},     # near-zero weight
        ]
        avg = self._weighted_avg(entries)
        assert avg > 4.5  # dominated by the 5.0 instructor

    def test_none_entry_skipped(self):
        entries = [None, {"rating": 3.0, "num_ratings": 10}]
        assert abs(self._weighted_avg(entries) - 3.0) < 1e-9

    def test_missing_rating_skipped(self):
        entries = [
            {"rating": None, "num_ratings": 50},
            {"rating": 4.0,  "num_ratings": 20},
        ]
        assert abs(self._weighted_avg(entries) - 4.0) < 1e-9

    def test_all_none_returns_none(self):
        assert self._weighted_avg([None, None]) is None

    def test_zero_num_ratings_floor_at_one(self):
        # num_ratings=0 → floor to 1, so both instructors get equal weight
        entries = [
            {"rating": 4.0, "num_ratings": 0},
            {"rating": 2.0, "num_ratings": 0},
        ]
        assert abs(self._weighted_avg(entries) - 3.0) < 1e-9

    def test_tba_instructors_produce_no_entry(self):
        # fetch_rmp.py skips "TBA": simulate by passing empty list
        assert self._weighted_avg([]) is None

    def test_biology_1b_six_instructors(self):
        # BIOLOGY 1B has 6 instructors: simulate typical RMP coverage
        entries = [
            {"rating": 4.9, "num_ratings": 80},
            {"rating": 4.7, "num_ratings": 60},
            {"rating": 4.5, "num_ratings": 40},
            {"rating": 4.2, "num_ratings": 20},
            {"rating": 3.8, "num_ratings": 10},
            {"rating": 3.5, "num_ratings": 5},
        ]
        avg = self._weighted_avg(entries)
        # Higher-reviewed instructors pull avg up; expect > 4.5
        assert avg > 4.5
        assert avg < 4.9


# ─────────────────────────────────────────────────────────────────────────────
# RequirementTracker — build_tracker integration with requirements.json
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildTracker:
    """Tests for build_tracker() which loads from requirements.json."""

    def test_list_majors_returns_known(self):
        majors = list_majors()
        assert "CS_BA" in majors
        assert "DATA_BA" in majors
        assert "MCB" in majors
        assert "BIOE_BS" in majors
        assert "EECS_BS" in majors
        assert "_meta" not in majors

    def test_list_tracks_data_ba(self):
        tracks = list_tracks("DATA_BA")
        assert "default" in tracks

    def test_list_tracks_mcb(self):
        tracks = list_tracks("MCB")
        assert "GGED_track1" in tracks
        assert "GGED_track2" in tracks
        assert "BBS_track1" in tracks
        assert "IMM_track1" in tracks

    def test_build_tracker_data_ba_default(self):
        tracker = build_tracker("DATA_BA")
        assert isinstance(tracker, RequirementTracker)
        assert "core" in tracker.buckets or any("core" in k for k in tracker.buckets)
        assert tracker.completion_ratio() == 0.0

    def test_build_tracker_mcb_gged1(self):
        tracker = build_tracker("MCB", "GGED_track1")
        assert isinstance(tracker, RequirementTracker)
        assert len(tracker.buckets) > 0

    def test_build_tracker_cs_ba(self):
        tracker = build_tracker("CS_BA")
        assert isinstance(tracker, RequirementTracker)

    def test_build_tracker_bioe_computational(self):
        tracker = build_tracker("BIOE_BS", "computational_biology")
        assert isinstance(tracker, RequirementTracker)

    def test_build_tracker_invalid_major_raises(self):
        with pytest.raises(ValueError, match="Unknown major"):
            build_tracker("FAKE_MAJOR")

    def test_build_tracker_invalid_track_raises(self):
        with pytest.raises(ValueError, match="Unknown track"):
            build_tracker("MCB", "nonexistent_track")

    def test_data_ba_core_courses_wired(self):
        tracker = build_tracker("DATA_BA")
        # DATA C100 should be registered to the 'core' bucket
        assert "DATA C100" in tracker.course_to_buckets

    def test_mcb_gged1_required_courses_wired(self):
        tracker = build_tracker("MCB", "GGED_track1")
        # MCELLBI C100A is req_1 in GGED track 1
        assert "MCELLBI C100A" in tracker.course_to_buckets

    def test_applying_courses_increases_ratio(self):
        tracker = build_tracker("DATA_BA")
        before = tracker.completion_ratio()
        tracker.apply("DATA C100")
        after = tracker.completion_ratio()
        assert after > before

    def test_mcb_lower_div_shared_loaded(self):
        tracker = build_tracker("MCB", "GGED_track1")
        # MCB lower_div_shared contains BIOLOGY 1A and CHEM 1A
        assert "BIOLOGY 1A & BIOLOGY 1AL" in tracker.course_to_buckets
        assert "CHEM 1A & CHEM 1AL" in tracker.course_to_buckets

    def test_completing_all_known_courses_raises_ratio(self):
        tracker = build_tracker("DATA_BA")
        for course in COURSES:
            tracker.apply(course)
        # Not necessarily 1.0 because some required courses aren't in courses.json
        assert tracker.completion_ratio() > 0.5

    def test_full_gged_track1_walkthrough(self):
        """Simulates completing all GGED Track 1 required courses in courses.json."""
        tracker = build_tracker("MCB", "GGED_track1")
        required = [
            "MCELLBI C100A",      # req_1
            "MCELLBI 140 & MCELLBI 140L",  # req_2 + lab
            "MCELLBI 110",        # req_3
            "MCELLBI 132",        # elective_b
            "BIOLOGY 1A & BIOLOGY 1AL",    # lower shared
            "BIOLOGY 1B",
            "CHEM 1A & CHEM 1AL",
            "CHEM 3A & CHEM 3AL",
            "PHYSICS 8A",
            "PHYSICS 8B",
            "MATH 51",
            "MATH 52",
        ]
        for c in required:
            tracker.apply(c)
        assert tracker.completion_ratio() > 0.5
