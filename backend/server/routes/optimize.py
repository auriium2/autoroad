import asyncio
import json
import logging
import os
import time

import polars as pl
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
from ortools.sat.python import cp_model

from shared.courses.requirements.parser import parse_fireroad_response
from shared.courses.requirements.validator import validate_and_prune
from shared.models.requests import OptimizationRequest
from shared.optimizer.constraints.basic import create_take_vars
from shared.optimizer.constraints.registry import get_all_constraints
from shared.optimizer.objectives.registry import get_all_objectives, get_default_objectives
from shared.optimizer.requirements.builder import add_requirement_constraints
from shared.services.cache import (
    get_courses_data,
    get_parsed_prerequisites_by_index,
    get_requirements,
)
from shared.utils import find_current_school_year

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

# Solver URL - if set, use C++ worker; otherwise solve locally
# In development: leave unset for local solving
# In production (Fly): set to the C++ worker URL
SOLVER_URL = os.environ.get("SOLVER_URL", "")


async def event_stream_local(request: OptimizationRequest):
    """Stream optimization results locally (development mode)."""
    from shared.optimize import event_stream

    try:
        async for line in event_stream(request):
            yield line
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'details': type(e).__name__})}\n\n"


async def event_stream_cpp_worker(request: OptimizationRequest):
    """
    Build CpModel in Python, serialize, and send to C++ worker for solving.

    This mode gives fast cold starts (C++ worker is lightweight) while keeping
    the complex model-building logic in Python.
    """
    import httpx

    from shared.optimize import serialize_model
    from shared.optimizer.constraints.base import ConstraintContext
    from shared.optimizer.constraints.basic import (
        add_basic_constraints,
        add_past_semester_constraints,
        create_take_vars,
    )
    from shared.optimizer.constraints.registry import instantiate_constraint
    from shared.optimizer.marker_constraint_builder import add_marker_constraints
    from shared.optimizer.objectives.builder import ObjectiveBuilder
    from shared.optimizer.objectives.registry import get_default_objectives, instantiate_objective
    from shared.optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
    from shared.optimizer.requirements.builder import add_requirement_constraints
    from shared.services.cache import get_courses_data, get_requirements

    start_time = time.time()
    timings: dict[str, float] = {}

    try:
        logger.info("Starting optimization request: requirements=%s, markers=%d",
                    request.requirements, len(request.markers) if request.markers else 0)

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Initializing...', 'step': 1, 'totalSteps': 10})}\n\n"

        # Fetch data
        t0 = time.time()
        courses_data = await get_courses_data()
        requirements_data = await get_requirements(
            tuple(request.requirements),
            requirement_sources=request.requirementSources
        )
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
        timings["fetch_data"] = time.time() - t0
        logger.info("Fetched %d courses, %d requirements in %.2fs",
                    len(courses_data), len(requirements_data), timings["fetch_data"])

        planning_year = request.planningYear
        if not planning_year:
            _, planning_year = find_current_school_year()
        planning_year_start = int(planning_year.split('-')[0])
        max_semesters = request.maxSemesters

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Creating model...', 'step': 2, 'totalSteps': 10})}\n\n"

        # Create model
        t0 = time.time()
        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, planning_year_start, max_semesters, request.markers)
        add_basic_constraints(model, take_vars, courses_df, max_semesters)

        if request.lockPastSemesters:
            add_past_semester_constraints(model, take_vars, courses_df, planning_year_start, request.markers)
        timings["create_model"] = time.time() - t0
        logger.info("Created model with %d variables in %.2fs", len(take_vars), timings["create_model"])

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding requirements...', 'step': 3, 'totalSteps': 10})}\n\n"

        # Add requirement constraints
        t0 = time.time()
        course_to_requirements: dict[int, set[str]] = {}
        for req_key in request.requirements:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_fireroad_response(req_data)
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        _, _, mapping = add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, req_key, enforce=True
                        )
                        for course_idx, req_paths in mapping.items():
                            if course_idx not in course_to_requirements:
                                course_to_requirements[course_idx] = set()
                            course_to_requirements[course_idx].update(req_paths)
        timings["add_requirements"] = time.time() - t0

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding prerequisites...', 'step': 4, 'totalSteps': 10})}\n\n"

        # Add prerequisite constraints
        t0 = time.time()
        prereq_trees = await get_parsed_prerequisites_by_index(courses_df)
        override_course_ids = {m.courseId for m in request.markers if m.status == 'override'}
        add_prerequisite_constraints(model, take_vars, courses_df, planning_year_start, prereq_trees, override_course_ids)
        timings["add_prerequisites"] = time.time() - t0

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding markers...', 'step': 5, 'totalSteps': 10})}\n\n"

        # Add marker constraints
        t0 = time.time()
        add_marker_constraints(model, take_vars, request.markers, courses_df, planning_year_start)
        timings["add_markers"] = time.time() - t0

        # Add hard constraints
        if request.hardConstraints:
            constraint_context = ConstraintContext(
                planning_year_start=planning_year_start,
                courses_df=courses_df,
                max_semesters=max_semesters,
                markers=request.markers,
            )
            for constraint_key in request.hardConstraints:
                try:
                    constraint = instantiate_constraint(constraint_key)
                    constraint.add_to_model(model, take_vars, constraint_context)
                except ValueError:
                    pass

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Building objective...', 'step': 6, 'totalSteps': 10})}\n\n"

        # Build objective
        t0 = time.time()
        builder = ObjectiveBuilder()

        from shared.optimizer.objectives.units import MinimizeUnits
        builder.add(MinimizeUnits(), key="minimize_units")

        if request.objectives:
            for obj_config in request.objectives:
                try:
                    obj = instantiate_objective(obj_config.key, obj_config.parameters)
                    builder.add(obj, key=obj_config.key)
                except ValueError:
                    pass
        else:
            for key, params in get_default_objectives():
                obj = instantiate_objective(key, params)
                builder.add(obj, key=key)

        marked_course_ids = {m.courseId for m in request.markers} if request.markers else set()

        objective = builder.build(
            model, take_vars, courses_df, planning_year_start,
            objective_tiers=request.objectiveTiers,
            requirement_tiers=request.requirementTiers,
            marked_course_ids=marked_course_ids,
            course_to_requirements=course_to_requirements
        )
        model.Minimize(objective)
        timings["build_objective"] = time.time() - t0

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Serializing model...', 'step': 7, 'totalSteps': 10})}\n\n"

        t0 = time.time()
        num_workers = int(os.environ.get("CPSAT_NUM_WORKERS", "8"))
        serialized = serialize_model(model, take_vars, courses_df, builder, max_time_seconds=20.0, num_workers=num_workers)
        timings["serialize"] = time.time() - t0

        model_size_kb = len(serialized.to_json()) / 1024
        logger.info("Model built: %d vars, %.1f KB payload, serialized in %.2fs",
                    len(take_vars), model_size_kb, timings["serialize"])

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Connecting to solver...', 'step': 8, 'totalSteps': 10, 'waiting': True})}\n\n"

        # Send to C++ worker and stream results
        worker_secret = os.getenv("WORKER_SECRET", "")
        t0 = time.time()
        logger.info("Connecting to C++ worker at %s", SOLVER_URL)

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            async with client.stream(
                "POST",
                f"{SOLVER_URL}/solve",
                content=serialized.to_json(),
                headers={"Content-Type": "application/json", "Connection": "close", "X-Worker-Secret": worker_secret}
            ) as response:
                timings["worker_connect"] = time.time() - t0
                logger.info("Worker connected in %.2fs, status=%d", timings["worker_connect"], response.status_code)

                if response.status_code != 200:
                    logger.error("Worker returned error status %d", response.status_code)
                    yield f"data: {json.dumps({'type': 'error', 'error': f'Solver returned {response.status_code}'})}\n\n"
                    return

                solution_count = 0
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield f"{line}\n\n"
                        # Count solutions for logging
                        try:
                            event = json.loads(line[6:])
                            if event.get("type") == "solution":
                                solution_count += 1
                            elif event.get("type") == "complete":
                                timings["solve"] = time.time() - t0 - timings["worker_connect"]
                                total_time = time.time() - start_time
                                logger.info(
                                    "Optimization complete: status=%s, solutions=%d, "
                                    "solve_time=%.2fs, total_time=%.2fs, timings=%s",
                                    event.get("status"), solution_count,
                                    timings.get("solve", 0), total_time, timings
                                )
                        except json.JSONDecodeError:
                            pass

    except httpx.ConnectError as e:
        logger.error("Failed to connect to C++ worker: %s", e)
        yield f"data: {json.dumps({'type': 'error', 'error': 'Failed to connect to solver', 'details': str(e)})}\n\n"
    except Exception as e:
        logger.exception("Optimization error: %s", e)
        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'details': type(e).__name__})}\n\n"


@router.post("/optimize")
@limiter.limit("10/minute")
async def optimize(request: Request, opt_request: OptimizationRequest):
    """
    Run optimization and stream progress via SSE.

    If SOLVER_URL is set, builds model locally and sends to C++ worker.
    Otherwise, runs the full optimization in-process (development mode).
    """
    if SOLVER_URL:
        stream_func = event_stream_cpp_worker(opt_request)
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
        courses_data = await get_courses_data()
        requirements_data = await get_requirements(tuple(request.requirements))
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

        loop = asyncio.get_event_loop()
        course_to_requirements = await loop.run_in_executor(None, build_mappings)

        result = {}
        for course_idx, req_paths in course_to_requirements.items():
            course_id = courses_df[course_idx, 'subject_id']
            result[course_id] = list(req_paths)

        return result

    except Exception as e:
        return {"error": str(e), "details": type(e).__name__}
