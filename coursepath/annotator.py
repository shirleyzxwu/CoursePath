"""
LLM-powered course annotation pipeline using local Ollama.

Reads courses.json and tag_taxonomy.json, calls a local Ollama model once per
unannotated course, and writes the enriched records back to courses.json.

Populates:
  "descriptors": list[str]   — free-form keyword phrases from course description
  "topics": dict[str,float]  — extended tag weights using the full taxonomy
  "manually_reviewed": bool  — always False from this script; flip manually

Requirements:
  1. Install ollama:          brew install ollama
  2. Pull a model:            ollama pull llama3        (best quality, ~4GB)
  3. Start the server:        ollama serve
  4. Run this script:         python -m coursepath.annotator

Usage:
  python -m coursepath.annotator                  # annotate only unannotated courses
  python -m coursepath.annotator --force          # re-annotate all courses
  python -m coursepath.annotator --model mistral  # use a different model
  python -m coursepath.annotator --dry-run        # preview output, don't write (the result would be descriptors before annotation)
"""

import json
import os
import sys
import time
import argparse
import re

import requests as _req

DATA_DIR      = os.path.join(os.path.dirname(__file__), "data")
COURSES_PATH  = os.path.join(DATA_DIR, "courses.json")
TAXONOMY_PATH = os.path.join(DATA_DIR, "tag_taxonomy.json")

OLLAMA_URL    = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"


# ─────────────────────────────────────────────
# Connectivity check
# ─────────────────────────────────────────────

