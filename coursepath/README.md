# CoursePath

A constraint-based academic planning tool that generates optimized one-semester and multi-year course schedules using prerequisite graph traversal, weighted scoring, beam search, and semantic interest profiling.

**Live demo:** [shirleyzxwu.github.io/CoursePath](https://shirleyzxwu.github.io/CoursePath)

---

## Repository structure

```
CoursePath/
├── .gitignore
├── environment.yml          # conda: python 3.11 + all deps
├── pyproject.toml           # package config + pytest markers
├── CoursePath_UI.jsx        # React planner UI (also on GitHub Pages)
│
├── coursepath/              # Python package
│   ├── __init__.py
│   ├── planner.py           # core engine: prereq graph, beam search, scoring
│   ├── annotator.py         # local LLM enrichment via Ollama (descriptors + topic tags)
│   ├── embedder.py          # semantic index builder + free-text profile builder
│   ├── data_quality.py      # per-course confidence scoring (7 signals)
│   ├── README.md
│   └── data/
│       ├── courses.json         # curated course dataset (50 courses) [in git]
│       ├── tag_taxonomy.json    # 97-tag vocabulary [in git]
│       ├── requirements.json    # major requirements: CS, EECS, Data Science, BioE, MCB [in git]
│       ├── embeddings.npz       # embedding index [gitignored — rebuild locally]
│       └── rmp_cache.json       # RMP ratings cache [gitignored — refresh per semester]
│
├── scripts/
│   ├── fetch_rmp.py         # scrape RateMyProfessors via Playwright → rmp_cache.json
│   ├── fetch_sis.py         # Berkeley SIS API → sis_classes_raw.json [gitignored]
│   └── merge_sources.py     # fold rmp + sis signals into courses.json
│
└── tests/
    ├── conftest.py          # sets working directory for all tests
    ├── test_planner.py      # ~175 tests: prereqs, scoring, beam search, RMP, requirements
    └── test_data_quality.py # ~45 tests: all 7 signal functions, scoring, labels
```

**What lives in git vs not:**

| File | In git | Reason |
|---|---|---|
| `courses.json`, `tag_taxonomy.json`, `requirements.json` | ✓ | curated source of truth |
| All `.py` files | ✓ | logic only, no secrets |
| `environment.yml`, `pyproject.toml` | ✓ | reproducible environment |
| `CoursePath_UI.jsx` | ✓ | frontend source |
| `embeddings.npz` | ✗ | derived artifact; `embedder --build` regenerates it |
| `rmp_cache.json` | ✗ | scraped data; refresh each semester |
| `sis_classes_raw.json` | ✗ | raw API dump; re-fetch with credentials |
| `.env` / any key file | ✗ | always |

---

## Pipeline (run in order)

```bash
conda activate coursepath

# 1. RMP ratings via Playwright (headless Chrome, no credentials needed)
#    On macOS with existing Chrome:
#    Edit fetch_rmp.py: executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
python scripts/fetch_rmp.py
# → writes coursepath/data/rmp_cache.json (gitignored)
# → populates: professor_rating, rmp_difficulty, would_take_again per instructor

# 2. SIS course data: requires SIS API credentials; data currently unavailable to students
#    (apply at developers.api.berkeley.edu)
export SIS_APP_ID=your_app_id
export SIS_APP_KEY=your_app_key
python scripts/fetch_sis.py --term 2258    # 2258 = Fall 2025
# → writes coursepath/data/sis_classes_raw.json (gitignored)

# 3. Merge external signals into courses.json
python scripts/merge_sources.py            # uses rmp + sis if both present
python scripts/merge_sources.py --rmp-only # before SIS credentials

# 4. LLM annotation via Ollama
#    Setup: brew install ollama && ollama pull llama3 && ollama serve
python -m coursepath.annotator --dry-run   # preview output first
python -m coursepath.annotator             # write to courses.json
python -m coursepath.annotator --model mistral  # use a different model

# 5. Data quality scoring
python -m coursepath.data_quality
# → writes data_quality score [0–1] into every course record

# 6. Build semantic embedding index
python -m coursepath.embedder --build
# → writes coursepath/data/embeddings.npz (gitignored, ~80MB on first run)

# 7. Run the planner
python -m coursepath.planner

# Commit enriched courses.json after steps 3–5
git add coursepath/data/courses.json
git commit -m "Update courses: RMP ratings, LLM annotations, data quality"
git push
```

---

## Core algorithms

### Prerequisite evaluation
Recursive `and`/`or` tree evaluation in O(n). Handles arbitrary nesting depth; raises `ValueError` on unknown formats.

### Topological ordering
Kahn's BFS algorithm over the full course dependency graph. Used to validate multi-year plan feasibility and detect prerequisite cycles.

### Single-semester planner
Enumerates feasible course combinations (capped at 6 courses per schedule) filtered by prerequisite satisfaction, unit bounds `[min_units, max_units]`, and term availability. Scored via:

```
score = w_interest         · confidence_weighted_interest_alignment
      − w_difficulty       · blended_difficulty
      + w_professor        · confidence_weighted_avg_professor_rating
      + w_would_take_again · confidence_weighted_avg_would_take_again  (0–1)
      + w_major_progress   · major_requirement_completion_delta
```

`blended_difficulty` = `rmp_difficulty × 0.6 + hand_authored_difficulty × 0.4` when RMP data exists, otherwise the hand-authored value. All signals except `major_progress` are confidence-weighted by `data_quality`. A min-heap of size `top_k` avoids storing all combinations.

### Multi-semester planner — beam search over state transitions
Planning over 2–8 semesters modelled as sequential state transitions. Each `PlannerState` carries:
- `completed: frozenset[str]` : courses taken so far
- `cumulative_score: float`
- `semester_plans: list[dict]`
- `req_tracker: RequirementTracker` : major requirement fulfillment

At each semester the beam expands by generating `top_k_per_semester` single-semester plans per state, then prunes to `beam_width` by cumulative score.

**Complexity:** O(beam_width × top_k × C(|available|, k)) per semester.

### Requirement tracker
Bucket-based fulfillment tracker. Courses map to named requirement buckets loaded from `requirements.json`. Completion ratio feeds the `major_progress` bonus in scoring. `build_tracker(major, track)` constructs a tracker for any supported major and track. Multiple majors can be merged into a single tracker for double-major planning.

---

## Major requirement tracking (`data/requirements.json`)

Five majors with all tracks encoded:

| Major | Tracks |
|---|---|
| CS B.A. | default |
| EECS B.S. | default |
| Data Science B.A. | default + 5 domain emphases (related to bio)|
| Bioengineering B.S. | bioinstrumentation, computational biology, synthetic/systems biology, cell/tissue engineering |
| MCB B.A. | BBS (2), CDP (2), GGED (2), IMM (3), MTX (2) — 11 tracks total |

```bash
python -m coursepath.planner
# → prompts for major(s) and track; supports multiple majors (e.g. DATA_BA, MCB)
```

All course references in `requirements.json` are validated against `courses.json` on every test run.

---

## Semantic interest profiling

### Tag taxonomy (`data/tag_taxonomy.json`)
97 canonical tags across CS, data science, statistics, biology, chemistry, physics, engineering, math, social science, and more. Each tag has a plain-English description used for LLM annotation prompts and embedding. Edit this file to add disciplines.

### LLM annotation (`annotator.py`)
Uses a local Ollama model (llama3, mistral, or phi3) to enrich each course with:
- `"descriptors"`: 5–8 keyword phrases a student would search for
- `"topics"`: expanded tag weights using the 97-tag taxonomy

```bash
# One-time setup
brew install ollama && ollama pull llama3
ollama serve   # keep running in a separate terminal tab

python -m coursepath.annotator --dry-run        # test on one course, no file changes
python -m coursepath.annotator                  # annotate unannotated courses
python -m coursepath.annotator --force          # re-annotate all
python -m coursepath.annotator --model mistral  # use a different model
```

### Semantic embedder (`embedder.py`)
Converts free-text interest input into a `{tag: weight}` profile:
1. Embed user text → query vector
2. Cosine similarity against all tag embeddings: `q · tag_i` (L2-normalised dot product, O(N·D))
3. Keep top-k tags above similarity threshold; normalise to [0, 1]

Three profile input modes at runtime: free-text description, liked courses (centroid embedding), or manual topic sliders.

```bash
python -m coursepath.embedder --build
python -m coursepath.embedder --query "computational genomics and single-cell RNA-seq"
```

---

## Data quality & confidence weighting (`data_quality.py`)

Each course gets a `data_quality` score in [0, 1] as a weighted sum of seven signals:

| Signal | Weight | Present when |
|---|---|---|
| `manually_reviewed` | 0.25 | A human has verified the annotation |
| `descriptors` | 0.20 | ≥ 3 free-form descriptor phrases |
| `extended_topics` | 0.15 | ≥ 4 topic tags |
| `professor_rating` | 0.15 | Rating exists and `num_ratings ≥ 5` |
| `would_take_again` | 0.10 | RMP would-take-again % present (≥ 80% gives full credit) |
| `grade_distribution` | 0.10 | `grade_dist` key with ≥ 3 grade entries |
| `sis_verified` | 0.05 | Verified against SIS API |

Weights are tunable via `SIGNAL_WEIGHTS`. New signals require one function + one dict entry in `_SIGNAL_FNS` — no other changes.

```bash
python -m coursepath.data_quality          
python -m coursepath.data_quality --show
```

---

## RMP data collection (`scripts/fetch_rmp.py`)

Uses **Playwright** (headless Chrome) to navigate RMP search pages and read professor cards directly from the rendered DOM, bypassing Cloudflare's bot detection that blocks plain HTTP requests. Includes fuzzy first-name verification to prevent wrong-person matches on common last names.

Fields scraped per instructor: `rating`, `difficulty`, `num_ratings`, `would_take_again`, `department`, `rmp_id`.

For courses with multiple instructors, `merge_sources.py` computes weighted averages (by `num_ratings`) and writes three fields to `courses.json`: `professor_rating`, `rmp_difficulty`, `would_take_again`.

```bash
pip install playwright
python scripts/fetch_rmp.py           # fetch all instructors
python scripts/fetch_rmp.py --force
```

---

## Web interface

`CoursePath_UI.jsx` is a self-contained React component with no backend. All planning logic runs in the browser.

**Three-tab interface:**
- **Interest Profile** : topic sliders (0–1) for all tags; colour-coded by domain; completed courses input
- **Scoring Weights** : adjustable weights for all five scoring signals; unit bounds; beam width; semester count (1–4 years); major and track selector
- **Plan** : beam search results across plan variants; semester grid; per-course detail with topic difficulty, would-take-again, data quality; four stat cards including major requirement progress %

---

## Tests

```bash
conda activate coursepath
pip install pytest pytest-mock

pytest tests/ -v -m "not integration"
pytest tests/ -v -m integration -s
pytest tests/test_planner.py::TestBuildTracker -v
pytest tests/test_planner.py::TestNameMatching -v
```

**`test_planner.py`** (~130 tests, 12 classes): prereq evaluation, topological ordering, `RequirementTracker`, interest alignment, scoring (difficulty blending, would-take-again bonus, major progress delta), unit bounds, semester plans, four-year beam search, `PlannerState` immutability, multi-instructor RMP averaging, `build_tracker` for all majors/tracks, name-match verification, mocked Playwright scraping.

**`test_data_quality.py`** (~45 tests, 9 classes): `SIGNAL_WEIGHTS` invariant, all 7 signal functions with boundary values and partial credit tiers, `score_course`, `breakdown`, `quality_label`, `plan_quality_summary`.

---

## Data sources

### Berkeley SIS API
Authenticated REST at `gateway.api.berkeley.edu`. Apply at `developers.api.berkeley.edu` with CalNet. Run `fetch_sis.py` once per semester. (Currently unavailable to students)

### RateMyProfessors
Scraped via Playwright. Cloudflare blocks plain HTTP requests; browser automation is required. Cache in `rmp_cache.json` and refresh once per semester.

---

## Planned extensions

- [ ] L&S/CDSS breadth requirement tracking
- [ ] ILP-based exact solver (PuLP/OR-Tools) as alternative to beam search
- [ ] FastAPI backend exposing the planner as a REST API
- [ ] Per-course score breakdown in plan output

---

## Disclaimer

Research and learning tool. Does not guarantee enrollment availability or institutional compliance. Not a substitute for official academic advising.

---
