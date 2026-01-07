"""
Base worker logic for processing optimization jobs from Redis queue.

This module contains the core worker logic that can be used by any executor:
- Cloud Run (HTTP triggered)
- Modal (serverless)
- GCE (always-on VM)
- Local development

The worker:
1. Pulls jobs from Redis queue
2. Runs optimization
3. Publishes progress events to Redis pub/sub
4. Stores final result in Redis
"""

import asyncio
import json
import os
import time
from typing import Any

import redis

from shared.models.requests import OptimizationRequest
from shared.optimize import run_optimization
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


class QueueWorker:
    """
    Worker that processes jobs from Redis queue.
    
    Can run in two modes:
    - poll(): Continuously poll for jobs (for always-on workers)
    - process_one(): Process a single job (for serverless/triggered workers)
    """

    def __init__(self, redis_url: str = REDIS_URL):
        self.redis_url = redis_url
        self._redis: redis.Redis | None = None
        self._pending_events: list[tuple[str, dict[str, Any]]] = []
        self._batch_size = 2  # Publish every 2 progress events for responsiveness

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def close(self):
        if self._redis:
            self._redis.close()
            self._redis = None

    def _publish_event(self, job_id: str, event: dict[str, Any]):
        """Publish event to job channel using pipeline for batching."""
        r = self._get_redis()
        channel = f"{JOB_PREFIX}{job_id}{EVENTS_SUFFIX}"
        r.publish(channel, json.dumps(event))

    def _publish_events_batch(self, job_id: str, events: list[dict[str, Any]]):
        """Publish multiple events in a single pipeline."""
        if not events:
            return
        r = self._get_redis()
        channel = f"{JOB_PREFIX}{job_id}{EVENTS_SUFFIX}"
        pipe = r.pipeline()
        for event in events:
            pipe.publish(channel, json.dumps(event))
        pipe.execute()

    def _update_status(self, job_id: str, status: JobStatus, error: str | None = None):
        """Update job status in Redis."""
        r = self._get_redis()
        job_key = f"{JOB_PREFIX}{job_id}"

        updates: dict[str, Any] = {"status": status.value}
        if status == JobStatus.RUNNING:
            updates["started_at"] = time.time()
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            updates["completed_at"] = time.time()
        if error:
            updates["error"] = error

        r.hset(job_key, mapping=updates)
        r.expire(job_key, JOB_TTL)

    def _store_result(self, job_id: str, events: list[dict[str, Any]]):
        """Store all events for later retrieval (reconnection support)."""
        r = self._get_redis()
        result_key = f"{JOB_PREFIX}{job_id}{RESULT_SUFFIX}"
        r.set(result_key, json.dumps({"events": events}), ex=RESULT_TTL)

    def _get_job_request(self, job_id: str) -> dict[str, Any] | None:
        """Get job request data from Redis."""
        r = self._get_redis()
        job_key = f"{JOB_PREFIX}{job_id}"
        data = r.hget(job_key, "request")
        if data:
            return json.loads(data)
        return None

    def process_job(self, job_id: str) -> bool:
        """
        Process a single job. Returns True if successful.
        
        This is the main entry point for job processing.
        """
        timings: dict[str, float] = {}
        t_start = time.time()

        print(f"[WORKER] Processing job {job_id}")

        # Get job request
        t0 = time.time()
        request_data = self._get_job_request(job_id)
        timings["get_request"] = time.time() - t0

        if not request_data:
            print(f"[WORKER] Job {job_id} not found or missing request")
            self._update_status(job_id, JobStatus.FAILED, "Job request not found")
            self._publish_event(job_id, {"type": "error", "error": "Job request not found"})
            return False

        # Update status to running and notify frontend
        t0 = time.time()
        self._update_status(job_id, JobStatus.RUNNING)
        self._publish_event(job_id, {
            "type": "worker_started",
            "message": "Worker picked up job",
        })
        timings["update_status_running"] = time.time() - t0

        # Parse request
        try:
            t0 = time.time()
            request = OptimizationRequest(**request_data)
            timings["parse_request"] = time.time() - t0
        except Exception as e:
            error_msg = f"Invalid request: {e}"
            print(f"[WORKER] {error_msg}")
            self._update_status(job_id, JobStatus.FAILED, error_msg)
            self._publish_event(job_id, {"type": "error", "error": error_msg})
            return False

        # Run optimization and publish events
        all_events: list[dict[str, Any]] = []
        pending_batch: list[dict[str, Any]] = []
        publish_times: list[float] = []

        try:
            # Run the async optimization in a sync context
            async def run():
                nonlocal timings, pending_batch
                t_opt_start = time.time()
                async for event in run_optimization(request):
                    if event.get("type") == "solution":
                        timings["optimization_to_solution"] = time.time() - t_opt_start
                    all_events.append(event)

                    event_type = event.get("type")
                    # Batch progress events, immediately publish solutions/complete
                    if event_type in ("solution", "complete", "error"):
                        # Flush any pending progress events first
                        if pending_batch:
                            t_pub = time.time()
                            self._publish_events_batch(job_id, pending_batch)
                            publish_times.append(time.time() - t_pub)
                            pending_batch = []
                        # Then publish the important event immediately
                        t_pub = time.time()
                        self._publish_event(job_id, event)
                        publish_times.append(time.time() - t_pub)
                    else:
                        # Buffer progress events
                        pending_batch.append(event)
                        # Flush batch every 2 events for responsiveness
                        if len(pending_batch) >= 2:
                            t_pub = time.time()
                            self._publish_events_batch(job_id, pending_batch)
                            publish_times.append(time.time() - t_pub)
                            pending_batch = []

                # Flush any remaining events
                if pending_batch:
                    t_pub = time.time()
                    self._publish_events_batch(job_id, pending_batch)
                    publish_times.append(time.time() - t_pub)
                    pending_batch = []

                timings["optimization_total"] = time.time() - t_opt_start

            t0 = time.time()
            asyncio.run(run())
            timings["asyncio_run"] = time.time() - t0

            if publish_times:
                timings["publish_count"] = len(all_events)
                timings["publish_batches"] = len(publish_times)
                timings["publish_total"] = sum(publish_times)
                timings["publish_avg_batch"] = sum(publish_times) / len(publish_times)
                timings["publish_max"] = max(publish_times)

            # Store result and update status in pipeline
            t0 = time.time()
            r = self._get_redis()
            pipe = r.pipeline()
            result_key = f"{JOB_PREFIX}{job_id}{RESULT_SUFFIX}"
            pipe.set(result_key, json.dumps({"events": all_events}), ex=RESULT_TTL)
            job_key = f"{JOB_PREFIX}{job_id}"
            pipe.hset(job_key, mapping={"status": JobStatus.COMPLETED.value, "completed_at": time.time()})
            pipe.expire(job_key, JOB_TTL)
            pipe.execute()
            timings["store_and_complete"] = time.time() - t0

            timings["total"] = time.time() - t_start

            print(f"[WORKER] Job {job_id} completed with {len(all_events)} events")
            print(f"[WORKER] TIMINGS: {json.dumps(timings, indent=2)}")
            return True

        except Exception as e:
            error_msg = f"Optimization failed: {e}"
            print(f"[WORKER] {error_msg}")
            error_event = {"type": "error", "error": str(e), "details": type(e).__name__}
            all_events.append(error_event)
            self._publish_event(job_id, error_event)
            self._store_result(job_id, all_events)
            self._update_status(job_id, JobStatus.FAILED, str(e))
            return False

    def poll(self, timeout: float = 5.0):
        """
        Continuously poll for jobs. Blocks until a job is available.
        
        For always-on workers (GCE, local development).
        """
        r = self._get_redis()
        print(f"[WORKER] Polling for jobs on {QUEUE_KEY}...")

        while True:
            try:
                # Block waiting for job
                result = r.brpop(QUEUE_KEY, timeout=timeout)
                if result:
                    _, job_id = result
                    self.process_job(job_id)
                # If timeout, loop continues (allows for graceful shutdown checks)
            except KeyboardInterrupt:
                print("[WORKER] Shutting down...")
                break
            except Exception as e:
                print(f"[WORKER] Error polling: {e}")
                time.sleep(1)  # Back off on error

    def process_one(self, timeout: float = 0) -> bool:
        """
        Try to process one job from the queue.
        
        For serverless workers that are triggered externally.
        Returns True if a job was processed.
        """
        r = self._get_redis()

        if timeout > 0:
            result = r.brpop(QUEUE_KEY, timeout=timeout)
        else:
            result = r.rpop(QUEUE_KEY)
            if result:
                result = (QUEUE_KEY, result)

        if result:
            _, job_id = result
            self.process_job(job_id)
            return True
        return False


def run_worker_loop():
    """Entry point for running the worker in polling mode."""
    worker = QueueWorker()
    try:
        worker.poll()
    finally:
        worker.close()


if __name__ == "__main__":
    run_worker_loop()