def check_ollama(model: str) -> None:
    """Verify Ollama is running and the requested model is available."""
    try:
        r = _req.get("http://localhost:11434/api/tags", timeout=3)
        r.raise_for_status()
    except Exception:
        print(
            "Error: Cannot reach Ollama at http://localhost:11434\n"
            "Make sure it's running:  ollama serve\n"
            "Then retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    available = [m["name"].split(":")[0] for m in r.json().get("models", [])]
    model_base = model.split(":")[0]
    if model_base not in available:
        print(
            f"Error: Model '{model}' not found in Ollama.\n"
            f"Available: {available or '(none)'}\n"
            f"Pull it with:  ollama pull {model}",
            file=sys.stderr,
        )
        sys.exit(1)


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
Existing topic weights: {existing_topics}

Your task is to produce two things:

1. "descriptors": A list of 5-12 short free-form keyword phrases (2-5 words each)
   that a student might use when searching for this course. Focus on what skills
   are practiced, what problems are solved, and what career paths it prepares for.
   Examples: "sequence alignment algorithms", "Jupyter notebook workflows",
   "molecular cloning techniques", "causal inference with observational data".

2. "topics": A dict mapping tag names to weights (0.0-1.0) reflecting how much
   instructional emphasis each tag receives. Weights do NOT need to sum to 1.
   Only include tags with weight >= 0.05. Use the existing topics as a starting
   point and expand using the full taxonomy below.

Available tags and their meanings:
{tag_block}

Respond ONLY with a valid JSON object. No explanation, no markdown, no preamble.
Format exactly like this:
{{
  "descriptors": ["phrase one", "phrase two"],
  "topics": {{
    "python": 0.5,
    "statistics": 0.4
  }}
}}"""


# ─────────────────────────────────────────────
# Parse and validate LLM response
# ─────────────────────────────────────────────

def parse_response(raw: str, course_name: str) -> dict:
    """
    Parse the model's text output into a validated dict.
    Handles common failure modes: markdown fences, trailing text,
    JSON embedded inside prose.
    """
    text = raw.strip()

    # Strip markdown fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            if part.startswith("json"):
                text = part[4:].strip()
                break
            elif "{" in part:
                text = part.strip()
                break

    # Extract the first JSON object if surrounded by prose
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    result = json.loads(text)

    if "descriptors" not in result or "topics" not in result:
        raise ValueError(f"Missing keys in response: {list(result.keys())}")
    if not isinstance(result["descriptors"], list):
        raise ValueError("descriptors must be a list")
    if not isinstance(result["topics"], dict):
        raise ValueError("topics must be a dict")
    if not result["descriptors"]:
        raise ValueError("descriptors list is empty")
    if not result["topics"]:
        raise ValueError("topics dict is empty")

    # Clamp topic weights to [0, 1]
    result["topics"] = {
        k: max(0.0, min(1.0, float(v)))
        for k, v in result["topics"].items()
        if float(v) >= 0.05
    }

    return result


# ─────────────────────────────────────────────
# Single course annotation via Ollama
# ─────────────────────────────────────────────

def annotate_course(
    course_name: str,
    course_data: dict,
    tag_descriptions: dict[str, str],
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Call the local Ollama model to annotate one course.
    Returns {"descriptors": [...], "topics": {...}} or raises on failure.
    """
    prompt = build_prompt(course_name, course_data, tag_descriptions)

    resp = _req.post(
        OLLAMA_URL,
        json={
            "model":  model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 1024,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()

    raw = resp.json().get("response", "").strip()
    if not raw:
        raise ValueError("Empty response from Ollama")

    return parse_response(raw, course_name)


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def run(force: bool = False, model: str = DEFAULT_MODEL, dry_run: bool = False) -> None:
    check_ollama(model)

    with open(COURSES_PATH) as f:
        courses: dict = json.load(f)
    with open(TAXONOMY_PATH) as f:
        taxonomy: dict = json.load(f)

    tag_descriptions: dict[str, str] = taxonomy["tags"]

    needs_annotation = [
        name for name, data in courses.items()
        if force or not data.get("descriptors")
    ]

    if not needs_annotation:
        print("All courses already annotated. Use --force to re-annotate.")
        return

    mode_label = "[DRY RUN] " if dry_run else ""
    print(f"{mode_label}Annotating {len(needs_annotation)} courses with {model}…")
    if dry_run:
        print("(dry-run: output will be printed but courses.json will not be modified)\n")

    failed = []

    for i, name in enumerate(needs_annotation, 1):
        print(f"  [{i:>2}/{len(needs_annotation)}] {name}", end="", flush=True)
        try:
            result = annotate_course(name, courses[name], tag_descriptions, model)

            if dry_run:
                print(f"\n    descriptors ({len(result['descriptors'])}):")
                for d in result["descriptors"]:
                    print(f"      - {d}")
                print(f"    topics ({len(result['topics'])}):")
                for tag, w in sorted(result["topics"].items(), key=lambda x: -x[1]):
                    print(f"      {tag:<30} {w:.2f}")
                print()
            else:
                courses[name]["descriptors"] = result["descriptors"]
                courses[name]["topics"]      = result["topics"]
                if "manually_reviewed" not in courses[name]:
                    courses[name]["manually_reviewed"] = False

                print(f"  ✓  ({len(result['descriptors'])} descriptors, "
                      f"{len(result['topics'])} tags)")

                # Write after every course
                with open(COURSES_PATH, "w") as f:
                    json.dump(courses, f, indent=2)

        except Exception as e:
            print(f"  ✗  {e}")
            failed.append(name)

        # Brief pause between requests
        if i < len(needs_annotation):
            time.sleep(0.3)

    if dry_run:
        print(f"Dry run complete — {len(needs_annotation) - len(failed)} would be annotated.")
    else:
        print(f"\nDone. {len(needs_annotation) - len(failed)} annotated, "
              f"{len(failed)} failed.")
    if failed:
        print("Failed:", failed)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Annotate courses.json using a local Ollama LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Setup:
  brew install ollama
  ollama pull llama3        # recommended (~4GB, best quality)
  python -m coursepath.annotator
  python -m coursepath.annotator --force --model mistral
  python -m coursepath.annotator --dry-run
        """
    )
    parser.add_argument("--force",   action="store_true",
                        help="Re-annotate all courses, not just unannotated ones")
    parser.add_argument("--model",   default=DEFAULT_MODEL,
                        help=f"Ollama model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview output without modifying courses.json")
    args = parser.parse_args()
    run(force=args.force, model=args.model, dry_run=args.dry_run)
