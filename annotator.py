"""
LLM-powered course annotation pipeline.

Reads courses.json + tag_taxonomy.json, calls the Anthropic API once per
unannotated course, and writes the enriched records back to courses.json.

Run once (or re-run on new courses) to populate:
  - "descriptors": list[str]; free-form keywords from course description
  - "topics": dict[str,float]; extended tag weights using the full taxonomy
  - "manually_reviewed": bool; always False from this script; flip manually

Usage:
  python -m coursepath.annotator [--force]   # re-annotates all courses
"""

import json
import os
import sys
import time
import argparse
import anthropic

DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
COURSES_PATH  = os.path.join(DATA_DIR, "courses.json")
TAXONOMY_PATH = os.path.join(DATA_DIR, "tag_taxonomy.json")


# ─────────────────────────────────────────────
# Prompt construction
# ─────────────────────────────────────────────

def build_prompt(course_name: str, course_data: dict, tag_descriptions: dict[str, str]) -> str:
    tag_block = "\n".join(
        f'  "{tag}": "{desc}"'
        for tag, desc in tag_descriptions.items()
    )
    existing_topics = json.dumps(course_data.get("topics", {}), indent=2)

    return f"""You are annotating a UC Berkeley course for an academic planning system.

Course: {course_name}
Units: {course_data.get("units")}
Existing topic weights (may be incomplete): {existing_topics}

Your task is to produce two things:

1. "descriptors": A list of 5–12 short free-form keyword phrases (2–5 words each)
   that a student might use when searching for this course. Focus on what skills
   are practiced, what problems are solved, and what career paths it prepares for.
   Examples: "sequence alignment algorithms", "Jupyter notebook workflows",
   "molecular cloning techniques", "causal inference with observational data".

2. "topics": A dict mapping tag names to weights (0.0–1.0) reflecting how much
   instructional emphasis each tag receives. Weights do NOT need to sum to 1 —
   each tag is scored independently. Only include tags with weight >= 0.05.
   Use the tag weights from the existing topics as a starting point and expand
   them using the full taxonomy below.

Available tags and their meanings:
{tag_block}

Respond ONLY with a valid JSON object. No explanation, no markdown fences.
Example format:
{{
  "descriptors": ["example keyword phrase", "another phrase"],
  "topics": {{
    "python": 0.5,
    "statistics": 0.4,
    "data_analysis": 0.3
  }}
}}"""


# ─────────────────────────────────────────────
# Annotation
# ─────────────────────────────────────────────

def annotate_course(
    client: anthropic.Anthropic,
    course_name: str,
    course_data: dict,
    tag_descriptions: dict[str, str],
) -> dict:
    """
    Call claude-sonnet-4-20250514 to annotate one course.
    Returns {"descriptors": [...], "topics": {...}} or raises on parse failure.
    """
    prompt = build_prompt(course_name, course_data, tag_descriptions)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    # Strip accidental markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)

    # Validate structure
    if "descriptors" not in result or "topics" not in result:
        raise ValueError(f"Missing keys in response for {course_name}: {result}")
    if not isinstance(result["descriptors"], list):
        raise ValueError("descriptors must be a list")
    if not isinstance(result["topics"], dict):
        raise ValueError("topics must be a dict")

    return result


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def run(force: bool = False) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    with open(COURSES_PATH) as f:
        courses: dict = json.load(f)
    with open(TAXONOMY_PATH) as f:
        taxonomy: dict = json.load(f)

    tag_descriptions: dict[str, str] = taxonomy["tags"]
    client = anthropic.Anthropic(api_key=api_key)

    needs_annotation = [
        name for name, data in courses.items()
        if force or not data.get("descriptors")
    ]

    if not needs_annotation:
        print("All courses already annotated. Use --force to re-annotate.")
        return

    print(f"Annotating {len(needs_annotation)} courses using Claude…")
    failed = []

    for i, name in enumerate(needs_annotation, 1):
        print(f"  [{i}/{len(needs_annotation)}] {name}", end="", flush=True)
        try:
            result = annotate_course(client, name, courses[name], tag_descriptions)

            # Merge: LLM result takes precedence over existing topics
            courses[name]["descriptors"] = result["descriptors"]
            courses[name]["topics"] = result["topics"]
            # Preserve existing manually_reviewed flag; set False if absent
            if "manually_reviewed" not in courses[name]:
                courses[name]["manually_reviewed"] = False

            print(f"  ✓  ({len(result['descriptors'])} descriptors, "
                  f"{len(result['topics'])} tags)")
        except Exception as e:
            print(f"  ✗  {e}")
            failed.append(name)

        # Write after every course so partial progress is not lost
        with open(COURSES_PATH, "w") as f:
            json.dump(courses, f, indent=2)

        if i < len(needs_annotation):
            time.sleep(1.0)

    print(f"\nDone. {len(needs_annotation) - len(failed)} annotated, "
          f"{len(failed)} failed.")
    if failed:
        print("Failed courses:", failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM-powered course annotator")
    parser.add_argument("--force", action="store_true",
                        help="Re-annotate all courses, not just unannotated ones")
    args = parser.parse_args()
    run(force=args.force)
    