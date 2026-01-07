"""
Redis-based job queue for optimization requests.

Architecture:
- Jobs are stored in Redis hashes: job:{job_id}
- Job queue is a Redis list: optimize:queue
- Events are published via Redis pub/sub: job:{job_id}:events
- Workers pull jobs from queue, publish progress, store results

This decouples the server from workers, enabling:
- Job queuing with position tracking
- Resilient reconnects (frontend can resume from job state)
- Horizontal worker scaling
"""

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
import redis.asyncio as aioredis

from shared.services.job_constants import (
    EVENTS_SUFFIX,
    JOB_PREFIX,
    JOB_TTL,
    QUEUE_KEY,
    RESULT_SUFFIX,
    RESULT_TTL,
    JobStatus,
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
WORKER_WEBHOOK_URL = os.environ.get("WORKER_WEBHOOK_URL", "")


@dataclass
class Job:
    job_id: str
    status: JobStatus
    request: dict[str, Any]
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    queue_position: int | None = None


class JobQueue:
    def __init__(self, redis_url: str = REDIS_URL):
        self.redis_url = redis_url
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def close(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def create_job(self, request: dict[str, Any]) -> str:
        """Create a job and trigger the worker webhook."""
        r = await self._get_redis()
        job_id = str(uuid.uuid4())
        job_key = f"{JOB_PREFIX}{job_id}"

        job_data = {
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "request": json.dumps(request),
            "created_at": time.time(),
        }

        await r.hset(job_key, mapping=job_data)
        await r.expire(job_key, JOB_TTL)
        await r.lpush(QUEUE_KEY, job_id)

        if WORKER_WEBHOOK_URL:
            await self._trigger_webhook(job_id)

        return job_id

    async def _trigger_webhook(self, job_id: str):
        """Notify worker to pick up job immediately."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(WORKER_WEBHOOK_URL, json={"job_id": job_id})
        except Exception as e:
            print(f"[QUEUE] Webhook trigger failed: {e}")

    async def get_job(self, job_id: str) -> Job | None:
        r = await self._get_redis()
        job_key = f"{JOB_PREFIX}{job_id}"
        data = await r.hgetall(job_key)

        if not data:
            return None

        queue_position, _ = await self._get_queue_position(job_id)

        return Job(
            job_id=data["job_id"],
            status=JobStatus(data["status"]),
            request=json.loads(data["request"]),
            created_at=float(data["created_at"]),
            started_at=float(data["started_at"]) if data.get("started_at") else None,
            completed_at=float(data["completed_at"]) if data.get("completed_at") else None,
            error=data.get("error"),
            queue_position=queue_position,
        )

    async def _get_queue_position(self, job_id: str) -> tuple[int | None, int]:
        """Get queue position and total queue length."""
        r = await self._get_redis()
        queue = await r.lrange(QUEUE_KEY, 0, -1)
        queue_length = len(queue)
        try:
            position = queue.index(job_id) + 1
            return position, queue_length
        except ValueError:
            return None, queue_length

    # ─── Worker Methods ───

    async def pop_job(self, timeout: float = 0) -> str | None:
        """Pop the next job from the queue. Blocks up to timeout seconds."""
        r = await self._get_redis()
        result = await r.brpop(QUEUE_KEY, timeout=timeout)
        if result:
            _, job_id = result
            return job_id
        return None

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None
    ):
        r = await self._get_redis()
        job_key = f"{JOB_PREFIX}{job_id}"

        updates: dict[str, Any] = {"status": status.value}
        if status == JobStatus.RUNNING:
            updates["started_at"] = time.time()
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            updates["completed_at"] = time.time()
        if error:
            updates["error"] = error

        await r.hset(job_key, mapping=updates)
        await r.expire(job_key, JOB_TTL)

    async def publish_event(self, job_id: str, event: dict[str, Any]):
        """Publish an event to the job's channel."""
        r = await self._get_redis()
        channel = f"{JOB_PREFIX}{job_id}{EVENTS_SUFFIX}"
        await r.publish(channel, json.dumps(event))

    async def store_result(self, job_id: str, result: dict[str, Any]):
        """Store the final result for later retrieval."""
        r = await self._get_redis()
        result_key = f"{JOB_PREFIX}{job_id}{RESULT_SUFFIX}"
        await r.set(result_key, json.dumps(result), ex=RESULT_TTL)

    async def get_result(self, job_id: str) -> dict[str, Any] | None:
        """Get stored result if job is complete."""
        r = await self._get_redis()
        result_key = f"{JOB_PREFIX}{job_id}{RESULT_SUFFIX}"
        data = await r.get(result_key)
        if data:
            return json.loads(data)
        return None

    # ─── Server Methods (SSE Streaming) ───

    async def subscribe_to_job(self, job_id: str) -> AsyncIterator[dict[str, Any]]:
        """
        Subscribe to job events. Yields events as they arrive.
        Handles reconnection by checking job status and replaying result if complete.
        """
        r = await self._get_redis()
        job = await self.get_job(job_id)

        if not job:
            yield {"type": "error", "error": "Job not found"}
            return

        # If already complete, return cached result
        if job.status == JobStatus.COMPLETED:
            result = await self.get_result(job_id)
            if result:
                for event in result.get("events", []):
                    yield event
            return

        if job.status == JobStatus.FAILED:
            yield {"type": "error", "error": job.error or "Job failed"}
            return

        # Send queue position if still queued
        if job.status == JobStatus.QUEUED and job.queue_position:
            position, queue_length = await self._get_queue_position(job_id)
            yield {
                "type": "queued",
                "position": position,
                "queueLength": queue_length,
                "message": f"Position {position} of {queue_length} in queue" if queue_length > 1 else "Starting worker..."
            }

        # Subscribe to events
        pubsub = r.pubsub()
        channel = f"{JOB_PREFIX}{job_id}{EVENTS_SUFFIX}"
        await pubsub.subscribe(channel)

        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0
                    )
                    if message and message["type"] == "message":
                        event = json.loads(message["data"])
                        yield event

                        if event.get("type") in ("complete", "error"):
                            break
                except asyncio.TimeoutError:
                    job = await self.get_job(job_id)
                    if not job:
                        yield {"type": "error", "error": "Job disappeared"}
                        break
                    if job.status == JobStatus.FAILED:
                        yield {"type": "error", "error": job.error or "Job failed"}
                        break
                    if job.status == JobStatus.COMPLETED:
                        result = await self.get_result(job_id)
                        if result:
                            for event in result.get("events", []):
                                if event.get("type") == "complete":
                                    yield event
                        break
                    if job.status == JobStatus.QUEUED:
                        position, queue_length = await self._get_queue_position(job_id)
                        if position:
                            yield {
                                "type": "queued",
                                "position": position,
                                "queueLength": queue_length,
                                "message": f"Position {position} of {queue_length} in queue" if queue_length > 1 else "Starting worker..."
                            }
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()


# Singleton instance
_job_queue: JobQueue | None = None


def get_job_queue() -> JobQueue:
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    return _job_queue
