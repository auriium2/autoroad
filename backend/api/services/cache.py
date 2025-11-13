import concurrent.futures
import threading
from typing import Any, Dict, List

import requests
from cachetools import TTLCache, cached

# Cache for 1 hour (3600 seconds)
# Course data changes infrequently
_courses_cache = TTLCache(maxsize=1, ttl=3600)
_courses_lock = threading.RLock()

# Cache requirements for 1 hour
# Individual requirements cached separately
_requirements_cache = TTLCache(maxsize=128, ttl=3600)
_requirements_lock = threading.RLock()


@cached(cache=_courses_cache, lock=_courses_lock)
def get_courses_data() -> List[Dict[str, Any]]:
    """
    Fetch and cache all courses from Fireroad API.
    Cached for 1 hour, then automatically evicted.
    Returns raw course data as list of dicts.
    """
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    data = response.json()

    # Filter out historical courses
    courses = [c for c in data if not c.get('is_historical')]

    return courses


def fetch_requirement(key: str) -> tuple[str, Dict[str, Any]]:
    """Fetch a single requirement from Fireroad API"""
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return key, resp.json()


@cached(cache=_requirements_cache, lock=_requirements_lock)
def get_requirement(key: str) -> Dict[str, Any]:
    """
    Fetch and cache a single requirement.
    Cached for 1 hour per requirement key.
    """
    _, data = fetch_requirement(key)
    return data


def get_requirements(requirement_keys: tuple[str, ...]) -> Dict[str, Any]:
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


def clear_cache():
    """Clear all caches (useful for testing or forcing refresh)"""
    with _courses_lock:
        _courses_cache.clear()
    with _requirements_lock:
        _requirements_cache.clear()
