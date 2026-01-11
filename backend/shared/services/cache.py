"""
In-memory caching for courses and requirements data.
"""

import concurrent.futures
import threading
from pathlib import Path
from typing import Any

import polars as pl
import requests
from cachetools import TTLCache

from shared.courses.prerequisites.types import PrereqNode

REQUIREMENTS_DIR = Path(__file__).parent.parent.parent / "requirements"

_courses_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(maxsize=1, ttl=3600)
_courses_lock = threading.RLock()

_requirements_cache: TTLCache[str, dict[str, object]] = TTLCache(maxsize=128, ttl=3600)
_requirements_lock = threading.RLock()


def _fetch_courses() -> list[dict[str, Any]]:
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    return [c for c in response.json() if not c.get('is_historical')]


def get_courses_data() -> list[dict[str, Any]]:
    with _courses_lock:
        if "courses" in _courses_cache:
            return _courses_cache["courses"]

    data = _fetch_courses()

    with _courses_lock:
        _courses_cache["courses"] = data

    return data


def _parse_local_requirement(content: str) -> dict[str, object]:
    from shared.courses.requirements.fireroad_parser import parse_fireroad_file
    return parse_fireroad_file(content)


def _load_local_requirement(key: str) -> dict[str, object] | None:
    for ext in ['.fireroad', '.txt']:
        path = REQUIREMENTS_DIR / f"{key}{ext}"
        if path.exists():
            try:
                content = path.read_text()
                return _parse_local_requirement(content)
            except Exception as e:
                print(f"[CACHE] Error parsing local requirement {key}: {e}")
    return None


def fetch_requirement(key: str, source: str = "beta") -> dict[str, object]:
    if source == "canonical":
        try:
            resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError:
            local = _load_local_requirement(key)
            if local is not None:
                return local
            raise
    else:
        local = _load_local_requirement(key)
        if local is not None:
            return local

        resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
        resp.raise_for_status()
        return resp.json()


def _cache_key(key: str, source: str) -> str:
    return f"{key}:{source}"


def get_requirements(
    requirement_keys: tuple[str, ...],
    requirement_sources: dict[str, str] | None = None
) -> dict[str, object]:
    if not requirement_keys:
        return {}

    sources = requirement_sources or {}
    default_source = "canonical"

    result: dict[str, object] = {}
    missing: list[tuple[str, str]] = []

    with _requirements_lock:
        for key in requirement_keys:
            source = sources.get(key, default_source)
            cache_key = _cache_key(key, source)
            if cache_key in _requirements_cache:
                result[key] = _requirements_cache[cache_key]
            else:
                missing.append((key, source))

    if not missing:
        return result

    def fetch(k: str, src: str) -> tuple[str, str, dict[str, object]]:
        return k, src, fetch_requirement(k, src)

    with concurrent.futures.ThreadPoolExecutor() as ex:
        futures = [ex.submit(fetch, k, s) for k, s in missing]
        for future in concurrent.futures.as_completed(futures):
            key, source, data = future.result()
            result[key] = data
            cache_key = _cache_key(key, source)
            with _requirements_lock:
                _requirements_cache[cache_key] = data

    return result


def get_parsed_prerequisites(courses_df: pl.DataFrame) -> dict[int, PrereqNode]:
    from shared.courses.prerequisites.parser import parse_fireroad

    prereq_trees: dict[int, PrereqNode] = {}
    for course_idx in range(len(courses_df)):
        prereq_str = courses_df[course_idx, 'prerequisites']
        if prereq_str:
            try:
                tree = parse_fireroad(prereq_str)
                if tree is not None:
                    prereq_trees[course_idx] = tree
            except Exception:
                pass
    return prereq_trees


def clear_cache():
    with _courses_lock:
        _courses_cache.clear()
    with _requirements_lock:
        _requirements_cache.clear()
