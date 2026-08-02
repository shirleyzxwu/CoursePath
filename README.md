# CoursePath

A constraint-based academic planning engine that generates optimized one-semester and four-year course schedules using prerequisite graph traversal, weighted scoring, beam search, and semantic interest profiling.

---

## Repository structure

```
CoursePath/
├── .gitignore
├── environment.yml          # conda: python 3.11 + all deps
├── setup.sh                 # ordered pipeline reference
├── CoursePath_UI.jsx        # React four-year planner UI
│
├── coursepath/              # Python package
│   ├── __init__.py
│   ├── planner.py           # core engine: prereq graph, beam search, scoring
│   ├── annotator.py         # LLM batch enrichment (descriptors + topic tags)
│   ├── embedder.py          # semantic index builder + free-text profile builder
│   ├── data_quality.py      # per-course confidence scoring
│   ├── README.md            
│   └── data/
│       ├── courses.json         # curated course dataset [in git]
│       ├── tag_taxonomy.json    # 97-tag vocabulary [in git]
│       ├── embeddings.npz       # embedding index [gitignored — rebuild locally]
│       └── rmp_cache.json       # RMP ratings cache [gitignored — refresh per semester]
│
├── scripts/
│   ├── fetch_rmp.py         # scrape RateMyProfessors → rmp_cache.json
│   ├── fetch_sis.py         # Berkeley SIS API → sis_classes_raw.json [gitignored]
│   └── merge_sources.py     # fold rmp + sis data into courses.json
│
└── tests/
    ├── conftest.py          # sets working directory for all tests
    ├── test_planner.py      # 50 tests: prereqs, topo sort, scoring, beam search
    └── test_data_quality.py # 45 tests: signal functions, scoring, labels
```

## Pipeline

```bash
conda activate coursepath

# 1. RMP ratings
python scripts/fetch_rmp.py
# writes coursepath/data/rmp_cache.json

# 2. SIS course data (currently not available to students)
export SIS_APP_ID=your_app_id
export SIS_APP_KEY=your_app_key
python scripts/fetch_sis.py --term 2258    # 2258 = Fall 2025
# writes coursepath/data/sis_classes_raw.json

# 3. Merge external signals into courses.json
python scripts/merge_sources.py            # uses rmp + sis if both present
python scripts/merge_sources.py --rmp-only # before SIS credentials

# 4. LLM annotation
export ANTHROPIC_API_KEY=sk-ant-...
python -m coursepath.annotator
# adds descriptors + extended topic tags to courses.json

# 5. Data quality scoring
python -m coursepath.data_quality
# writes data_quality field into every course record

# 6. Build semantic embedding index
python -m coursepath.embedder --build
# writes coursepath/data/embeddings.npz

# 7. Run the planner
python -m coursepath.planner

# Commit the enriched courses.json after steps 3–5
git add coursepath/data/courses.json
git commit -m "Update courses: RMP ratings, LLM annotations, data quality"
git push
```

---

## Core algorithms

### Prerequisite evaluation
Recursive `and`/`or` tree evaluation in O(n). Handles arbitrary nesting; raises on unknown formats.

### Topological ordering
Kahn's BFS algorithm over the full dependency graph. Used to validate multi-year plan feasibility and verify no prerequisite cycles exist.

### Single-semester planner
Enumerates feasible course combinations (schedule size capped at 6) filtered by:
- prerequisite satisfaction
- unit bounds `[min_units, max_units]`
- term availability (`Fall` / `Spring`)

Scored via a weighted linear model:

```
score = w_interest  · confidence_weighted_interest_alignment
      − w_difficulty · avg_difficulty
      + w_professor  · confidence_weighted_avg_professor_rating
      + w_breadth    · breadth_completion_delta
```

Interest and professor signals are weighted by each course's `data_quality` score before averaging. A min-heap of size `top_k` avoids materialising all combinations.

### Four-year planner: beam search over state transitions
Eight-semester planning modelled as sequential state transitions. Each `PlannerState` carries:
- `completed: frozenset[str]` : courses taken so far
- `cumulative_score: float`
- `semester_plans: list[dict]`
- `req_tracker: RequirementTracker` : breadth/major requirement fulfillment

At each semester the beam expands by generating `top_k_per_semester` single-semester plans per state, then prunes to `beam_width` by cumulative score.

**Complexity:** O(beam_width × top_k × C(|available|, k)) per semester.

### Requirement tracker
Bucket-based fulfillment tracker. Courses map to named requirement buckets (e.g. `breadth:social`, `major:upper-div`). Completion ratio feeds the breadth bonus weight.

---

## Semantic interest profiling

### Tag taxonomy (`data/tag_taxonomy.json`)
97 canonical tags across CS, data science, statistics, biology, chemistry, physics, engineering, math, social science, and more. Each tag has a short description used for LLM annotation prompts and embedding.

