# CoursePath

A constraint-based academic planning engine that generates optimized one-semester and four-year course schedules using prerequisite graph traversal, weighted scoring, beam search, and semantic interest profiling.

---

## Architecture

```
coursepath/
├── planner.py          # Core planning engine (prerequisite graph, scoring, beam search)
├── annotator.py        # LLM-powered batch annotation: descriptors + expanded topic tags
├── embedder.py         # Semantic index builder + free-text → interest profile converter
├── data_quality.py     # Per-course confidence scoring; quality-weighted schedule display
├── data/
│   ├── courses.json        # Normalized course dataset (source of truth)
│   ├── tag_taxonomy.json   # Canonical ~100-tag vocabulary with descriptions
│   ├── embeddings.npz      # Pre-built embedding index [gitignored, rebuilt locally]
│   └── rmp_cache.json      # RateMyProfessor cache [gitignored, refreshed per semester]
└── examples/
    └── sample_output.txt
```

**What lives in version control vs not:**

| File | In git | Reason |
|---|---|---|
| `courses.json` | ✓ | manually curated + LLM-annotated source of truth |
| `tag_taxonomy.json` | ✓ | stable vocabulary; changes are intentional |
| `annotator.py`, `embedder.py`, `data_quality.py` | ✓ | logic only, no keys |
| `embeddings.npz` | ✗ | derived artifact; `embedder --build` regenerates it |
| `rmp_cache.json` | ✗ | scraped data; refresh each semester |
| `sis_classes_raw.json` | ✗ | raw API dump; re-fetch with credentials |
| `.env` / any file with API keys | ✗ | always |

---

## Core Algorithms

### Prerequisite Evaluation
Recursive evaluation of nested `and`/`or` prerequisite trees in O(n) per course. Handles arbitrary nesting depth and shared sub-expressions.

### Topological Ordering
Kahn's algorithm (BFS-based) builds a valid enrollment order across the full course graph. Used to validate multi-year plan feasibility and detect prerequisite cycles.

### Single-Semester Planner
Enumerates feasible course combinations filtered by prerequisite satisfaction, unit bounds `[min_units, max_units]`, and term availability. Scored via:

```
score = w_interest  · confidence_weighted_interest_alignment
      − w_difficulty · avg_difficulty
      + w_professor  · confidence_weighted_professor_rating
      + w_breadth    · breadth_completion_delta
```

Interest and professor signals are scaled by each course's `data_quality` score before averaging, so low-confidence courses exert proportionally less influence. A min-heap of size `top_k` avoids materializing all combinations.

### Four-Year Planner (Beam Search over State Transitions)
Eight-semester planning modeled as sequential state transitions. Each `PlannerState` carries:
- `completed: frozenset[str]` — courses taken so far
- `cumulative_score: float`
- `semester_plans: list[dict]`
- `req_tracker: RequirementTracker` — breadth/major requirement fulfillment

At each semester the beam is expanded by generating `top_k_per_semester` single-semester plans per state, then pruned to `beam_width` by cumulative score.

**Complexity:** O(beam\_width × top\_k × C(|available|, k)) per semester, schedule size capped at 6.

---

## Semantic Interest Profiling

### Tag Taxonomy (`data/tag_taxonomy.json`)
~100 canonical tags spanning CS, data science, statistics, biology, chemistry, physics, engineering, math, social science, and more. Each tag has a short description used both for LLM annotation prompts and for building the embedding index. The taxonomy is the single file to edit when adding new disciplines — nothing else needs updating.

### LLM Annotation (`annotator.py`)
Uses `claude-sonnet-4-20250514` to enrich each course with:
- `"descriptors"`: 5–12 free-form keyword phrases (what skills are practiced, what problems are solved, what careers it prepares for)
- `"topics"`: expanded tag weights using the full taxonomy, using the existing hand-crafted weights as a starting point

Runs once per new batch of courses. Writes back to `courses.json` with `"manually_reviewed": false`. Flip to `true` after human verification.

```bash
ANTHROPIC_API_KEY=sk-... python -m coursepath.annotator       # annotate new courses
ANTHROPIC_API_KEY=sk-... python -m coursepath.annotator --force  # re-annotate all
```

### Semantic Embedder (`embedder.py`)
Converts a free-text interest description into a `{tag: weight}` profile via:
1. Embed user input → query vector (1 model call)
2. Cosine similarity against all tag embeddings: `sim(q, tag_i) = q · tag_i` (L2-normalised dot product, O(N·D))
3. Keep top-k tags above similarity threshold; normalise to [0, 1]

**Default model:** `all-MiniLM-L6-v2` (sentence-transformers, 384-dim, MIT license, runs fully offline on CPU in ~80ms).

**Alternative:** set `COURSEPATH_EMBED_BACKEND=anthropic` to use `voyage-3-lite` embeddings via the Anthropic API — faster for large batches, requires network and `ANTHROPIC_API_KEY`.

