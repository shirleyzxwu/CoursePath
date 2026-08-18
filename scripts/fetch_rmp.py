"""
RateMyProfessors cache builder.

Queries RMP's GraphQL API directly.
The GraphQL endpoint is public and used by the RMP website itself.

Reads instructors from courses.json, fetches ratings for each,
writes coursepath/data/rmp_cache.json (gitignored).

Run once per semester, or when the instructor list changes.

Usage:
    conda activate coursepath
    python scripts/fetch_rmp.py [--force]

    --force   re-fetch instructors already in rmp_cache.json
"""

import json
import os
import time
import argparse
# requests is kept for potential future use; Playwright currently handles RMP fetching
try:
    import requests
except ImportError:
    pass

# ── Playwright import (top-level so tests can mock scripts.fetch_rmp.sync_playwright) ──
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None   # type: ignore

# ── Paths ──────────────────────────────────────────────────────────────────

ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSES_PATH = os.path.join(ROOT, "coursepath", "data", "courses.json")
CACHE_PATH   = os.path.join(ROOT, "coursepath", "data", "rmp_cache.json")

# ── RMP GraphQL config ──────────────────────────────────────────────────────
# UC Berkeley's RMP school node ID (base64 of "School-1072")
# Confirmed at https://www.ratemyprofessors.com/school/1072

# RMP blocks plain HTTP requests with 403 host_not_allowed (Cloudflare).
# Use Playwright to run a real headless browser that intercepts the
# GraphQL response RMP's own JS makes, which bypasses the bot detection.
#
# Install: pip install playwright && playwright install chromium
#
# BERKELEY_SCHOOL_ID is base64("School-1072"), used in the RMP GraphQL query.
BERKELEY_SCHOOL_ID = "U2Nob29sLTEwNzI="   # base64("School-1072")
RMP_SEARCH_URL = "https://www.ratemyprofessors.com/search/professors/1072?q={name}"



def _parse_card_text(text: str, href: str) -> dict | None:
    """
    Parse a professor card's inner text from RMP search results.

    RMP card text is newline-separated and looks like:
      QUALITY
      <rating float>
      <First Last>
      <Department>
      At <School Name>
      <N> ratings
      QUALITY  (or DIFFICULTY)
      <difficulty float>
      Would Take Again: <N>%   (optional)
    """
    import re as _re

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Floats that look like ratings/difficulty (1.0–5.0)
    floats = [float(x) for x in _re.findall(r"\b[1-5]\.\d\b", text)]
    rating = floats[0] if floats else None
    diff   = floats[1] if len(floats) > 1 else None

    # Num ratings
    nums = _re.findall(r"(\d+)\s*rating", text, _re.IGNORECASE)
    num_ratings = int(nums[0]) if nums else 0

    # Would take again %
    wta_m = _re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    wta = float(wta_m.group(1)) if wta_m else None

    # Name: first line that isn't a label, float, school line, count, or %
    name_line = ""
    for line in lines:
        if _re.match(r"^[1-5]\.\d$", line):              continue
        if line.upper() in ("QUALITY", "DIFFICULTY", "N/A"): continue
        if line.startswith("At "):                          continue
        if _re.search(r"\d+\s*rating", line, _re.I):      continue
        if _re.search(r"\d+\s*%", line):                   continue
        if len(line) < 3:                                   continue
        name_line = line
        break

    if not name_line:
        return None

    parts = name_line.split()
    first = parts[0]  if parts else ""
    lname = parts[-1] if len(parts) > 1 else name_line

    # Department: first qualifying line after the name line
    dept = ""
    found_name = False
    for line in lines:
        if line == name_line:
            found_name = True
            continue
        if not found_name:
            continue
        if _re.match(r"^[1-5]\.\d$", line):              continue
        if line.upper() in ("QUALITY", "DIFFICULTY", "N/A"): continue
        if line.startswith("At "):                          continue
        if _re.search(r"\d+\s*rating", line, _re.I):      continue
        if _re.search(r"\d+\s*%", line):                   continue
        dept = line
        break

    rmp_id = href.split("/professor/")[-1].strip("/") if "/professor/" in href else None

    return {
        "rating":           rating,
        "difficulty":       diff,
        "num_ratings":      num_ratings,
        "would_take_again": wta,
        "department":       dept,
        "first_name":       first,
        "last_name":        lname,
        "rmp_id":           rmp_id,
    }


def _name_matches(full_name: str, result: dict) -> bool:
    """
    Check whether a parsed RMP card result matches the instructor searched for.
    Uses the first name as the verification signal.
      - Case-insensitive
      - The RMP first name just needs to START with the first name's first
        letter to handle nicknames (e.g. "Ani" matching "Anil")
      - Last names must match exactly (modulo case)
    """
    parts = full_name.strip().split()
    if not parts:
        return False

    our_first = parts[0].lower()
    our_last  = parts[-1].lower()

    rmp_first = (result.get("first_name") or "").lower()
    rmp_last  = (result.get("last_name")  or "").lower()

    last_ok  = our_last == rmp_last
    if not rmp_first:
        return False
    first_ok = (
        our_first == rmp_first
        or our_first.startswith(rmp_first[0]) and rmp_first.startswith(our_first[0])
        or rmp_first.startswith(our_first)
        or our_first.startswith(rmp_first)
    )
    return last_ok and first_ok


