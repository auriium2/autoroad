"""
Async caching for courses and requirements data using cashews.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import polars as pl
from cashews import cache
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger("uvicorn.error")

from shared.courses.prerequisites.types import PrereqNode

REQUIREMENTS_DIR = Path(__file__).parent.parent.parent / "requirements"
FIREROAD_BASE_URL = "https://fireroad.mit.edu"
HYDRANT_BASE_URL = "https://hydrant.mit.edu"

# Configure in-memory cache
cache.setup("mem://")

# Shared HTTP client for connection pooling
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Get the shared HTTP client, creating it if necessary."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _http_client


async def close_http_client() -> None:
    """Close the shared HTTP client. Call this on app shutdown."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


@asynccontextmanager
async def lifespan_http_client():
    """Context manager for managing the HTTP client lifecycle."""
    yield get_http_client()
    await close_http_client()


# Retry decorator for external API calls
def with_retry():
    """Decorator for retrying external API calls with exponential backoff."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )


def _calculate_imdb_rating(rating: float | None, enrollment: int | None) -> float | None:
    if rating is None or enrollment is None:
        return None
    m = 30
    c = 5.0
    weighted = (enrollment / (enrollment + m)) * rating + (m / (enrollment + m)) * c
    return round(weighted, 1)


def _build_equivalency_map(courses: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Build a symmetric equivalency map from course data."""
    equivalencies: dict[str, set[str]] = {}

    for course in courses:
        course_id = course.get("subject_id")
        equiv_list = course.get("equivalent_subjects")
        if course_id and equiv_list:
            if course_id not in equivalencies:
                equivalencies[course_id] = set()
            equivalencies[course_id].update(equiv_list)
            # Add reverse mappings for symmetry
            for equiv_id in equiv_list:
                if equiv_id not in equivalencies:
                    equivalencies[equiv_id] = set()
                equivalencies[equiv_id].add(course_id)

    return {k: list(v) for k, v in equivalencies.items()}


def _inject_equivalencies(node: PrereqNode, equivalencies: dict[str, list[str]]) -> PrereqNode:
    """
    Recursively inject equivalent courses into a prereq tree.
    
    Transforms PrereqCourse("18.06") into PrereqGroup(threshold=1, items=(PrereqCourse("18.06"), PrereqCourse("18.C06")))
    when 18.06 has equivalents.
    """
    from shared.courses.prerequisites.types import PrereqCourse, PrereqGroup

    if isinstance(node, PrereqCourse):
        equiv_list = equivalencies.get(node.course_id)
        if equiv_list:
            # Create OR group: original course OR any equivalent
            items = [node] + [PrereqCourse(course_id=equiv_id) for equiv_id in equiv_list]
            return PrereqGroup(threshold=1, items=tuple(items))
        return node

    elif isinstance(node, PrereqGroup):
        # Recursively process children
        new_items = tuple(_inject_equivalencies(item, equivalencies) for item in node.items)
        return PrereqGroup(threshold=node.threshold, items=new_items, was_pruned=node.was_pruned)

    return node


def _parse_prerequisites(courses: list[dict[str, Any]]) -> dict[str, PrereqNode]:
    """Parse all prerequisites and return a map from subject_id to PrereqNode."""
    from shared.courses.prerequisites.parser import parse_fireroad

    # Build equivalency map first
    equivalencies = _build_equivalency_map(courses)

    id2prereq: dict[str, PrereqNode] = {}
    for course in courses:
        prereq_str = course.get("prerequisites")
        if prereq_str:
            try:
                tree = parse_fireroad(prereq_str)
                if tree is not None:
                    # Inject equivalencies into the tree
                    tree = _inject_equivalencies(tree, equivalencies)
                    id2prereq[course["subject_id"]] = tree
            except Exception:
                pass
    return id2prereq


@with_retry()
async def _fetch_courses_from_fireroad() -> list[dict[str, Any]]:
    """Fetch courses from Fireroad API with retry logic."""
    client = get_http_client()
    response = await client.get(f"{FIREROAD_BASE_URL}/courses/all?full=true")
    response.raise_for_status()
    return [c for c in response.json() if not c.get("is_historical")]


@cache(ttl="1h", lock=True)
async def get_courses_data() -> list[dict[str, Any]]:
    """
    Fetch all courses from Fireroad API with caching.

    Pre-computes IMDB ratings to avoid per-request calculation.
    Uses lock=True to prevent thundering herd on cache miss.
    """
    courses = await _fetch_courses_from_fireroad()

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
                logger.warning("Error parsing local requirement %s: %s", key, e)
    return None


@with_retry()
async def _fetch_requirement_from_fireroad(key: str) -> dict[str, object]:
    """Fetch a single requirement from Fireroad API with retry logic."""
    client = get_http_client()
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
            logger.warning("Error fetching requirement: %s", result)
            continue
        key, data = result
        output[key] = data

    return output


async def clear_cache() -> None:
    """Clear all cached data."""
    await cache.clear()

@with_retry()
async def _fetch_hydrant_data(url: str) -> dict[str, Any]:
    """Fetch data from Hydrant API with retry logic."""
    client = get_http_client()
    response = await client.get(url)
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type or response.text.strip().startswith("<!DOCTYPE"):
        raise ValueError(f"URL {url} returned HTML instead of JSON")
    response.raise_for_status()
    return response.json()


@cache(ttl="1h", lock=True, key="hydrant:latest")
async def _get_hydrant_latest() -> dict[str, Any]:
    """Fetch latest.json from Hydrant."""
    return await _fetch_hydrant_data(f"{HYDRANT_BASE_URL}/latest.json")


@cache(ttl="1h", lock=True, key="hydrant:{semester}")
async def get_hydrant_semester_data(semester: str) -> dict[str, Any]:
    url = f"{HYDRANT_BASE_URL}/latest.json" if semester == "latest" else f"{HYDRANT_BASE_URL}/{semester}.json"
    return await _fetch_hydrant_data(url)


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
