"""
Per-course data quality (confidence) scoring.

Each course in courses.json may have some signals fully populated,
partially populated, or absent. This module computes a data_quality
score in [0, 1] for every course and optionally embeds it directly
into the course records.

The score is a weighted average of signal presence:

  Signal                Weight   How presence is judged
  ──────────────────────────────────────────────────────
  manually_reviewed     0.30     courses[c]["manually_reviewed"] == True
  descriptors           0.20     len(descriptors) >= 3
  extended_topics       0.15     len(topics) >= 4 (uses expanded taxonomy)
  professor_rating      0.15     rating exists AND num_ratings >= 5
  grade_distribution    0.10     "grade_dist" key present with >= 3 entries
  sis_verified          0.10     "sis_verified" == True (set by fetcher.py)

Weights are exposed as SIGNAL_WEIGHTS so users can tune them without
touching the logic.

  # Score a single course record (dict)
  q = score_course(course_data)         

  # Write data_quality into every course in courses.json
  annotate_all()
"""

import json
import os
from typing import Any

DATA_DIR     = os.path.join(os.path.dirname(__file__), "data")
COURSES_PATH = os.path.join(DATA_DIR, "courses.json")

# ─────────────────────────────────────────────
# Signal weights  (must sum to 1.0)
# ─────────────────────────────────────────────

SIGNAL_WEIGHTS: dict[str, float] = {
    "manually_reviewed": 0.25,
    "descriptors":       0.20,
    "extended_topics":   0.15,
    "professor_rating":  0.15,
    "would_take_again":  0.10,
    "grade_distribution":0.10,
    "sis_verified":      0.05,
}

assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9, \
    "SIGNAL_WEIGHTS must sum to 1.0"


# ─────────────────────────────────────────────
# Per-signal presence check
# Returns float in [0, 1] per signal (partial credit possible)
# ─────────────────────────────────────────────

def _signal_manually_reviewed(data: dict) -> float:
    return 1.0 if data.get("manually_reviewed") is True else 0.0


def _signal_descriptors(data: dict) -> float:
    descs = data.get("descriptors", [])
    if len(descs) >= 5:  return 1.0
    if len(descs) >= 3:  return 0.7
    if len(descs) >= 1:  return 0.3
    return 0.0


def _signal_extended_topics(data: dict) -> float:
    topics = data.get("topics", {})
    if len(topics) >= 6:  return 1.0
    if len(topics) >= 4:  return 0.7
    if len(topics) >= 2:  return 0.4
    return 0.0


def _signal_professor_rating(data: dict) -> float:
    rating = data.get("professor_rating")
    n      = data.get("num_ratings", 0)
    if rating is None:  return 0.0
    if n >= 20:  return 1.0
    if n >= 5:   return 0.7
    if n >= 1:   return 0.4
    # Rating exists but num_ratings not recorded: give partial credit
    return 0.5


def _signal_grade_distribution(data: dict) -> float:
    dist = data.get("grade_dist", {})
    if len(dist) >= 5:  return 1.0
    if len(dist) >= 3:  return 0.6
    if len(dist) >= 1:  return 0.3
    return 0.0


def _signal_sis_verified(data: dict) -> float:
    return 1.0 if data.get("sis_verified") is True else 0.0


def _signal_would_take_again(data: dict) -> float:
    """
    Presence of a would_take_again percentage (0–100).
    Partial credit tiers based on value:
      >= 80%: excellent engagement signal  → 1.0
      >= 60%: good                         → 0.7
      any value present                    → 0.4
      absent                               → 0.0
    """
    wta = data.get("would_take_again")
    if wta is None:  return 0.0
    if wta >= 80:    return 1.0
    if wta >= 60:    return 0.7
    return 0.4


# ─────────────────────────────────────────────
# Map signal names to presence functions
# Add new signals here without touching score_course()
# ─────────────────────────────────────────────

_SIGNAL_FNS: dict[str, Any] = {
    "manually_reviewed":  _signal_manually_reviewed,
    "descriptors":        _signal_descriptors,
    "extended_topics":    _signal_extended_topics,
    "professor_rating":   _signal_professor_rating,
    "would_take_again":   _signal_would_take_again,
    "grade_distribution": _signal_grade_distribution,
    "sis_verified":       _signal_sis_verified,
}


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def score_course(data: dict) -> float:
    """
    Compute data quality score for a single course record.
    Returns float in [0.0, 1.0].
    """
    score = 0.0
    for signal, weight in SIGNAL_WEIGHTS.items():
        fn = _SIGNAL_FNS[signal]
        score += weight * fn(data)
    return round(score, 4)


def breakdown(data: dict) -> dict[str, float]:
    """
    Return per-signal presence scores (before weighting).
    """
    return {
        signal: _SIGNAL_FNS[signal](data)
        for signal in SIGNAL_WEIGHTS
    }


def quality_label(score: float) -> str:
    """Human-readable quality tier for display in the UI."""
    if score >= 0.80: return "high"
    if score >= 0.50: return "medium"
    if score >= 0.25: return "low"
    return "minimal"


def annotate_all(courses_path: str = COURSES_PATH) -> None:
    """
    Compute data_quality for every course and write it back to courses.json.
    Safe to re-run at any time.
    """
    with open(courses_path) as f:
        courses: dict = json.load(f)

    for name, data in courses.items():
        courses[name]["data_quality"] = score_course(data)

    with open(courses_path, "w") as f:
        json.dump(courses, f, indent=2)

    scores = [d["data_quality"] for d in courses.values()]
    avg = sum(scores) / len(scores)
    print(f"Annotated {len(courses)} courses. Mean data quality: {avg:.3f}")
    dist = {"high": 0, "medium": 0, "low": 0, "minimal": 0}
    for s in scores:
        dist[quality_label(s)] += 1
    for tier, count in dist.items():
        print(f"  {tier:<8} {count}")


def plan_quality_summary(course_names: list[str], courses: dict) -> dict:
    """
    Summarise data quality across a set of courses (e.g., one semester plan).
    Returns:
      {
        "mean": float,
        "min":  float,
        "low_confidence": list[str],   # courses with quality < 0.30
        "label": str,                  # overall tier
      }
    """
    scores = {c: courses[c].get("data_quality", score_course(courses[c]))
              for c in course_names if c in courses}
    if not scores:
        return {"mean": 0.0, "min": 0.0, "low_confidence": [], "label": "minimal"}

    mean = sum(scores.values()) / len(scores)
    return {
        "mean": round(mean, 4),
        "min":  round(min(scores.values()), 4),
        "low_confidence": [c for c, s in scores.items() if s < 0.30],
        "label": quality_label(mean),
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Annotate courses.json with data_quality scores")
    parser.add_argument("--show", action="store_true",
                        help="Print per-course scores without writing")
    args = parser.parse_args()

    with open(COURSES_PATH) as f:
        courses = json.load(f)

    if args.show:
        print(f"{'Course':<45} {'Score':>6}  {'Label':<8}  Signals")
        print("─" * 90)
        for name, data in sorted(courses.items()):
            sc = score_course(data)
            bd = breakdown(data)
            flags = "  ".join(
                f"{sig}={v:.1f}" for sig, v in bd.items() if v > 0
            )
            print(f"{name:<45} {sc:>6.3f}  {quality_label(sc):<8}  {flags}")
    else:
        annotate_all()
