"""
Merge external data sources into courses.json.

Reads:
  data/rmp_cache.json         (from fetch_rmp.py)
  data/sis_classes_raw.json   (from fetch_sis.py, optional)

Updates courses.json in-place with:
  - professor_rating, num_ratings  (from RMP)
  - sis_verified = True            (if course found in SIS data)
  - grade_dist                     (from SIS grade distributions)

Existing hand-authored fields (prerequisites, topics, units) are never
overwritten; external data only fills in or updates the signal fields.

Usage:
    python scripts/merge_sources.py [--rmp-only] [--sis-only]
"""

import json
import os
import argparse

ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSES_PATH = os.path.join(ROOT, "coursepath", "data", "courses.json")
RMP_PATH     = os.path.join(ROOT, "coursepath", "data", "rmp_cache.json")
SIS_PATH     = os.path.join(ROOT, "coursepath", "data", "sis_classes_raw.json")


def merge_rmp(courses: dict, rmp_cache: dict) -> int:
    """
    Update professor_rating and num_ratings from rmp_cache.

    For courses with multiple instructors, averages their RMP ratings
    weighted by num_ratings (more-reviewed instructors count more).
    Instructors not found in cache or with None rating are skipped.

    Returns count of courses updated.
    """
    updated = 0
    for name, data in courses.items():
        instructors = [i for i in data.get("instructors", []) if i != "TBA"]
        if not instructors:
            continue

        ratings, weights, difficulties = [], [], []
        for instructor in instructors:
            entry = rmp_cache.get(instructor)
            if not entry:
                continue
            rating = entry.get("rating")
            n      = entry.get("num_ratings", 0)
            diff   = entry.get("difficulty")
            if rating is None:
                continue
            w = max(n, 1)   # weight by review count; floor at 1 to avoid zero-weight
            ratings.append(rating * w)
            weights.append(w)
            if diff is not None:
                difficulties.append(diff * w)

        if not ratings:
            continue

        total_weight = sum(weights)
        avg_rating   = sum(ratings) / total_weight
        total_n      = sum(w for w in weights)

        # Only overwrite if have more data than before
        old_n = data.get("num_ratings", 0)
        if total_n >= old_n:
            courses[name]["professor_rating"] = round(avg_rating, 2)
            courses[name]["num_ratings"]      = int(total_n)
            if difficulties:
                courses[name]["rmp_difficulty"] = round(sum(difficulties) / total_weight, 2)
            updated += 1

    return updated


def merge_sis(courses: dict, sis_raw: dict) -> int:
    """
    Update sis_verified and grade_dist from SIS raw data.

    SIS course IDs look like 'COMPSCI-061A'; courses.json keys look like
    'COMPSCI 61A'.  Normalised both to uppercase, no leading zeros,
    space-separated for matching.
    """
    def normalise(s: str) -> str:
        return s.upper().replace("-", " ").lstrip("0").strip()

    # Build a lookup from normalised SIS course ID to grade distribution
    grade_lookup: dict[str, dict] = {}
    for course_id, dist in sis_raw.get("grade_distributions", {}).items():
        grade_lookup[normalise(course_id)] = dist

    # Build a set of normalised SIS course IDs for sis_verified
    sis_ids: set[str] = set()
    for cls in sis_raw.get("classes", []):
        raw_id = (
            cls.get("course", {})
               .get("identifiers", [{}])[0]
               .get("id", "")
        )
        if raw_id:
            sis_ids.add(normalise(raw_id))

    updated = 0
    for name, data in courses.items():
        norm_name = normalise(name)

        if norm_name in sis_ids:
            courses[name]["sis_verified"] = True

        dist = grade_lookup.get(norm_name)
        if dist:
            courses[name]["grade_dist"] = dist
            updated += 1

    return updated


def run(use_rmp: bool = True, use_sis: bool = True) -> None:
    with open(COURSES_PATH) as f:
        courses = json.load(f)

    if use_rmp:
        if not os.path.exists(RMP_PATH):
            print(f"RMP cache not found at {RMP_PATH} — skipping RMP merge.")
            print("Run scripts/fetch_rmp.py first.")
        else:
            with open(RMP_PATH) as f:
                rmp_cache = json.load(f)
            n = merge_rmp(courses, rmp_cache)
            print(f"RMP: updated {n} courses with professor ratings")

    if use_sis:
        if not os.path.exists(SIS_PATH):
            print(f"SIS raw data not found at {SIS_PATH} — skipping SIS merge.")
            print("Run scripts/fetch_sis.py first (requires SIS credentials).")
        else:
            with open(SIS_PATH) as f:
                sis_raw = json.load(f)
            n = merge_sis(courses, sis_raw)
            print(f"SIS: marked sis_verified, updated {n} courses with grade distributions")

    with open(COURSES_PATH, "w") as f:
        json.dump(courses, f, indent=2)

    print(f"\nMerged data written to {COURSES_PATH}")
    print("Next step: run coursepath/annotator.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge RMP and SIS data into courses.json")
    parser.add_argument("--rmp-only", action="store_true")
    parser.add_argument("--sis-only", action="store_true")
    args = parser.parse_args()

    use_rmp = not args.sis_only
    use_sis = not args.rmp_only
    run(use_rmp=use_rmp, use_sis=use_sis)
