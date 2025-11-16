import asyncio
import json
import uuid

from arq import create_pool
from backend.api.models.requests import OptimizationRequest
from backend.api.services.cache import clear_cache, get_courses_data, get_requirements
from backend.api.services.redis_client import get_redis
from backend.api.workers.settings import get_redis_settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post("/optimize")
async def optimize(request: OptimizationRequest):
    """
    Start optimization job and stream progress via SSE.
    
    The job runs on a background worker process and publishes updates to Redis Stream.
    This endpoint streams those updates to the client in real-time.
    
    Returns:
        SSE stream with messages:
        - progress: Status updates
        - solution: New solution found
        - complete: Optimization finished
        - error: Error occurred
    """

    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Get data for optimization
        courses_data = get_courses_data()
        requirements_data = get_requirements(tuple(request.requirements))

        request_dict = request.model_dump()

        # Enqueue job to arq worker
        redis_pool = await create_pool(get_redis_settings())

        await redis_pool.enqueue_job(
            'run_optimization_job',
            job_id,
            request_dict,
            courses_data,
            requirements_data,
            _job_id=job_id
        )

        # Stream results from Redis Stream
        async def event_stream():
            redis_client = await get_redis()
            last_id = '0'
            timeout_counter = 0
            max_timeouts = 600  # 60 seconds max wait (100ms * 600)

            # First message: send job_id so client can cancel
            yield f"data: {json.dumps({'type': 'job_started', 'job_id': job_id})}\n\n"

            # Stream until we see a 'complete' or 'error' message
            while timeout_counter < max_timeouts:
                # Read from Redis Stream (blocking with timeout)
                messages = await redis_client.xread(
                    {f"optimization:{job_id}": last_id},
                    count=10,
                    block=100  # 100ms timeout
                )

                if messages:
                    timeout_counter = 0  # Reset timeout on activity
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            last_id = message_id
                            data = message_data.get('data', '{}')

                            # Yield SSE message
                            yield f"data: {data}\n\n"

                            # Check if we're done
                            parsed = json.loads(data)
                            if parsed.get('type') in ['complete', 'error']:
                                return
                else:
                    timeout_counter += 1
                    await asyncio.sleep(0.01)  # Small delay

            # Timeout - send error
            yield f"data: {json.dumps({'type': 'error', 'error': 'Job timeout'})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimize/{job_id}")
async def get_optimization_result(job_id: str):
    """
    Get the result of a completed optimization job.
    
    Useful if SSE stream was interrupted or client wants to retrieve
    results after reconnecting.
    
    Returns:
        - 200: Job completed, returns result
        - 202: Job still running/queued
        - 404: Job not found or expired
    """
    redis_client = await get_redis()

    # Check if job result exists
    result = await redis_client.get(f"optimization:result:{job_id}")

    if result:
        return {
            "status": "completed",
            "result": json.loads(result)
        }

    # Check if job is still in queue/running
    from arq.jobs import Job, JobStatus
    redis_pool = await create_pool(get_redis_settings())

    try:
        job = Job(job_id, redis_pool)
        job_info = await job.info()

        if job_info:
            status_map = {
                JobStatus.deferred: "queued",
                JobStatus.queued: "queued",
                JobStatus.in_progress: "running",
                JobStatus.complete: "completed",
                JobStatus.not_found: "not_found"
            }

            return {
                "status": status_map.get(job_info.status, "unknown"),
                "job_status": str(job_info.status)
            }
    except:
        pass

    raise HTTPException(status_code=404, detail="Job not found or expired")


@router.delete("/optimize/{job_id}")
async def cancel_optimization(job_id: str):
    """
    Cancel an optimization job (queued or running).
    
    Two-phase cancellation:
    1. Abort job in queue (if not started yet)
    2. Set cancellation flag for running jobs (checked on each solution)
    
    Guarantees cancellation within 1-2 seconds regardless of job state.
    """
    redis_pool = await create_pool(get_redis_settings())
    redis_client = await get_redis()

    # Phase 1: Try to abort if still in queue
    from arq.jobs import Job
    try:
        job = Job(job_id, redis_pool)
        await job.abort()
    except:
        pass  # Job might not exist or already running

    # Phase 2: Set cancellation flag for running jobs
    await redis_client.set(f"cancel:{job_id}", "1", ex=60)

    return {"message": f"Cancellation requested for job {job_id}"}


@router.post("/optimize/clear-cache")
async def clear_optimization_cache():
    """
    Clear all cached course and requirement data.
    Useful for forcing a refresh from Fireroad API.
    """
    clear_cache()
    return {"message": "Cache cleared successfully"}
