"""
Semantic Academic Planning Tool
Four-year constraint-based planner with state transitions and DP scoring.
"""

import json
import itertools
import heapq
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

# Optional semantic profile builder (requires embedder index to be built)
try:
    from coursepath.embedder import profile_from_text, profile_from_course_names
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False

# Optional data quality module
try:
    from coursepath.data_quality import score_course, plan_quality_summary
    DATA_QUALITY_AVAILABLE = True
except ImportError:
    DATA_QUALITY_AVAILABLE = False

# ─────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────

with open("coursepath/data/courses.json") as f:
    COURSES: dict = json.load(f)

with open("coursepath/data/requirements.json") as f:
    REQUIREMENTS: dict = json.load(f)


# ─────────────────────────────────────────────
# Prerequisite checker  (recursive, O(n))
# ─────────────────────────────────────────────

def prereq_satisfied(req, taken: set[str]) -> bool:
    """
    Recursively evaluate a prerequisite expression.
    req is one of:
      None                        → always satisfied
      str                         → single course required
      {"and": [req, ...]}         → all sub-reqs must hold
      {"or":  [req, ...]}         → at least one sub-req must hold
    """
    if req is None:
        return True
    if isinstance(req, str):
        return req in taken
    if "and" in req:
        return all(prereq_satisfied(r, taken) for r in req["and"])
    if "or" in req:
        return any(prereq_satisfied(r, taken) for r in req["or"])
    raise ValueError(f"Unknown prerequisite format: {req!r}")


def prereqs_met(course_name: str, taken: set[str]) -> bool:
    return prereq_satisfied(COURSES[course_name]["prerequisites"], taken)


# ─────────────────────────────────────────────
# Prerequisite dependency graph + topological order
# ─────────────────────────────────────────────

def build_prereq_graph() -> dict[str, set[str]]:
    """
    Returns adj[course] = set of courses that directly depend on course
    (i.e., course → courses that list course as a prerequisite leaf).
    Used for topological feasibility checks in multi-year planning.
    """
    def collect_leaves(req) -> set[str]:
        if req is None:
            return set()
        if isinstance(req, str):
            return {req}
        if "and" in req:
            return set().union(*(collect_leaves(r) for r in req["and"]))
        if "or" in req:
            # Under OR, only *one* branch is required: conservatively
            # include all leaves so the planner knows every possible dependency.
            return set().union(*(collect_leaves(r) for r in req["or"]))
        return set()

    adj: dict[str, set[str]] = defaultdict(set)
    for course, data in COURSES.items():
        for dep in collect_leaves(data["prerequisites"]):
            if dep in COURSES:
                adj[dep].add(course)
    return adj


