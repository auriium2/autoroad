import os
from typing import Optional

import redis.asyncio as redis

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """
    Get Redis client singleton.
    Connection pooling handled automatically by redis-py.
    """
    global _redis_client

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            encoding="utf-8"
        )

    return _redis_client


async def close_redis():
    """Close Redis connection (call on shutdown)"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
