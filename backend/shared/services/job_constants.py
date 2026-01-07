"""
Shared constants for job queue.

These are in a separate file to avoid pulling in httpx for workers
that only need the constants (not the full JobQueue class).
"""

from enum import Enum

# Keys
QUEUE_KEY = "optimize:queue"
JOB_PREFIX = "job:"
EVENTS_SUFFIX = ":events"
RESULT_SUFFIX = ":result"

# TTLs
JOB_TTL = 3600  # 1 hour
RESULT_TTL = 3600 * 24  # 24 hours


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