def search_professor(prof_last_name: str, full_name: str = "") -> dict | None:
    """
    Fetch RMP data for a professor by last name at Berkeley.

    Uses Playwright to navigate to the RMP search page and reads professor
    cards directly from the rendered DOM.

    If full_name is provided, uses it to verify the first name of each
    result before accepting.
    """
    if sync_playwright is None:
        print("    ⚠ Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )
            page = browser.new_page()

            # Block images/fonts to speed up loading
            page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}",
                       lambda r: r.abort())

            page.goto(
                RMP_SEARCH_URL.format(name=prof_last_name),
                wait_until="domcontentloaded",
                timeout=20000,
            )

            # Dismiss cookie banner if present
            try:
                for label in ["Accept", "OK", "Got it", "I Accept"]:
                    btn = page.locator(f"button:has-text('{label}')")
                    if btn.count() > 0:
                        btn.first.click(timeout=1500)
                        break
            except Exception:
                pass

            # Wait for professor cards
            try:
                page.wait_for_selector("a[href*='/professor/']", timeout=8000)
            except Exception:
                browser.close()
                return None

            def _collect_results():
                cards = page.query_selector_all("a[href*='/professor/']")
                out = []
                for card in cards:
                    try:
                        text = card.inner_text()
                        href = card.get_attribute("href") or ""
                        parsed = _parse_card_text(text, href)
                        if parsed:
                            out.append(parsed)
                    except Exception:
                        continue
                return out

            results = _collect_results()

            # RMP sometimes lists duplicate/legacy "ghost" professor entries
            # with 0 ratings alongside the real one. 
            # _parse_card_text only matches rating floats in the
            # 1.0-5.9 range, so these ghost cards parse with rating=None.
            # Filtered those out before ranking so a
            # lower-rated-but-real card always beats a null-rating duplicate.
            rated = [r for r in results if r.get("rating") is not None]

            # If nothing with an actual rating showed up on the initial
            # render, some search result pages hide additional cards behind
            # a "Show More" button. Click it once and re-collect before
            # giving up.
            if not rated:
                try:
                    show_more = page.locator("button:has-text('Show More')")
                    if show_more.count() > 0:
                        show_more.first.click(timeout=2000)
                        page.wait_for_timeout(1000)
                        results = _collect_results()
                        rated = [r for r in results if r.get("rating") is not None]
                except Exception:
                    pass

            browser.close()

            if not rated:
                return None

            # If have a full name, filter to only matching results first
            if full_name:
                matching = [r for r in rated if _name_matches(full_name, r)]
                if matching:
                    # Among verified matches, pick the one with most ratings
                    return max(matching, key=lambda r: r.get("num_ratings") or 0)
                # Return None when no verified match found
                return None

            # If no full name provided, fall back to most-rated
            return max(rated, key=lambda r: r.get("num_ratings") or 0)

    except Exception as e:
        print(f"    ✗ Playwright error: {e}")
        return None

def last_name(full_name: str) -> str:
    """Extract last name for RMP search. Handles 'First Last' and 'First M. Last'."""
    parts = full_name.strip().split()
    return parts[-1] if parts else full_name


def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def collect_instructors(courses: dict) -> list[str]:
    """Return sorted list of unique non-TBA instructor names."""
    instructors = set()
    for data in courses.values():
        for name in data.get("instructors", []):
            if name and name != "TBA":
                instructors.add(name)
    return sorted(instructors)


# ── Main ───────────────────────────────────────────────────────────────────

def run(force: bool = False) -> None:
    with open(COURSES_PATH) as f:
        courses = json.load(f)

    instructors = collect_instructors(courses)
    if not instructors:
        print("No instructors found in courses.json.")
        return

    cache = load_cache()
    to_fetch = instructors if force else [i for i in instructors if i not in cache]

    if not to_fetch:
        print(f"All {len(instructors)} instructors already cached. Use --force to re-fetch.")
        return

    print(f"Fetching {len(to_fetch)} instructors from RMP GraphQL API "
          f"({len(instructors) - len(to_fetch)} already cached)...\n")

    for i, name in enumerate(to_fetch, 1):
        print(f"  [{i:>3}/{len(to_fetch)}] {name}", end="  ", flush=True)
        result = search_professor(last_name(name), full_name=name)

        if result and result.get("rating") is not None:
            n = result["num_ratings"]
            r = result["rating"]
            low = " ⚠ low confidence (<5 ratings)" if n < 5 else ""
            found_name = f"{result.get('first_name','')} {result.get('last_name','')}".strip()
            print(f"★ {r}  ({n} ratings)  [{found_name}]{low}")
        else:
            print("not found")

        cache[name] = result
        save_cache(cache)

        if i < len(to_fetch):
            time.sleep(0.8)

    found    = sum(1 for v in cache.values() if v and v.get("rating") is not None)
    not_found = sum(1 for v in cache.values() if v is None or v.get("rating") is None)
    low_conf = sum(1 for v in cache.values() if v and 0 < v.get("num_ratings", 0) < 5)

    print(f"\nDone.")
    print(f"  Found:          {found}")
    print(f"  Not found:      {not_found}")
    print(f"  Low confidence: {low_conf}  (<5 ratings)")
    print(f"  Cache saved to: {CACHE_PATH}")
    print(f"\nNext: run scripts/merge_sources.py --rmp-only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch RMP ratings via GraphQL")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch instructors already in cache")
    args = parser.parse_args()
    run(force=args.force)