```bash
# Build index once (or after updating courses.json / tag_taxonomy.json)
python -m coursepath.embedder --build

# Try a query
python -m coursepath.embedder --query "I want to do computational genomics and ML pipelines for single-cell RNA-seq"
```

Three profile input modes are available at runtime:
- **Free-text** — describe interests in plain English; embedder derives the profile
- **Liked courses** — list courses enjoyed; profile derived from their centroid embedding
- **Manual sliders** — classic per-topic rating (fallback when embedder index unavailable)

---

## Data Quality & Confidence Weighting (`data_quality.py`)

Each course receives a `data_quality` score in [0, 1] computed as a weighted sum of six signals:

| Signal | Weight | Present when |
|---|---|---|
| `manually_reviewed` | 0.30 | A human has verified the annotation |
| `descriptors` | 0.20 | ≥ 3 free-form descriptor phrases exist |
| `extended_topics` | 0.15 | ≥ 4 topic tags (expanded taxonomy) |
| `professor_rating` | 0.15 | Rating exists and `num_ratings ≥ 5` |
| `grade_distribution` | 0.10 | `grade_dist` key present with ≥ 3 grade entries |
| `sis_verified` | 0.10 | Course verified against SIS API |

Weights are tunable via `SIGNAL_WEIGHTS` in `data_quality.py` without touching any other logic. New signals are added by implementing one presence function and registering it in `_SIGNAL_FNS`.

The planner's output includes a `"quality"` field per plan:
```json
{
  "courses": ["DATA C100", "MCELLBI C148"],
  "score": 0.812,
  "quality": {
    "mean": 0.45,
    "min": 0.30,
    "low_confidence": ["MCELLBI C148"],
    "label": "medium"
  }
}
```

```bash
python -m coursepath.data_quality           # write data_quality into courses.json
python -m coursepath.data_quality --show    # print per-course scores without writing
```

---

## Data Sources & API Integration

### Berkeley SIS API
Authenticated REST API (OpenAPI v3) at `gateway.api.berkeley.edu`. Apply for credentials at `developers.api.berkeley.edu` with a CalNet identity. Use a one-time bulk fetch pattern — store the API key in an environment variable, write output to `data/sis_classes_raw.json` (gitignored), then run a post-processing script to merge into `courses.json`. The fetcher script belongs in version control; the raw dump does not.

### Berkeleytime (`asuc-octo/berkeleytime`)
The open-source repo's Django models and ingestion pipeline (`apps/backend/catalog/`) reveal the exact SIS API endpoints and response parsing logic. The most valuable signal: per-section letter grade distributions (`grade_dist`), published 2–3 months after semester end. Use these to refine `difficulty` with actual grade variance rather than anecdotal ratings.

### RateMyProfessors
`pip install RateMyProfessorAPI`. Scrape once per semester, cache to `data/rmp_cache.json` (gitignored). Apply a `num_ratings` gate (≥ 5) before trusting ratings; fall back to department median otherwise.

```python
import ratemyprofessor, time, json
school = ratemyprofessor.get_school_by_name("University of California Berkeley")
cache = {}
for instructor in instructors:
    prof = ratemyprofessor.get_professor_by_school_and_name(school, instructor)
    cache[instructor] = {"rating": prof.rating, "num_ratings": prof.num_ratings} if prof else None
    time.sleep(1)
with open("data/rmp_cache.json", "w") as f:
    json.dump(cache, f, indent=2)
```

---

## Quickstart

```bash
# 1. Annotate courses with the LLM (once, or on new courses)
ANTHROPIC_API_KEY=sk-... python -m coursepath.annotator

# 2. Score data quality
python -m coursepath.data_quality

# 3. Build the semantic embedding index
python -m coursepath.embedder --build

# 4. Run the planner
python -m coursepath.planner
```

Run tests:
```bash
python -c "
import coursepath.planner as p
p.test_prereq_satisfied()
p.test_topological_order()
p.test_single_semester()
p.test_four_year_plan()
"
```

---

## Planned Extensions

- [ ] SIS API fetcher script + `courses.json` merge pipeline
- [ ] Berkeleytime grade distribution → `grade_dist` field per course
- [ ] Breadth requirement rule engine (L&S, Data Science, MCB tracks)
- [ ] ILP-based exact solver (PuLP/OR-Tools) as alternative to beam search
- [ ] FastAPI backend + React drag-and-drop schedule builder
- [ ] Per-course score breakdown in planner output (explainability layer)

---

## Disclaimer

Research and learning tool. Does not guarantee enrollment availability or institutional compliance. Not a substitute for official academic advising.

---

*Author: Shirley Wu — UC Berkeley · Molecular & Cell Biology, Data Science, Bioinformatics*
