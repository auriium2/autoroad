#!/usr/bin/env python3
"""
Clear Redis cache for requirements.

Run this after deploying changes to requirement parsing logic to ensure
stale cached data doesn't cause issues.

Usage:
    uv run python scripts/clear_cache.py [--all] [--pattern PATTERN]

Options:
    --all           Clear all autoroad caches (courses + requirements)
    --pattern       Clear caches matching pattern (e.g., '*_concentration')
                    Default: clears all requirement caches
"""

import argparse
import os
import sys

import redis


def main():
    parser = argparse.ArgumentParser(description="Clear Redis cache")
    parser.add_argument("--all", action="store_true", help="Clear all autoroad caches")
    parser.add_argument("--pattern", default="*", help="Pattern to match requirement keys")
    args = parser.parse_args()

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        print("REDIS_URL not set, nothing to clear")
        sys.exit(0)

    try:
        r = redis.from_url(redis_url, decode_responses=True)
        r.ping()
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        sys.exit(1)

    deleted = 0

    # Clear requirement caches
    req_pattern = f"autoroad:req:{args.pattern}"
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor, match=req_pattern, count=100)
        if keys:
            for key in keys:
                print(f"Deleting: {key}")
                r.delete(key)
                deleted += 1
        if cursor == 0:
            break

    # Clear courses cache if --all
    if args.all:
        if r.exists("autoroad:courses"):
            print("Deleting: autoroad:courses")
            r.delete("autoroad:courses")
            deleted += 1

    print(f"Deleted {deleted} cache entries")


if __name__ == "__main__":
    main()
