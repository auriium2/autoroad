from .optimizer_worker import run_optimization_job
from .settings import get_redis_settings


async def startup(ctx):
    """Called when worker starts up"""
    print("Starting optimization worker...")


async def shutdown(ctx):
    """Called when worker shuts down"""
    print("Shutting down optimization worker...")


class WorkerSettings:
    """
    arq worker configuration.
    
    CP-SAT releases the GIL during solving, allowing multiple jobs to run
    concurrently in the same worker process via asyncio + run_in_executor.
    
    Note: We use enumerate_all_solutions with callbacks for streaming, which
    disables CP-SAT's internal multi-threading. Each solve runs single-threaded,
    but multiple solves can run in parallel in the same process (GIL released).
    
    Scale workers:
    - Horizontally: Run multiple worker processes (different machines/containers)
    - Vertically: Increase max_jobs (2-4 recommended based on CPU cores)
    """

    functions = [run_optimization_job]
    redis_settings = get_redis_settings()

    # Worker configuration
    # CP-SAT releases GIL, so 2-4 jobs can run concurrently per worker
    max_jobs = 2  # Adjust based on available CPU cores
    job_timeout = 300  # 5 minutes max per job

    # Hooks
    on_startup = startup
    on_shutdown = shutdown

    # Retry configuration
    max_tries = 1  # Don't retry optimization jobs (deterministic)

    # Health check
    health_check_interval = 60
