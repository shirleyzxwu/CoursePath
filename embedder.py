"""
embedder.py — Semantic interest profile builder.

Two responsibilities:

  1. build_index()
     Embeds every tag description and every course descriptor using
     sentence-transformers. Saves a local index to data/embeddings.npz
     so subsequent runs are instant (no re-embedding needed unless
     courses.json or tag_taxonomy.json change).

  2. profile_from_text(user_input) -> dict[str, float]
     Given a free-text description of interests (e.g. "I want to do
     computational genomics and build ML pipelines for single-cell data"),
     returns a normalized interest profile dict {tag: weight} ready to
     pass directly into the planner's scoring model.

Model choice:
  all-MiniLM-L6-v2   — fast (80ms/sentence on CPU), 384-dim, MIT license,
                        available on HuggingFace without an API key.
                        Best default for offline/local use.

  If you have an Anthropic API key and prefer not to install
  sentence-transformers, set COURSEPATH_EMBED_BACKEND=anthropic
  and the module will use voyage-3-lite embeddings instead (faster
  for large batches, requires network).

Dependencies:
  pip install sentence-transformers numpy          # default backend
  pip install anthropic numpy                      # Anthropic backend

Usage:
  python -m coursepath.embedder --build            # build / refresh index
  python -m coursepath.embedder --query "your text here"
"""

import json
import os
import sys
import argparse
import numpy as np

DATA_DIR      = os.path.join(os.path.dirname(__file__), "data")
COURSES_PATH  = os.path.join(DATA_DIR, "courses.json")
TAXONOMY_PATH = os.path.join(DATA_DIR, "tag_taxonomy.json")
INDEX_PATH    = os.path.join(DATA_DIR, "embeddings.npz")

BACKEND = os.environ.get("COURSEPATH_EMBED_BACKEND", "sentence_transformers")
ST_MODEL = "all-MiniLM-L6-v2"


# ─────────────────────────────────────────────
# Backend: sentence-transformers (default)
# ─────────────────────────────────────────────

def _st_embed(texts: list[str]) -> np.ndarray:
    """
    Embed a list of strings using all-MiniLM-L6-v2.
    Returns shape (N, 384), dtype float32, L2-normalised.
    """
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(ST_MODEL)
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.array(vecs, dtype=np.float32)


# ─────────────────────────────────────────────
# Backend: Anthropic voyage-3-lite
# ─────────────────────────────────────────────

def _anthropic_embed(texts: list[str]) -> np.ndarray:
    """
    Embed using Anthropic's voyage-3-lite model via the anthropic client.
    Requires ANTHROPIC_API_KEY in the environment.
    """
    import anthropic
    client = anthropic.Anthropic()
    # voyage-3-lite supports batches up to 128 inputs
    all_vecs = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(
            model="voyage-3-lite",
            input=batch,
        )
        all_vecs.extend([e.embedding for e in response.data])
    mat = np.array(all_vecs, dtype=np.float32)
    # L2-normalise
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return mat / norms


def embed(texts: list[str]) -> np.ndarray:
    if BACKEND == "anthropic":
        return _anthropic_embed(texts)
    return _st_embed(texts)


# ─────────────────────────────────────────────
# Cosine similarity
# ─────────────────────────────────────────────

def cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """
    query_vec: (D,)  — already L2-normalised
    matrix:    (N, D) — already L2-normalised
    Returns (N,) similarity scores in [-1, 1].

    Because both sides are unit-norm, this reduces to a dot product:
      sim(q, m_i) = q · m_i
    which is O(N·D) and computable in a single matmul.
    """
    return matrix @ query_vec   # shape (N,)


# ─────────────────────────────────────────────
# Index build
# ─────────────────────────────────────────────

def build_index(force: bool = False) -> None:
    """
    Embed all tag descriptions + course descriptors and save to INDEX_PATH.
    Skips if the index is already up-to-date (mtime check), unless force=True.
    """
    if not force and os.path.exists(INDEX_PATH):
        index_mtime = os.path.getmtime(INDEX_PATH)
        sources_mtime = max(
            os.path.getmtime(COURSES_PATH),
            os.path.getmtime(TAXONOMY_PATH),
        )
        if index_mtime >= sources_mtime:
            print("Index is up-to-date. Use --build --force to rebuild.")
            return

    with open(TAXONOMY_PATH) as f:
        taxonomy = json.load(f)
    with open(COURSES_PATH) as f:
        courses = json.load(f)

    tag_names = list(taxonomy["tags"].keys())
    tag_descs = [taxonomy["tags"][t] for t in tag_names]

    # One text per course: join descriptors into a single sentence.
    # Courses without descriptors fall back to the tag names in their topics dict.
    course_names = list(courses.keys())
    course_texts = []
    for name in course_names:
        data = courses[name]
        descs = data.get("descriptors", [])
        if descs:
            course_texts.append("; ".join(descs))
        else:
            course_texts.append(", ".join(data.get("topics", {}).keys()) or name)

    print(f"Embedding {len(tag_names)} tags and {len(course_names)} courses "
          f"using backend '{BACKEND}'…")

    all_texts = tag_descs + course_texts
    all_vecs  = embed(all_texts)

    tag_vecs    = all_vecs[:len(tag_names)]
    course_vecs = all_vecs[len(tag_names):]

    np.savez(
        INDEX_PATH,
        tag_names=np.array(tag_names),
        tag_vecs=tag_vecs,
        course_names=np.array(course_names),
        course_vecs=course_vecs,
    )
    print(f"Saved index to {INDEX_PATH}")