def topological_order() -> list[str]:
    """
    Kahn's algorithm: returns a valid enrollment order respecting prerequisites.
    Courses with no prerequisites come first.
    """
    in_degree: dict[str, int] = {c: 0 for c in COURSES}
    adj = build_prereq_graph()
    for deps in adj.values():
        for d in deps:
            if d in in_degree:
                in_degree[d] += 1

    queue = deque(c for c, deg in in_degree.items() if deg == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    return order


# ─────────────────────────────────────────────
# Major Requirement tracking
# ─────────────────────────────────────────────

@dataclass
class RequirementTracker:
    """
    Tracks fulfillment of named requirement buckets.
    Each bucket has a target count; courses may satisfy one or more buckets.
    """
    buckets: dict[str, int]                       # {bucket_name: courses_needed}
    course_to_buckets: dict[str, list[str]]       # {course_name: [bucket, ...]}
    fulfilled: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.fulfilled = {b: 0 for b in self.buckets}

    def apply(self, course: str) -> None:
        for bucket in self.course_to_buckets.get(course, []):
            if bucket in self.fulfilled:
                self.fulfilled[bucket] = min(
                    self.fulfilled[bucket] + 1, self.buckets[bucket]
                )

    def completion_ratio(self) -> float:
        if not self.buckets:
            return 1.0
        return sum(
            self.fulfilled[b] / self.buckets[b] for b in self.buckets
        ) / len(self.buckets)

    def clone(self) -> "RequirementTracker":
        import copy
        t = RequirementTracker(
            buckets=dict(self.buckets),
            course_to_buckets=self.course_to_buckets,
        )
        t.fulfilled = dict(self.fulfilled)
        return t


# ─────────────────────────────────────────────
# Requirement tracker builder
# ─────────────────────────────────────────────

def build_tracker(major: str, track: str = "default") -> "RequirementTracker":
    """
    Build a RequirementTracker from requirements.json for a given major+track.

    Supports:
      build_tracker("DATA_BA")
      build_tracker("MCB", "GGED_track1")
      build_tracker("BIOE_BS", "computational_biology")

    Only courses present in COURSES are wired up; courses noted as
    'not in courses.json' contribute 0 to completion ratio until added.
    """
    major_data = REQUIREMENTS.get(major)
    if major_data is None:
        raise ValueError(f"Unknown major '{major}'. Available: {list_majors()}")

    tracks_data = major_data.get("tracks", {})
    lower_shared = major_data.get("lower_div_shared", {})

    if track not in tracks_data and track != "default":
        raise ValueError(
            f"Unknown track '{track}' for {major}. "
            f"Available: {list(tracks_data.keys())}"
        )

    chosen = tracks_data.get(track, tracks_data.get("default", {}))

    all_buckets_raw: dict = {}
    for section_name, section in chosen.items():
        if isinstance(section, dict) and ("count" in section or "options" in section):
            all_buckets_raw[section_name] = section
        elif isinstance(section, dict):
            for bucket_name, bucket in section.items():
                if isinstance(bucket, dict) and "count" in bucket:
                    all_buckets_raw[f"{section_name}.{bucket_name}"] = bucket

    for bucket_name, bucket in lower_shared.items():
        if isinstance(bucket, dict) and "count" in bucket:
            all_buckets_raw[f"lower.{bucket_name}"] = bucket

    buckets: dict[str, int] = {}
    course_to_buckets: dict[str, list[str]] = defaultdict(list)

    for bucket_name, bucket_def in all_buckets_raw.items():
        count = bucket_def.get("count", 1)
        buckets[bucket_name] = count
        for course in bucket_def.get("options", []):
            if course in COURSES:
                course_to_buckets[course].append(bucket_name)

    return RequirementTracker(
        buckets=buckets,
        course_to_buckets=dict(course_to_buckets),
    )


def list_majors() -> list[str]:
    """Return all major keys available in requirements.json."""
    return [k for k in REQUIREMENTS if not k.startswith("_")]


def list_tracks(major: str) -> list[str]:
    """Return all track keys for a given major."""
    return list(REQUIREMENTS.get(major, {}).get("tracks", {}).keys())


# ─────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────

def interest_alignment(schedule: tuple[str, ...], interest_profile: dict[str, float]) -> float:
    """Weighted dot product of course topic vectors against the interest profile."""
    if not schedule:
        return 0.0
    total = 0.0
    for course_name in schedule:
        for topic, weight in COURSES[course_name]["topics"].items():
            total += weight * interest_profile.get(topic, 0.0)
    return total / len(schedule)


def score_schedule(
    schedule: tuple[str, ...],
    interest_profile: dict[str, float],
    weights: dict[str, float],
    req_tracker: Optional[RequirementTracker] = None,
) -> float:
    """
    Composite linear score:
      w_interest  · interest_alignment
    − w_difficulty · avg_difficulty
    + w_professor  · avg_professor_rating
    + w_major_progress    · major_progress_delta

    Each course's contribution to interest and professor signals is scaled
    by its data_quality score (confidence weighting).  Difficulty is not
    confidence-weighted because the fallback value is still informative.
    If data_quality is absent, the course is treated as fully confident.
    """
    n = len(schedule)

    # ── Interest alignment (confidence-weighted) ──────────────────────────
    interest_total = 0.0
    weight_sum = 0.0
    for course_name in schedule:
        dq = COURSES[course_name].get("data_quality", 1.0)
        course_sim = sum(
            w * interest_profile.get(t, 0.0)
            for t, w in COURSES[course_name]["topics"].items()
        )
        interest_total += dq * course_sim
        weight_sum += dq
    interest = (interest_total / weight_sum) if weight_sum > 0 else 0.0

    # ── Difficulty (raw average) ────────────────────
    avg_diff = sum(COURSES[c]["difficulty"] for c in schedule) / n

    # ── Professor rating (confidence-weighted) ────────────────────────────
    prof_total = 0.0
    prof_weight = 0.0
    for c in schedule:
        dq = COURSES[c].get("data_quality", 1.0)
        prof_total  += dq * COURSES[c]["professor_rating"]
        prof_weight += dq
    avg_prof = (prof_total / prof_weight) if prof_weight > 0 else 0.0

    # ── Difficulty — blends rmp_difficulty with hand-authored value ────────
    # rmp_difficulty comes from RMP DOM scrape; hand-authored difficulty is
    # the manually set value in courses.json.  When both exist, rmp gets 60%
    # weight. Both are confidence-weighted by data_quality.
    diff_total = 0.0
    diff_weight = 0.0
    for c in schedule:
        dq    = COURSES[c].get("data_quality", 1.0)
        rmp_d = COURSES[c].get("rmp_difficulty")
        base_d = COURSES[c]["difficulty"]
        blended = (rmp_d * 0.6 + base_d * 0.4) if rmp_d is not None else base_d
        diff_total  += dq * blended
        diff_weight += dq
    avg_diff_blended = (diff_total / diff_weight) if diff_weight > 0 else avg_diff

    # ── Would-take-again bonus (confidence-weighted, 0-100 → 0-1) ─────────
    wta_total = 0.0
    wta_weight = 0.0
    for c in schedule:
        wta = COURSES[c].get("would_take_again")
        if wta is not None:
            dq = COURSES[c].get("data_quality", 1.0)
            wta_total  += dq * (wta / 100.0)
            wta_weight += dq
    avg_wta = (wta_total / wta_weight) if wta_weight > 0 else 0.0

    # ── Major progress bonus ───────────────────────────────────────────────
    major_progress_bonus = 0.0
    if req_tracker is not None:
        before = req_tracker.completion_ratio()
        temp = req_tracker.clone()
        for c in schedule:
            temp.apply(c)
        after = temp.completion_ratio()
        major_progress_bonus = after - before

    return (
        weights.get("interest", 1.0)           * interest
        - weights.get("difficulty", 0.5)       * avg_diff_blended
        + weights.get("professor", 0.3)        * avg_prof
        + weights.get("would_take_again", 0.2) * avg_wta
        + weights.get("major_progress", 0.2)   * major_progress_bonus
    )



# ─────────────────────────────────────────────
# Single-semester planner
# ─────────────────────────────────────────────

def valid_schedule(schedule: tuple[str, ...], min_units: int = 8, max_units: int = 18) -> bool:
    total = sum(COURSES[c]["units"] for c in schedule)
    return min_units <= total <= max_units


def generate_semester_plans(
    completed: set[str],
    interest_profile: dict[str, float],
    term: Optional[str] = None,
    min_units: int = 8,
    max_units: int = 18,
    weights: Optional[dict[str, float]] = None,
    top_k: int = 5,
    req_tracker: Optional[RequirementTracker] = None,
    exclude: Optional[set[str]] = None,
) -> list[dict]:
    """
    Enumerate feasible one-semester course combinations and return the top-k by score.
    Uses a min-heap of size top_k to avoid materializing all combinations.
    """
    if weights is None:
        weights = {"interest": 1.0, "difficulty": 0.5, "professor": 0.3}
    if exclude is None:
        exclude = set()

    available = [
        c for c in COURSES
        if c not in completed
        and c not in exclude
        and prereqs_met(c, completed)
        and (term is None or term in COURSES[c]["terms_offered"])
    ]

    heap: list[tuple[float, tuple[str, ...]]] = []

    for r in range(1, min(len(available), 6) + 1):   # cap combo size at 6 for performance
        for sched in itertools.combinations(available, r):
            if not valid_schedule(sched, min_units, max_units):
                continue
            sc = score_schedule(sched, interest_profile, weights, req_tracker)
            if len(heap) < top_k:
                heapq.heappush(heap, (sc, sched))
            elif sc > heap[0][0]:
                heapq.heapreplace(heap, (sc, sched))

    results = []
    for sc, s in sorted(heap, key=lambda x: -x[0]):
        entry: dict = {"courses": list(s), "score": round(sc, 4)}
        if DATA_QUALITY_AVAILABLE:
            entry["quality"] = plan_quality_summary(list(s), COURSES)
        results.append(entry)
    return results


# ─────────────────────────────────────────────
# Four-year (multi-semester) planner
# Uses greedy DP with beam search across semesters
# ─────────────────────────────────────────────

TERM_SEQUENCE = [
    ("Fall",   "Year 1"), ("Spring", "Year 1"),
    ("Fall",   "Year 2"), ("Spring", "Year 2"),
    ("Fall",   "Year 3"), ("Spring", "Year 3"),
    ("Fall",   "Year 4"), ("Spring", "Year 4"),
]


@dataclass
class PlannerState:
    """Immutable snapshot of academic progress at the start of a semester."""
    completed: frozenset[str]
    cumulative_score: float
    semester_plans: list[dict]          # list of {term, year, courses, score}
    req_tracker: Optional[RequirementTracker]

    def apply_semester(self, term: str, year: str, sched: dict) -> "PlannerState":
        new_completed = self.completed | frozenset(sched["courses"])
        new_rt = None
        if self.req_tracker is not None:
            new_rt = self.req_tracker.clone()
            for c in sched["courses"]:
                new_rt.apply(c)
        return PlannerState(
            completed=new_completed,
            cumulative_score=self.cumulative_score + sched["score"],
            semester_plans=self.semester_plans + [{
                "term": term, "year": year, **sched
            }],
            req_tracker=new_rt,
        )


def plan_four_years(
    interest_profile: dict[str, float],
    initial_completed: Optional[set[str]] = None,
    weights: Optional[dict[str, float]] = None,
    min_units: int = 12,
    max_units: int = 18,
    beam_width: int = 5,
    top_k_per_semester: int = 8,
    req_tracker: Optional[RequirementTracker] = None,
) -> list[PlannerState]:
    """
    Beam search over eight semesters.

    At each semester we:
      1. For every state in the beam, generate top_k_per_semester single-semester plans.
      2. Expand each (state, plan) pair into a new state.
      3. Keep only the beam_width states with the highest cumulative score.

    Complexity: O(beam_width × top_k × 2^|available| per semester).
    The inner combination loop is bounded by capping schedule size at 6 courses.

    Returns the beam_width best complete four-year plan states.
    """
    if weights is None:
        weights = {"interest": 1.0, "difficulty": 0.5, "professor": 0.3, "major_progress": 0.2}
    if initial_completed is None:
        initial_completed = set()

    init_rt = req_tracker.clone() if req_tracker else None
    beam: list[PlannerState] = [
        PlannerState(
            completed=frozenset(initial_completed),
            cumulative_score=0.0,
            semester_plans=[],
            req_tracker=init_rt,
        )
    ]

    for term, year in TERM_SEQUENCE:
        next_beam: list[PlannerState] = []

        for state in beam:
            semester_options = generate_semester_plans(
                completed=set(state.completed),
                interest_profile=interest_profile,
                term=term,
                min_units=min_units,
                max_units=max_units,
                weights=weights,
                top_k=top_k_per_semester,
                req_tracker=state.req_tracker,
            )
            if not semester_options:
                # No valid schedule found; carry state forward with empty semester
                next_beam.append(state)
                continue
            for plan in semester_options:
                next_beam.append(state.apply_semester(term, year, plan))

        # Prune beam to top beam_width states by cumulative score
        next_beam.sort(key=lambda s: -s.cumulative_score)
        beam = next_beam[:beam_width]

    return beam


# ─────────────────────────────────────────────
# Interactive helpers
# ─────────────────────────────────────────────

def collect_topics() -> list[str]:
    all_topics: set[str] = set()
    for c in COURSES.values():
        all_topics.update(c.get("topics", {}).keys())
    return sorted(all_topics)


def get_interest_profile(topics: list[str]) -> dict[str, float]:
    print("\nRate your interest in each topic (0.0 – 1.0):")
    profile: dict[str, float] = {}
    for t in topics:
        while True:
            try:
                val = float(input(f"  {t}: "))
                if 0.0 <= val <= 1.0:
                    profile[t] = val
                    break
                print("  ↳ Please enter a value between 0 and 1.")
            except ValueError:
                print("  ↳ Invalid input.")
    return profile


def get_weights() -> dict[str, float]:
    print("\nSet scoring weights (suggested defaults — press Enter to accept):")
    return {
        "interest":         float(input("  Interest alignment weight  (1.0): ") or 1.0),
        "difficulty":       float(input("  Difficulty penalty weight  (0.5): ") or 0.5),
        "professor":        float(input("  Professor quality weight   (0.3): ") or 0.3),
        "would_take_again": float(input("  Would-take-again weight    (0.2): ") or 0.2),
        "major_progress":   float(input("  Major progress weight      (0.2): ") or 0.2),
    }


def print_four_year_plan(state: PlannerState) -> None:
    print(f"\n{'═'*60}")
    print(f"  4-Year Plan  |  Cumulative Score: {state.cumulative_score:.3f}")
    print(f"{'═'*60}")
    for sem in state.semester_plans:
        print(f"\n  {sem['year']}  {sem['term']}  (score: {sem['score']:.3f})")
        for c in sem["courses"]:
            units = COURSES[c]["units"]
            diff  = COURSES[c]["difficulty"]
            print(f"    • {c:<40}  {units} units  diff={diff}")
    courses_taken = set(state.completed)
    print(f"\n  Total courses completed: {len(courses_taken)}")
    if state.req_tracker:
        print(f"  Major progress:     {state.req_tracker.completion_ratio():.0%}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # ── Interest profile ──────────────────────────────────────────────────
    if EMBEDDER_AVAILABLE:
        profile_mode = input(
            "Interest profile input:\n"
            "  (1) type free-text description  [uses semantic embeddings]\n"
            "  (2) rate topics manually        [classic sliders]\n"
            "  (3) list courses you enjoyed    [derives profile from past courses]\n"
            "Choice [1/2/3]: "
        ).strip()
    else:
        profile_mode = "2"
        print("(embedder not available; using manual topic rating)")

    if profile_mode == "1" and EMBEDDER_AVAILABLE:
        user_text = input("\nDescribe your academic interests in a sentence or two:\n> ")
        interest_profile = profile_from_text(user_text)
        print(f"\nDerived profile ({len(interest_profile)} tags):")
        for tag, w in sorted(interest_profile.items(), key=lambda x: -x[1])[:10]:
            print(f"  {tag:<35} {w:.3f}")
    elif profile_mode == "3" and EMBEDDER_AVAILABLE:
        raw = input("\nEnter course names you enjoyed (comma-separated):\n> ")
        liked = [c.strip() for c in raw.split(",")]
        interest_profile = profile_from_course_names(liked)
        print(f"\nDerived profile ({len(interest_profile)} tags):")
        for tag, w in sorted(interest_profile.items(), key=lambda x: -x[1])[:10]:
            print(f"  {tag:<35} {w:.3f}")
    else:
        topics = collect_topics()
        interest_profile = get_interest_profile(topics)

    weights = get_weights()

    # ── Completed courses ─────────────────────────────────────────────────────
    print("\nEnter courses you have already completed (comma-separated),")
    print("or leave blank to start from scratch.")
    print(f"Known courses: {', '.join(sorted(COURSES.keys())[:8])} …")
    raw_completed = input("> ").strip()
    completed: set[str] = set()
    if raw_completed:
        for c in [x.strip() for x in raw_completed.split(",")]:
            if c in COURSES:
                completed.add(c)
            elif c:
                print(f"  ⚠ '{c}' not in courses.json — skipped")
    if completed:
        print(f"  Loaded {len(completed)} completed courses: {', '.join(sorted(completed))}")

    # ── Major + track selection (supports multiple majors) ───────────────────
    majors = list_majors()
    print(f"\nAvailable majors: {', '.join(majors)}")
    print("Enter one or more major keys separated by commas, or leave blank to skip.")
    print("Example: DATA_BA, MCB")
    raw_majors = input("> ").strip()

    req_tracker = None
    if raw_majors:
        chosen_majors = [m.strip().upper() for m in raw_majors.split(",") if m.strip()]
        trackers = []
        for chosen_major in chosen_majors:
            if chosen_major not in majors:
                print(f"  ⚠ '{chosen_major}' not recognised; skipped")
                continue
            tracks = list_tracks(chosen_major)
            if tracks and tracks != ["default"]:
                print(f"\n  Tracks for {chosen_major}: {', '.join(tracks)}")
                chosen_track = input(f"  Track for {chosen_major} (or Enter for default): ").strip() or "default"
            else:
                chosen_track = "default"
            try:
                t = build_tracker(chosen_major, chosen_track)
                trackers.append((chosen_major, chosen_track, t))
                print(f"  ✓ {chosen_major} / {chosen_track} — {len(t.buckets)} requirement buckets")
            except ValueError as e:
                print(f"  ⚠ {e} — skipped")

        if trackers:
            if len(trackers) == 1:
                req_tracker = trackers[0][2]
            else:
                # Merge multiple trackers: combine all buckets and course mappings
                merged_buckets: dict = {}
                merged_c2b: dict = {}
                for major_key, track_key, t in trackers:
                    prefix = f"{major_key}"
                    for bucket, count in t.buckets.items():
                        merged_buckets[f"{prefix}.{bucket}"] = count
                    for course, buckets in t.course_to_buckets.items():
                        prefixed = [f"{prefix}.{b}" for b in buckets]
                        if course in merged_c2b:
                            merged_c2b[course].extend(prefixed)
                        else:
                            merged_c2b[course] = prefixed
                req_tracker = RequirementTracker(
                    buckets=merged_buckets,
                    course_to_buckets=merged_c2b,
                )
                total = sum(len(t.buckets) for _, _, t in trackers)
                print(f"\n  Merged {len(trackers)} majors → {total} total requirement buckets")

    mode = input("\nMode — (1) single semester  (2) multi-semester plan [1/2]: ").strip()

    if mode == "2":
        n_sems = input("How many semesters to plan (default 8 = 4 years)? ").strip()
        n_sems = int(n_sems) if n_sems.isdigit() else 8
        print(f"\nGenerating {n_sems//2}-year plan (beam search)…")
        plans = plan_four_years(
            interest_profile=interest_profile,
            initial_completed=completed,
            weights=weights,
            min_units=12,
            max_units=18,
            beam_width=3,
            req_tracker=req_tracker,
        )
        for i, plan in enumerate(plans, 1):
            print(f"\n{'─'*60}\nPlan {i}")
            print_four_year_plan(plan)
    else:
        term = input("Term (Fall/Spring, or leave blank for any): ").strip() or None
        plans = generate_semester_plans(
            completed=completed,
            interest_profile=interest_profile,
            term=term,
            weights=weights,
            top_k=5,
            req_tracker=req_tracker,
        )
        print("\nTop 5 Recommended Schedules:")
        for i, plan in enumerate(plans, 1):
            q = plan.get("quality", {})
            quality_note = (
                f"  [data quality: {q.get('label','?')} · "
                f"avg={q.get('mean',0):.2f}"
                + (f" · ⚠ low confidence: {', '.join(q['low_confidence'])}"
                   if q.get("low_confidence") else "")
                + "]"
            ) if q else ""
            print(f"\nPlan {i} | Score: {plan['score']}{quality_note}")
            for c in plan["courses"]:
                dq = COURSES[c].get("data_quality", None)
                dq_str = f"  [dq={dq:.2f}]" if dq is not None else ""
                print(f"  - {c}{dq_str}")


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

def test_prereq_satisfied():
    taken = {"MATH 51", "PHYSICS 7A", "BIOENG 11"}
    assert prereq_satisfied("MATH 51", taken)
    assert prereq_satisfied({"and": ["MATH 51", "PHYSICS 7A"]}, taken)
    assert prereq_satisfied({"or": ["BIOLOGY 1A", "BIOENG 11"]}, taken)
    assert not prereq_satisfied("COMPSCI 61A", taken)
    print("✓ test_prereq_satisfied")


def test_topological_order():
    order = topological_order()
    pos = {c: i for i, c in enumerate(order)}
    for course, data in COURSES.items():
        if course not in pos:
            continue
        def check(req):
            if req is None: return
            if isinstance(req, str):
                if req in pos:
                    assert pos[req] < pos[course], \
                        f"Topo violation: {req} should come before {course}"
            elif "and" in req:
                for r in req["and"]: check(r)
            elif "or" in req:
                pass  # OR deps are optional; skip strict check
        check(data["prerequisites"])
    print("✓ test_topological_order")


def test_single_semester():
    profile = {"bioinformatics": 1.0, "python": 0.8, "statistics": 0.6}
    plans = generate_semester_plans(
        completed={"MATH 51", "MATH 52"},
        interest_profile=profile,
        min_units=8,
        max_units=16,
        top_k=3,
    )
    assert plans, "Expected at least one plan"
    assert all("courses" in p and "score" in p for p in plans)
    print("✓ test_single_semester")


def test_four_year_plan():
    profile = {"bioinformatics": 1.0, "python": 0.8, "statistics": 0.6, "genetics": 0.7}
    plans = plan_four_years(
        interest_profile=profile,
        min_units=8,
        max_units=18,
        beam_width=2,
        top_k_per_semester=4,
    )
    assert plans
    assert len(plans[0].semester_plans) == 8
    print("✓ test_four_year_plan")


if __name__ == "__test__":
    test_prereq_satisfied()
    test_topological_order()
    test_single_semester()
    test_four_year_plan()