### LLM annotation (`annotator.py`)
Uses `claude-sonnet-4-20250514` to enrich each course with:
- `"descriptors"`: 5–12 free-form keyword phrases (skills practiced, problems solved, career paths)
- `"topics"`: extended tag weights using the full taxonomy

Runs once per new batch of courses. Sets `"manually_reviewed": false`; flip to `true` after human verification.

```bash
ANTHROPIC_API_KEY=sk-ant-... python -m coursepath.annotator          # new courses only
ANTHROPIC_API_KEY=sk-ant-... python -m coursepath.annotator --force  # re-annotate all
```

### Semantic embedder (`embedder.py`)
Converts free-text interest input into a `{tag: weight}` profile:
1. Embed user text → query vector (1 model call)
2. Cosine similarity against all tag embeddings: `q · tag_i` (L2-normalised dot product, O(N·D))
3. Keep top-k tags above threshold; normalise to [0, 1]

**Default model:** `all-MiniLM-L6-v2`

Three profile input modes at runtime: free-text description, list of liked courses (centroid embedding), or manual sliders.

```bash
python -m coursepath.embedder --build
python -m coursepath.embedder --query "computational genomics and single-cell RNA-seq"
```

---

## Data quality & confidence weighting (`data_quality.py`)

Each course gets a `data_quality` score in [0, 1] computed as a weighted sum of six signals:

| Signal | Weight | Present when |
|---|---|---|
| `manually_reviewed` | 0.30 | A human has verified the annotation |
| `descriptors` | 0.20 | ≥ 3 free-form descriptor phrases |
| `extended_topics` | 0.15 | ≥ 4 topic tags |
| `professor_rating` | 0.15 | Rating exists and `num_ratings ≥ 5` |
| `grade_distribution` | 0.10 | `grade_dist` key with ≥ 3 grade entries |
| `sis_verified` | 0.10 | Verified against SIS API |

Weights are tunable via `SIGNAL_WEIGHTS` without touching any other logic. New signals are added by implementing one function and registering it in `_SIGNAL_FNS`.

Planner output includes a `"quality"` field per plan:
```json
{
  "courses": ["DATA C100", "MCELLBI C148"],
  "score": 0.812,
  "quality": { "mean": 0.45, "min": 0.30, "low_confidence": ["MCELLBI C148"], "label": "medium" }
}
```

```bash
python -m coursepath.data_quality           # write scores into courses.json
python -m coursepath.data_quality --show    # print per-course breakdown, no write
```

---

## Multi-instructor courses

Courses with multiple instructors store an `"instructors": [...]` list. `fetch_rmp.py` scrapes each instructor individually; `merge_sources.py` computes a weighted average of their RMP ratings, weighted by `num_ratings` (instructors with more reviews count proportionally more). The averaged scalar is stored as `professor_rating`.

Instructors listed as `"TBA"` are skipped during scraping and contribute zero to the `professor_rating` signal in `data_quality.py`.

---

## Data sources

### Berkeley SIS API
Authenticated REST API at `gateway.api.berkeley.edu`. Apply at `developers.api.berkeley.edu` with a CalNet identity (as checked in August 2026, the course and class APIs are not available to students). Store credentials in environment variables; never commit them. Run `fetch_sis.py` once per semester; the raw dump (`sis_classes_raw.json`) is gitignored.

### RateMyProfessors
`pip install RateMyProfessorAPI`. Scrape once per semester into `rmp_cache.json` (gitignored). Apply a `num_ratings ≥ 5` gate; fall back to department median for courses below the threshold.

---

## Tests

```bash
pip install pytest
pytest tests/ -v                                          # all tests
pytest tests/test_planner.py -v                          # planner only
pytest tests/test_data_quality.py -v                     # data quality only
pytest tests/test_planner.py::TestPrereqSatisfied -v     # one class
```

`test_planner.py` — 50 tests: prereq evaluation, topological ordering, `RequirementTracker`, interest alignment, scoring, unit bounds, `generate_semester_plans` (prereq gating, term filters, completed exclusion), `plan_four_years` (beam width, 8-semester sequence, no duplicates, score ordering), `PlannerState` immutability.

`test_data_quality.py` — 45 tests: `SIGNAL_WEIGHTS` invariant, all six signal functions (boundary values, partial credit tiers), `score_course` (range, rounding, tier ordering), `breakdown`, `quality_label` (8 parameterised boundaries), `plan_quality_summary`.

---

## Planned extensions

- [ ] Add an example run
- [ ] SIS API fetcher; auto-populate `courses.json` each semester
- [ ] Add breadth requirement rules
- [ ] ILP-based exact solver (PuLP/OR-Tools) as alternative to beam search
- [ ] FastAPI backend serving the planner

---

## Disclaimer

Research and learning tool. Does not guarantee enrollment availability or institutional compliance. Not a substitute for official academic advising.

---
