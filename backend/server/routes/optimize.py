import asyncio
import json
import os

import polars as pl
from fastapi import APIRouter
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

USE_WORKERS = os.environ.get("USE_WORKERS", "false").lower() == "true"


@router.get("/optimize/health")
async def health_check():
    return {"status": "healthy", "service": "optimizer"}


async def event_stream_via_worker(request: OptimizationRequest):
    """Stream optimization results via HTTP call to worker (production mode)."""
    from shared.services.worker_client import call_worker_optimize

    try:
        async for line in call_worker_optimize(request.model_dump()):
            yield line
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'details': type(e).__name__})}\n\n"


async def event_stream_local(request: OptimizationRequest):
    """Stream optimization results locally (development mode)."""
    from shared.optimize import event_stream

    try:
        async for line in event_stream(request):
            yield line
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'details': type(e).__name__})}\n\n"


@router.post("/optimize")
async def optimize(request: OptimizationRequest):
    """
    Run optimization and stream progress via SSE.

    In production (USE_WORKERS=true), forwards to Cloud Run workers via HTTP.
    In development (USE_WORKERS=false), runs optimization locally.
    """
    if USE_WORKERS:
        stream_func = event_stream_via_worker(request)
    else:
        stream_func = event_stream_local(request)

    return StreamingResponse(
        stream_func,
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