# ─────────────────────────────────────────────
# Load index (cached in module scope)
# ─────────────────────────────────────────────

_INDEX_CACHE: dict | None = None

def load_index() -> dict:
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(
            f"Embedding index not found at {INDEX_PATH}. "
            "Run: python -m coursepath.embedder --build"
        )
    data = np.load(INDEX_PATH, allow_pickle=False)
    _INDEX_CACHE = {
        "tag_names":    list(data["tag_names"]),
        "tag_vecs":     data["tag_vecs"],      # (N_tags, D)
        "course_names": list(data["course_names"]),
        "course_vecs":  data["course_vecs"],   # (N_courses, D)
    }
    return _INDEX_CACHE


# ─────────────────────────────────────────────
# Profile derivation
# ─────────────────────────────────────────────

def profile_from_text(
    user_input: str,
    top_k_tags: int = 20,
    min_similarity: float = 0.15,
) -> dict[str, float]:
    """
    Convert free-text interest description into a {tag: weight} profile.

    Algorithm:
      1. Embed user_input (1 API/model call).
      2. Compute cosine similarity against every tag embedding.
      3. Keep the top_k_tags tags above min_similarity threshold.
      4. Normalise weights to [0, 1] by dividing by the max similarity.

    The returned dict is ready to pass to generate_semester_plans() or
    plan_four_years() as interest_profile.

    Parameters
    ----------
    user_input      : free-text string from the user
    top_k_tags      : maximum number of tags to include in the profile
    min_similarity  : tags below this cosine similarity are dropped
    """
    index = load_index()

    query_vec = embed([user_input])[0]   # shape (D,)

    sims = cosine_similarity(query_vec, index["tag_vecs"])   # shape (N_tags,)

    # Rank tags by similarity
    ranked_indices = np.argsort(sims)[::-1]

    profile: dict[str, float] = {}
    for idx in ranked_indices[:top_k_tags]:
        sim = float(sims[idx])
        if sim < min_similarity:
            break
        tag = index["tag_names"][idx]
        profile[tag] = sim

    if not profile:
        return {}

    # Normalise to [0, 1]
    max_sim = max(profile.values())
    return {tag: round(w / max_sim, 4) for tag, w in profile.items()}


def profile_from_course_names(
    liked_courses: list[str],
    top_k_tags: int = 20,
    min_similarity: float = 0.10,
) -> dict[str, float]:
    """
    Alternative entry point: derive a profile from a list of courses the
    student already enjoyed.  Averages their embeddings then runs the same
    tag-similarity lookup.
    """
    index = load_index()

    name_to_idx = {n: i for i, n in enumerate(index["course_names"])}
    valid = [n for n in liked_courses if n in name_to_idx]
    if not valid:
        return {}

    course_vecs = np.stack([index["course_vecs"][name_to_idx[n]] for n in valid])
    centroid = course_vecs.mean(axis=0)
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm

    sims = cosine_similarity(centroid, index["tag_vecs"])
    ranked_indices = np.argsort(sims)[::-1]

    profile: dict[str, float] = {}
    for idx in ranked_indices[:top_k_tags]:
        sim = float(sims[idx])
        if sim < min_similarity:
            break
        profile[index["tag_names"][idx]] = sim

    if not profile:
        return {}

    max_sim = max(profile.values())
    return {tag: round(w / max_sim, 4) for tag, w in profile.items()}


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CoursePath semantic embedder")
    parser.add_argument("--build", action="store_true",
                        help="Build or refresh the embedding index")
    parser.add_argument("--force", action="store_true",
                        help="Force rebuild even if index is current")
    parser.add_argument("--query", type=str, default=None,
                        help="Free-text interest description to convert to a profile")
    parser.add_argument("--top-k", type=int, default=20,
                        help="Max tags to include in the profile (default: 20)")
    args = parser.parse_args()

    if args.build:
        build_index(force=args.force)

    if args.query:
        if not os.path.exists(INDEX_PATH):
            print("Index not found. Run with --build first.", file=sys.stderr)
            sys.exit(1)
        profile = profile_from_text(args.query, top_k_tags=args.top_k)
        print(f"\nInterest profile for: \"{args.query}\"\n")
        for tag, weight in sorted(profile.items(), key=lambda x: -x[1]):
            bar = "█" * int(weight * 20)
            print(f"  {tag:<35} {weight:.3f}  {bar}")

    if not args.build and not args.query:
        parser.print_help()
