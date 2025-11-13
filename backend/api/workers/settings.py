import os

from arq.connections import RedisSettings


def get_redis_settings() -> RedisSettings:
    """
    Get Redis settings for arq workers.
    Reads from environment variables or uses defaults.
    """
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_password = os.getenv("REDIS_PASSWORD", None)
    redis_db = int(os.getenv("REDIS_DB", "0"))

    return RedisSettings(
        host=redis_host,
        port=redis_port,
        password=redis_password,
        database=redis_db
    )
