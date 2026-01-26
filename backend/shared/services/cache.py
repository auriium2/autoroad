"""
Async caching for courses and requirements data using cashews.
"""

import asyncio
from pathlib import Path
from typing import Any

import httpx
import polars as pl
from cashews import cache

from shared.courses.prerequisites.types import PrereqNode

REQUIREMENTS_DIR = Path(__file__).parent.parent.parent / "requirements"
FIREROAD_BASE_URL = "https://fireroad.mit.edu"
HYDRANT_BASE_URL = "https://hydrant.mit.edu"

# Configure in-memory cache
cache.setup("mem://")


def _calculate_imdb_rating(rating: float | None, enrollment: int | None) -> float | None:
    if rating is None or enrollment is None:
        return None
    m = 30
    c = 5.0
    weighted = (enrollment / (enrollment + m)) * rating + (m / (enrollment + m)) * c
    return round(weighted, 1)


def _parse_prerequisites(courses: list[dict[str, Any]]) -> dict[str, PrereqNode]:
    """Parse all prerequisites and return a map from subject_id to PrereqNode."""
    from shared.courses.prerequisites.parser import parse_fireroad

    id2prereq: dict[str, PrereqNode] = {}
    for course in courses:
        prereq_str = course.get("prerequisites")
        if prereq_str:
            try:
                tree = parse_fireroad(prereq_str)
                if tree is not None:
                    id2prereq[course["subject_id"]] = tree
            except Exception:
                pass
    return id2prereq


@cache(ttl="1h", lock=True)
async def get_courses_data() -> list[dict[str, Any]]:
    """
    Fetch all courses from Fireroad API with caching.

    Pre-computes IMDB ratings to avoid per-request calculation.
    Uses lock=True to prevent thundering herd on cache miss.
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(f"{FIREROAD_BASE_URL}/courses/all?full=true")
        response.raise_for_status()
        courses = [c for c in response.json() if not c.get("is_historical")]

    # Pre-compute IMDB ratings
    for course in courses:
        course["imdb_rating"] = _calculate_imdb_rating(
            course.get("rating"),
            course.get("enrollment_number")
        )

    return courses


@cache(ttl="1h", lock=True)
async def get_parsed_prerequisites() -> dict[str, PrereqNode]:
    """
    Get parsed prerequisite trees for all courses.

    Returns a map from subject_id to PrereqNode.
    Cached separately from courses to avoid re-parsing on every request.
    """
    courses = await get_courses_data()
    return _parse_prerequisites(courses)


async def get_parsed_prerequisites_by_index(courses_df: pl.DataFrame) -> dict[int, PrereqNode]:
    """
    Get parsed prerequisites indexed by course position in DataFrame.

    This is a convenience wrapper that converts the subject_id-keyed cache
    to course_idx-keyed dict for use with the optimizer.
    """
    id2prereq = await get_parsed_prerequisites()

    subject_ids = courses_df["subject_id"].to_list()
    id2idx = {sid: idx for idx, sid in enumerate(subject_ids)}

    idx2prereq: dict[int, PrereqNode] = {}
    for subject_id, prereq in id2prereq.items():
        if subject_id in id2idx:
            idx2prereq[id2idx[subject_id]] = prereq

    return idx2prereq


def _parse_local_requirement(content: str) -> dict[str, object]:
    from shared.courses.requirements.fireroad_parser import parse_fireroad_file
    return parse_fireroad_file(content)


def _load_local_requirement(key: str) -> dict[str, object] | None:
    for ext in [".fireroad", ".txt"]:
        path = REQUIREMENTS_DIR / f"{key}{ext}"
        if path.exists():
            try:
                content = path.read_text()
                return _parse_local_requirement(content)
            except Exception as e:
                print(f"[CACHE] Error parsing local requirement {key}: {e}")
    return None


async def _fetch_requirement_from_fireroad(key: str) -> dict[str, object]:
    """Fetch a single requirement from Fireroad API."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(f"{FIREROAD_BASE_URL}/requirements/get_json/{key}")
        resp.raise_for_status()
        return resp.json()


@cache(ttl="1h", lock=True, key="{key}:{source}")
async def fetch_requirement(key: str, source: str = "beta") -> dict[str, object]:
    """
    Fetch a single requirement by key.

    Args:
        key: Requirement key (e.g., "girs", "major6-3")
        source: "canonical" for Fireroad-first, "beta" for local-first
    """
    if source == "canonical":
        try:
            return await _fetch_requirement_from_fireroad(key)
        except httpx.HTTPStatusError:
            local = _load_local_requirement(key)
            if local is not None:
                return local
            raise
    else:
        # Beta: try local first, then Fireroad
        local = _load_local_requirement(key)
        if local is not None:
            return local
        return await _fetch_requirement_from_fireroad(key)


async def get_requirements(
    requirement_keys: tuple[str, ...],
    requirement_sources: dict[str, str] | None = None
) -> dict[str, object]:
    """
    Fetch multiple requirements concurrently.

    Args:
        requirement_keys: Tuple of requirement keys to fetch
        requirement_sources: Optional map of key -> source ("canonical" or "beta")

    Returns:
        Dictionary mapping requirement keys to their parsed data
    """
    if not requirement_keys:
        return {}

    sources = requirement_sources or {}
    default_source = "canonical"


    async def fetch_one(key: str) -> tuple[str, dict[str, object]]:
        source = sources.get(key, default_source)
        data = await fetch_requirement(key, source)
        return key, data

    tasks = [fetch_one(key) for key in requirement_keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, object] = {}
    for result in results:
        if isinstance(result, BaseException):
            print(f"[CACHE] Error fetching requirement: {result}")
            continue
        key, data = result
        output[key] = data

    return output


async def clear_cache() -> None:
    """Clear all cached data."""
    await cache.clear()

@cache(ttl="1h", lock=True, key="hydrant:latest")
async def _get_hydrant_latest() -> dict[str, Any]:
    """Fetch latest.json from Hydrant."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(f"{HYDRANT_BASE_URL}/latest.json")
        response.raise_for_status()
        return response.json()


@cache(ttl="1h", lock=True, key="hydrant:{semester}")
async def get_hydrant_semester_data(semester: str) -> dict[str, Any]:
    url = f"{HYDRANT_BASE_URL}/latest.json" if semester == "latest" else f"{HYDRANT_BASE_URL}/{semester}.json"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type or response.text.strip().startswith("<!DOCTYPE"):
            raise ValueError(f"Semester {semester} not available on Hydrant")
        response.raise_for_status()
        return response.json()


async def get_hydrant_courses(
    semester: str,
    course_ids: list[str]
) -> dict[str, dict[str, Any]]:
    data = await get_hydrant_semester_data(semester)
    classes = data.get("classes", {})

    return {
        course_id: classes[course_id]
        for course_id in course_ids
        if course_id in classes
    }
