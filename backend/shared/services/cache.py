"""
Hybrid L1/L2 caching: in-memory (fast, short TTL) + Redis (shared, longer TTL).

L1: In-memory TTLCache - 60 second TTL, helps with burst requests on same instance
L2: Redis - 1 hour TTL, shared across all instances, survives restarts
"""

import concurrent.futures
import json
import os
import threading
from typing import cast

import polars as pl
import redis
import requests
from cachetools import TTLCache

from shared.courses.prerequisites.types import PrereqNode

REDIS_URL = os.environ.get("REDIS_URL")

# L1: In-memory caches (60s TTL - helps with sequential requests on same instance)
_courses_l1: TTLCache[str, list[dict[str, object]]] = TTLCache(maxsize=1, ttl=60)
_courses_lock = threading.RLock()

_requirements_l1: TTLCache[str, dict[str, object]] = TTLCache(maxsize=128, ttl=60)
_requirements_lock = threading.RLock()

# L2: Redis client (lazy init)
_redis_client: redis.Redis | None = None  # type: ignore[type-arg]
_redis_lock = threading.RLock()

COURSES_KEY = "autoroad:courses"
REQUIREMENTS_PREFIX = "autoroad:req:"
REDIS_TTL = 3600 * 24


def _get_redis() -> redis.Redis | None:  # type: ignore[type-arg]
    global _redis_client
    if _redis_client is None:
        with _redis_lock:
            if _redis_client is None:
                try:
                    _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                    _redis_client.ping()
                except Exception as e:
                    print(f"[CACHE] Redis unavailable: {e}")
                    return None
    return _redis_client


def _fetch_courses() -> list[dict[str, object]]:
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    return [c for c in response.json() if not c.get('is_historical')]


def get_courses_data() -> list[dict[str, object]]:
    # L1
    with _courses_lock:
        if "courses" in _courses_l1:
            return _courses_l1["courses"]

    # L2
    r = _get_redis()
    if r:
        try:
            cached = r.get(COURSES_KEY)
            if cached:
                data = json.loads(cached)
                with _courses_lock:
                    _courses_l1["courses"] = data
                return data
        except Exception:
            pass

    # Fetch
    data = _fetch_courses()

    with _courses_lock:
        _courses_l1["courses"] = data

    if r:
        try:
            r.setex(COURSES_KEY, REDIS_TTL, json.dumps(data))
        except Exception:
            pass

    return data


def _fetch_requirement(key: str) -> dict[str, object]:
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return resp.json()


def get_requirement(key: str) -> dict[str, object]:
    # L1
    with _requirements_lock:
        if key in _requirements_l1:
            return _requirements_l1[key]

    # L2
    r = _get_redis()
    if r:
        try:
            cached = r.get(f"{REQUIREMENTS_PREFIX}{key}")
            if cached:
                data = json.loads(cached)
                with _requirements_lock:
                    _requirements_l1[key] = data
                return data
        except Exception:
            pass

    # Fetch
    data = _fetch_requirement(key)

    with _requirements_lock:
        _requirements_l1[key] = data

    if r:
        try:
            r.setex(f"{REQUIREMENTS_PREFIX}{key}", REDIS_TTL, json.dumps(data))
        except Exception:
            pass

    return data


def get_requirements(requirement_keys: tuple[str, ...]) -> dict[str, object]:
    if not requirement_keys:
        return {}

    result: dict[str, object] = {}
    missing: list[str] = []

    # Check L1
    with _requirements_lock:
        for key in requirement_keys:
            if key in _requirements_l1:
                result[key] = _requirements_l1[key]
            else:
                missing.append(key)

    if not missing:
        return result

    # Check L2 for missing
    r = _get_redis()
    still_missing: list[str] = []

    if r:
        try:
            keys = [f"{REQUIREMENTS_PREFIX}{k}" for k in missing]
            values = r.mget(keys)
            for key, val in zip(missing, values):
                if val:
                    data = json.loads(val)
                    result[key] = data
                    with _requirements_lock:
                        _requirements_l1[key] = data
                else:
                    still_missing.append(key)
        except Exception:
            still_missing = missing
    else:
        still_missing = missing

    # Fetch remaining in parallel
    if still_missing:
        def fetch(k: str) -> tuple[str, dict[str, object]]:
            return k, _fetch_requirement(k)

        with concurrent.futures.ThreadPoolExecutor() as ex:
            futures = [ex.submit(fetch, k) for k in still_missing]
            for future in concurrent.futures.as_completed(futures):
                key, data = future.result()
                result[key] = data
                with _requirements_lock:
                    _requirements_l1[key] = data
                if r:
                    try:
                        r.setex(f"{REQUIREMENTS_PREFIX}{key}", REDIS_TTL, json.dumps(data))
                    except Exception:
                        pass

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
        _courses_l1.clear()
    with _requirements_lock:
        _requirements_l1.clear()

    r = _get_redis()
    if r:
        try:
            r.delete(COURSES_KEY)
            cursor: int = 0
            while True:
                scan_result = cast(tuple[int, list[str]], r.scan(cursor, match=f"{REQUIREMENTS_PREFIX}*", count=100))
                cursor = scan_result[0]
                keys = scan_result[1]
                if keys:
                    r.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            pass
