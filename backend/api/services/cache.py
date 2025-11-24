import concurrent.futures
import threading

import polars as pl
import requests
from cachetools import TTLCache, cached

_courses_cache: TTLCache[str, list[dict[str, object]]] = TTLCache(maxsize=1, ttl=3600)
_courses_lock = threading.RLock()

_requirements_cache: TTLCache[str, dict[str, object]] = TTLCache(maxsize=128, ttl=3600)
_requirements_lock = threading.RLock()

@cached(cache=_courses_cache, lock=_courses_lock)
def get_courses_data() -> list[dict[str, object]]:
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    data = response.json()

    # Filter out historical courses
    courses = [c for c in data if not c.get('is_historical')]

    return courses


def fetch_requirement(key: str) -> tuple[str, dict[str, object]]:
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return key, resp.json()


@cached(cache=_requirements_cache, lock=_requirements_lock)
def get_requirement(key: str) -> dict[str, object]:
    _, data = fetch_requirement(key)
    return data


def get_requirements(requirement_keys: tuple[str, ...]) -> dict[str, object]:
    """
    Fetch multiple requirements, using cache for each.

    Args:
        requirement_keys: Tuple of requirement keys (must be tuple for hashability)

    Returns:
        Dictionary mapping requirement keys to their data
    """
    if not requirement_keys:
        return {}

    # Check which keys are missing from cache
    with _requirements_lock:
        missing_keys = [k for k in requirement_keys if k not in _requirements_cache]

    if missing_keys:
        # Fetch missing keys in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(fetch_requirement, key): key for key in missing_keys}
            for future in concurrent.futures.as_completed(futures):
                key, data = future.result()
                # Populate cache
                get_requirement(key)

    # Return all requested requirements from cache
    return {k: get_requirement(k) for k in requirement_keys}


def get_parsed_prerequisites(courses_df: pl.DataFrame) -> dict[int, object]:
    """
    Parse prerequisite trees for all courses.

    Args:
        courses_df: Polars DataFrame with course data

    Returns:
        Dictionary mapping course_idx to parsed PrereqNode
    """
    from courses.prerequisites.parser import parse_fireroad

    prereq_trees = {}
    for course_idx in range(len(courses_df)):
        prereq_str = courses_df[course_idx, 'prerequisites']

        if prereq_str is not None and prereq_str:
            try:
                prereq_tree = parse_fireroad(prereq_str)
                # Only add to prereq_trees if parser returned a valid tree
                if prereq_tree is not None:
                    prereq_trees[course_idx] = prereq_tree
            except Exception:
                pass

    return prereq_trees


def clear_cache():
    """Clear all caches (useful for testing or forcing refresh)"""
    with _courses_lock:
        _courses_cache.clear()
    with _requirements_lock:
        _requirements_cache.clear()
