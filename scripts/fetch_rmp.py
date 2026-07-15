"""
scripts/fetch_rmp.py — RateMyProfessors cache builder.

Reads the instructor list from courses.json, scrapes RMP for each one,
and writes data/rmp_cache.json (gitignored).

Run once per semester, or whenever the instructor list changes.

Usage:
    conda activate coursepath
    python scripts/fetch_rmp.py [--force]

    --force   re-scrape instructors that are already in rmp_cache.json
              (default: skip existing entries to save time)

Dependencies:
    pip install RateMyProfessorAPI   (already in environment.yml)
"""

import json
import os
import time
import argparse

try:
    import ratemyprofessor
except ImportError:
    raise SystemExit("Run: pip install RateMyProfessorAPI")

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSES_PATH = os.path.join(ROOT, "coursepath", "data", "courses.json")
CACHE_PATH   = os.path.join(ROOT, "coursepath", "data", "rmp_cache.json")

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def collect_instructors(courses: dict) -> list[str]:
    """
    Pull all unique instructor names from courses.json.
    Reads the "instructors" list field; skips "TBA" entries.
    """
    instructors = set()
    for data in courses.values():
        for name in data.get("instructors", []):
            if name and name != "TBA":
                instructors.add(name)
    return sorted(instructors)


def scrape_professor(school, name: str) -> dict | None:
    """
    Return a dict of RMP fields for one professor, or None if not found.
    Catches all exceptions so one bad lookup doesn't abort the run.
    """
    try:
        prof = ratemyprofessor.get_professor_by_school_and_name(school, name)
        if prof is None:
            return None
        return {
            "rating":        prof.rating,
            "difficulty":    prof.difficulty,
            "num_ratings":   prof.num_ratings,
            "would_take_again": getattr(prof, "would_take_again", None),
            "department":    getattr(prof, "department", None),
        }
    except Exception as e:
        print(f"    ⚠ exception for '{name}': {e}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def run(force: bool = False) -> None:
    with open(COURSES_PATH) as f:
        courses = json.load(f)

    instructors = collect_instructors(courses)

    if not instructors:
        print(
            "No instructors found in courses.json.\n"
            "Add an 'instructor' field to each course record first, e.g.:\n"
            '  "instructor": "John DeNero"'
        )
        return

    cache = load_cache()

    to_scrape = (
        instructors if force
        else [i for i in instructors if i not in cache]
    )

    if not to_scrape:
        print(f"All {len(instructors)} instructors already cached. "
              "Use --force to re-scrape.")
        return

    print(f"Looking up Berkeley school on RateMyProfessors…")
    school = ratemyprofessor.get_school_by_name("University of California Berkeley")
    if school is None:
        raise SystemExit("Could not find UC Berkeley on RateMyProfessors. "
                         "Check your internet connection.")
    print(f"Found: {school.name} (id={school.id})\n")

    print(f"Scraping {len(to_scrape)} instructors "
          f"({len(instructors) - len(to_scrape)} already cached)…\n")

    for i, name in enumerate(to_scrape, 1):
        print(f"  [{i:>3}/{len(to_scrape)}] {name}", end="  ", flush=True)
        result = scrape_professor(school, name)

        if result:
            n = result["num_ratings"]
            r = result["rating"]
            low_conf = " ⚠ low confidence (<5 ratings)" if n < 5 else ""
            print(f"★ {r}  ({n} ratings){low_conf}")
        else:
            print("not found")

        cache[name] = result

        # Write after every entry — crash-safe
        save_cache(cache)

        # Stay well inside RMP's rate limits
        if i < len(to_scrape):
            time.sleep(1.2)

    # ── Summary ───────────────────────────────────────────────────────────────
    found     = sum(1 for v in cache.values() if v is not None)
    not_found = sum(1 for v in cache.values() if v is None)
    low_conf  = sum(
        1 for v in cache.values()
        if v and v.get("num_ratings", 0) < 5
    )

    print(f"\nDone.")
    print(f"  Found:          {found}")
    print(f"  Not found:      {not_found}  (will use department median as fallback)")
    print(f"  Low confidence: {low_conf}  (<5 ratings — treat with caution)")
    print(f"  Cache saved to: {CACHE_PATH}")
    print(f"\nNext step: run merge_sources.py to fold ratings into courses.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape RateMyProfessors for Berkeley instructors")
    parser.add_argument("--force", action="store_true",
                        help="Re-scrape instructors already in cache")
    args = parser.parse_args()
    run(force=args.force)
