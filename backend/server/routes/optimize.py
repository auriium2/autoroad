import asyncio
import json
import os

import polars as pl
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from ortools.sat.python import cp_model

from shared.courses.requirements.parser import parse_fireroad_response
from shared.courses.requirements.validator import validate_and_prune
from shared.models.requests import OptimizationRequest
from shared.optimizer.constraints.basic import create_take_vars
from shared.optimizer.constraints.registry import get_all_constraints
from shared.optimizer.objectives.registry import get_all_objectives, get_default_objectives
from shared.optimizer.requirements.builder import add_requirement_constraints
from shared.services.cache import get_courses_data, get_requirements
from shared.utils import find_current_school_year

router = APIRouter()

# Execution modes:
# - "local": Run optimization in-process (development)
# - "direct": Proxy to worker's /optimize endpoint (production, single worker)
# - "queue": Use Redis job queue (production, multi-worker)
EXECUTION_MODE = os.environ.get("EXECUTION_MODE", "local")
WORKER_URL = os.environ.get("WORKER_URL", "")


async def event_stream_local(request: OptimizationRequest):
    """Stream optimization results locally (development mode)."""
    from shared.optimize import event_stream

    try:
        async for line in event_stream(request):
            yield line
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'details': type(e).__name__})}\n\n"


async def event_stream_direct(request: OptimizationRequest):
    """Stream optimization by proxying directly to worker (single worker mode)."""
    import httpx

    if not WORKER_URL:
        yield f"data: {json.dumps({'type': 'error', 'error': 'WORKER_URL not configured'})}\n\n"
        return

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                f"{WORKER_URL}/optimize",
                json=request.model_dump(),
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status_code != 200:
                    yield f"data: {json.dumps({'type': 'error', 'error': f'Worker returned {response.status_code}'})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if line:
                        yield f"{line}\n"

    except httpx.ConnectError as e:
        yield f"data: {json.dumps({'type': 'error', 'error': 'Failed to connect to worker', 'details': str(e)})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'details': type(e).__name__})}\n\n"


async def event_stream_via_queue(request: OptimizationRequest):
    """Stream optimization results via Redis job queue (multi-worker mode)."""
    from shared.services.job_queue import get_job_queue

    queue = get_job_queue()

    try:
        job_id = await queue.create_job(request.model_dump())
        print(f"[QUEUE] Job {job_id[:8]} created")

        yield f"data: {json.dumps({'type': 'job_created', 'jobId': job_id})}\n\n"

        async for event in queue.subscribe_to_job(job_id):
            yield f"data: {json.dumps(event)}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'details': type(e).__name__})}\n\n"


@router.post("/optimize")
async def optimize(request: Request, opt_request: OptimizationRequest):
    """
    Run optimization and stream progress via SSE.

    Execution modes (set via EXECUTION_MODE env var):
    - "local": Run in-process (development)
    - "queue": Use Redis job queue (production)
    """
    if EXECUTION_MODE == "queue":
        stream_func = event_stream_via_queue(opt_request)
    elif EXECUTION_MODE == "direct":
        stream_func = event_stream_direct(opt_request)
    else:
        stream_func = event_stream_local(opt_request)

    return StreamingResponse(
        stream_func,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/optimize/job/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a job. Useful for reconnection."""
    from shared.services.job_queue import get_job_queue

    queue = get_job_queue()
    job = await queue.get_job(job_id)

    if not job:
        return {"error": "Job not found"}

    return {
        "jobId": job.job_id,
        "status": job.status.value,
        "queuePosition": job.queue_position,
        "createdAt": job.created_at,
        "startedAt": job.started_at,
        "completedAt": job.completed_at,
        "error": job.error,
    }


@router.get("/optimize/job/{job_id}/stream")
async def stream_job(job_id: str):
    """
    Reconnect to a job's event stream.
    If the job is complete, returns cached results.
    If still running, streams remaining events.
    """
    from shared.services.job_queue import get_job_queue

    queue = get_job_queue()

    async def stream():
        async for event in queue.subscribe_to_job(job_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/optimize/objectives")
async def get_objectives():
    """Get all available optimization objectives with metadata."""
    objectives = get_all_objectives()

    result = []
    for obj in objectives:
        result.append({
            "key": obj.key,
            "name": obj.name,
            "description": obj.description,
            "category": obj.category,
            "hasParameters": obj.has_parameters,
            "defaultParameters": obj.default_parameters,
            "parameterTypes": {k: v.__name__ if hasattr(v, '__name__') else str(v) for k, v in obj.parameter_types.items()},
            "defaultTier": obj.default_tier,
            "unremovable": obj.unremovable,
        })

    defaults = get_default_objectives()
    default_config = [{"key": key, "parameters": params} for key, params in defaults]

    return {"objectives": result, "defaultConfiguration": default_config}


@router.get("/optimize/constraints")
async def get_hard_constraints():
    """Get all available hard constraints."""
    constraints = get_all_constraints()

    result = []
    for constraint in constraints:
        result.append({
            "key": constraint.key,
            "name": constraint.name,
            "description": constraint.description,
            "category": constraint.category,
            "defaultEnabled": constraint.default_enabled,
        })

    return {"constraints": result}


@router.post("/optimize/course-categories")
async def get_course_categories(request: OptimizationRequest):
    """
    Get which requirement categories each course can satisfy.
    This is used by the frontend to display category tier stars on courses.
    """
    try:
        loop = asyncio.get_event_loop()
        courses_data = await loop.run_in_executor(None, get_courses_data)
        requirements_data = await loop.run_in_executor(None, get_requirements, tuple(request.requirements))
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        planning_year = request.planningYear
        if not planning_year:
            _, planning_year = find_current_school_year()
        planning_year_start = int(planning_year.split('-')[0])

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, planning_year_start, request.maxSemesters, request.markers)

        def build_mappings():
            course_to_requirements: dict[int, set[str]] = {}
            for req_key in request.requirements:
                if req_key in requirements_data:
                    req_data = requirements_data[req_key]
                    if isinstance(req_data, dict):
                        req_tree = parse_fireroad_response({'reqs': req_data.get('reqs', []), 'title': req_key})
                        validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                        if validation.pruned_tree is not None:
                            _, _, mapping = add_requirement_constraints(
                                model, take_vars, validation.pruned_tree,
                                courses_df, req_key, enforce=False
                            )
                            for course_idx, req_paths in mapping.items():
                                if course_idx not in course_to_requirements:
                                    course_to_requirements[course_idx] = set()
                                course_to_requirements[course_idx].update(req_paths)
            return course_to_requirements

        course_to_requirements = await loop.run_in_executor(None, build_mappings)

        result = {}
        for course_idx, req_paths in course_to_requirements.items():
            course_id = courses_df[course_idx, 'subject_id']
            result[course_id] = list(req_paths)

        return result

    except Exception as e:
        return {"error": str(e), "details": type(e).__name__}
