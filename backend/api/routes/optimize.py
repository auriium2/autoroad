import asyncio
import json
import os
import queue
import threading
import time
from ctypes import c_double, c_int
from multiprocessing import Value
from threading import RLock

import polars as pl
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ortools.sat.python import cp_model

from api.models.requests import OptimizationRequest
from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
from courses.prerequisites.types import PrereqNode
from courses.requirements.parser import parse_fireroad_response
from courses.requirements.validator import validate_and_prune
from optimizer.constraints import ConstraintContext
from optimizer.constraints.basic import (
    add_basic_constraints,
    add_past_semester_constraints,
    create_take_vars,
)
from optimizer.constraints.registry import (
    get_all_constraints,
    instantiate_constraint,
)
from optimizer.marker_constraint_builder import add_marker_constraints
from optimizer.objectives import ObjectiveBuilder
from optimizer.objectives.registry import (
    get_all_objectives,
    get_default_objectives,
    instantiate_objective,
)
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirements.builder import add_requirement_constraints
from utils.utils import find_current_school_year

router = APIRouter()

# BENCHMARK: Set to False to disable multi-threading for performance comparison
ENABLE_MULTITHREADING = True


@router.get("/optimize/health")
async def health_check():
    """
    Health check endpoint for the optimizer service.

    Returns:
        Status of the optimizer service
    """
    return {
        "status": "healthy",
        "service": "optimizer"
    }


class StreamingCallback(cp_model.CpSolverSolutionCallback):
    """
    Thread-safe CP-SAT callback for multi-threaded solving.
    Multiple solver threads can invoke this callback concurrently.
    Uses atomic operations and minimal locking for best performance.
    """

    def __init__(
        self,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        courses_df: pl.DataFrame,
        solution_queue: queue.Queue[object],
        builder: ObjectiveBuilder | None = None,
        model: cp_model.CpModel | None = None,
        planning_year_start: int | None = None,
        objective_tiers: dict[str, int] | None = None,
        requirement_tiers: dict[str, int] | None = None,
        marked_course_ids: set[str] | None = None
    ):
        super().__init__()
        self.take_vars: dict[tuple[int, int], cp_model.IntVar] = take_vars
        self.courses_df: pl.DataFrame = courses_df
        self.solution_queue: queue.Queue[object] = solution_queue

        # Atomic counter for solution numbering (thread-safe increment)
        self._solution_count = Value(c_int, 0)

        # Best solution tracking (only lock when updating best)
        self._best_lock = RLock()
        self._best_objective_value = Value(c_double, float('inf'))
        self._best_solution_nodes: list[dict[str, object]] = []

        # For cost breakdown calculation
        self.builder = builder
        self.model = model
        self.planning_year_start = planning_year_start
        self.objective_tiers = objective_tiers
        self.requirement_tiers = requirement_tiers
        self.marked_course_ids = marked_course_ids

    @property
    def solution_count(self) -> int:
        return self._solution_count.value

    @property
    def best_solution_nodes(self) -> list[dict[str, object]]:
        with self._best_lock:
            return self._best_solution_nodes.copy()

    @property
    def best_objective_value(self) -> float | None:
        val = self._best_objective_value.value
        return None if val == float('inf') else val

    def on_solution_callback(self) -> None:
        # Extract solution data (thread-local, no sync needed)
        nodes = []
        for (course_idx, semester), var in self.take_vars.items():
            if self.Value(var) != 0:
                course_id = self.courses_df[course_idx, 'subject_id']
                title = self.courses_df[course_idx, 'title'] if 'title' in self.courses_df.columns else None

                # Convert semester to section for frontend
                if semester < 0:
                    section = semester
                else:
                    section = semester - 1

                units = self.courses_df[course_idx, 'total_units'] if 'total_units' in self.courses_df.columns else 12

                nodes.append({
                    "courseId": course_id,
                    "section": section,
                    "title": title,
                    "units": units
                })

        current_objective = self.ObjectiveValue()

        # Calculate cost breakdown if builder is available
        cost_breakdown = None
        if self.builder:
            try:
                cost_breakdown = self.builder.calculate_cost_breakdown(self)
            except Exception as e:
                print(f"[WARNING] Failed to calculate cost breakdown: {e}")

        # Atomic increment for solution number
        with self._solution_count.get_lock():
            self._solution_count.value += 1
            solution_num = self._solution_count.value

        # Update best solution only if this is better (minimize contention)
        if current_objective < self._best_objective_value.value:
            with self._best_lock:
                # Double-check after acquiring lock
                if current_objective < self._best_objective_value.value:
                    self._best_objective_value.value = current_objective
                    self._best_solution_nodes = nodes
                    print(f"[SSE] Callback: New best solution #{solution_num} with objective={current_objective}")

        solution = {
            "type": "solution",
            "step": solution_num,
            "solutionNumber": solution_num,
            "nodes": nodes,
            "objectiveValue": current_objective,
            "costBreakdown": cost_breakdown
        }

        # Queue.put is thread-safe by default
        self.solution_queue.put(solution)
        print(f"[SSE] Callback: Solution {solution_num} queued with objective={current_objective}, {len(nodes)} courses")


def parse_prerequisites_for_all_courses(courses_df: pl.DataFrame) -> dict[int, PrereqNode]:
    """
    Parse prerequisites for all courses (with caching).

    DEPRECATED: Use get_parsed_prerequisites() from cache module directly.
    This wrapper exists for backwards compatibility.
    """
    return get_parsed_prerequisites(courses_df)


@router.post("/optimize")
async def optimize(request: OptimizationRequest):
    """
    Run optimization and stream progress via SSE.

    Returns:
        SSE stream with messages:
        - progress: Status updates
        - solution: New solution found
        - complete: Optimization finished
        - error: Error occurred
    """

    async def event_stream():
        try:
            # Performance tracking
            perf_timings: dict[str, float] = {}
            perf_start_total = time.time()

            # Send initial progress
            msg = {'type': 'progress', 'message': 'Initializing...', 'step': 1, 'totalSteps': 10}
            print(f"[SSE] Sending: {msg}")
            yield f"data: {json.dumps(msg)}\n\n"

            # Get data (run in thread pool to not block)
            perf_start = time.time()
            loop = asyncio.get_event_loop()
            print("[SSE] Fetching courses and requirements...")
            courses_data = await loop.run_in_executor(None, get_courses_data)
            requirements_data = await loop.run_in_executor(None, get_requirements, tuple(request.requirements))
            # Use infer_schema_length=None to ensure all columns are detected
            courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
            perf_timings['data_fetch'] = time.time() - perf_start
            print(f"[SSE] Loaded {len(courses_df)} courses in {perf_timings['data_fetch']:.3f}s")

            # Get planning year
            planning_year = request.planningYear
            if not planning_year:
                _, planning_year = find_current_school_year()
            planning_year_start = int(planning_year.split('-')[0])

            # Extract configuration
            max_semesters = request.maxSemesters

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Creating model...', 'step': 2, 'totalSteps': 10})}\n\n"

            # Create model (run in thread pool)
            perf_start = time.time()
            def create_model():
                model = cp_model.CpModel()
                take_vars = create_take_vars(model, courses_df, planning_year_start, max_semesters, request.markers)
                add_basic_constraints(model, take_vars, courses_df, max_semesters)

                # Add past semester constraints if enabled
                if request.lockPastSemesters:
                    add_past_semester_constraints(model, take_vars, courses_df, planning_year_start, request.markers)

                # Log decision variable stats
                unique_courses = len(set(course_idx for course_idx, _ in take_vars.keys()))
                print(f"[STATS] Created {len(take_vars)} decision variables for {unique_courses} courses out of {len(courses_df)} total")

                return model, take_vars

            model, take_vars = await loop.run_in_executor(None, create_model)
            perf_timings['model_creation'] = time.time() - perf_start
            print(f"[PERF] Model creation: {perf_timings['model_creation']:.3f}s")

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding requirements...', 'step': 3, 'totalSteps': 10})}\n\n"

            # Add requirement constraints (run in thread pool)
            perf_start = time.time()
            course_to_requirements = {}
            def add_requirements():
                nonlocal course_to_requirements
                # Collect course-to-requirement mappings from all requirements
                all_mappings = []
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
                                all_mappings.append(mapping)

                # Merge all mappings into a single dict
                for mapping in all_mappings:
                    for course_idx, req_paths in mapping.items():
                        if course_idx not in course_to_requirements:
                            course_to_requirements[course_idx] = set()
                        course_to_requirements[course_idx].update(req_paths)

            await loop.run_in_executor(None, add_requirements)
            perf_timings['requirements'] = time.time() - perf_start
            print(f"[PERF] Requirements: {perf_timings['requirements']:.3f}s")

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding prerequisites...', 'step': 4, 'totalSteps': 10})}\n\n"

            # Add prerequisite constraints (run in thread pool)
            perf_start = time.time()
            def add_prereqs():
                # Parse prerequisites
                prereq_parse_start = time.time()
                prereq_trees = get_parsed_prerequisites(courses_df)
                prereq_parse_time = time.time() - prereq_parse_start

                # Get override marker course IDs to skip prerequisite enforcement
                override_course_ids = set()
                for m in request.markers:
                    if m.status == 'override':
                        override_course_ids.add(m.courseId)

                # Log prereq stats
                courses_with_vars = set(course_idx for course_idx, _ in take_vars.keys())
                relevant_prereq_courses = len([idx for idx in prereq_trees.keys() if idx in courses_with_vars])
                print(f"[STATS] {len(prereq_trees)} courses have prereqs, {relevant_prereq_courses} have decision variables")

                # Add constraints to model
                constraint_start = time.time()
                result, builder = add_prerequisite_constraints(model, take_vars, courses_df, planning_year_start, prereq_trees, override_course_ids)
                constraint_time = time.time() - constraint_start

                # Log detailed cache and variable stats
                prereq_cache_size = len(builder._prereq_taken_before_cache)
                gir_cache_size = len(builder._gir_taken_before_cache)
                hass_cache_size = len(builder._hass_taken_before_cache)
                total_vars_created = builder.ctx._counter

                print(f"[PERF]   - Prereq parsing:           {prereq_parse_time:.3f}s")
                print(f"[PERF]   - Prereq constraint build:  {constraint_time:.3f}s")
                print(f"[STATS]  - Constraints added:        {result.constraints_added}")
                print(f"[STATS]  - Variables created:        {total_vars_created}")
                print(f"[STATS]  - Prereq cache size:        {prereq_cache_size}")
                print(f"[STATS]  - GIR cache size:           {gir_cache_size}")
                print(f"[STATS]  - HASS cache size:          {hass_cache_size}")
                print(f"[STATS]  - Warnings:                 {len(result.warnings)}")
                if result.warnings[:5]:
                    for w in result.warnings[:5]:
                        print(f"[WARN]     {w}")

            await loop.run_in_executor(None, add_prereqs)
            perf_timings['prerequisites'] = time.time() - perf_start
            print(f"[PERF] Prerequisites TOTAL: {perf_timings['prerequisites']:.3f}s")

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding markers...', 'step': 5, 'totalSteps': 10})}\n\n"

            # Add marker constraints (run in thread pool)
            perf_start = time.time()
            def add_markers():
                return add_marker_constraints(model, take_vars, request.markers, courses_df, planning_year_start)

            marker_result = await loop.run_in_executor(None, add_markers)
            perf_timings['markers'] = time.time() - perf_start
            print(f"[PERF] Markers: {perf_timings['markers']:.3f}s")

            # Add hard constraints (run in thread pool)
            perf_start = time.time()
            def add_hard_constraints():
                if request.hardConstraints:
                    constraint_context = ConstraintContext(
                        planning_year_start=planning_year_start,
                        courses_df=courses_df,
                        max_semesters=max_semesters,
                        markers=request.markers,
                    )

                    print(f"[OPTIMIZER] Applying {len(request.hardConstraints)} hard constraints:")
                    for constraint_key in request.hardConstraints:
                        try:
                            constraint = instantiate_constraint(constraint_key)
                            constraint.add_to_model(model, take_vars, constraint_context)
                            print(f"  - {constraint_key}: {constraint.get_name()}")
                        except ValueError as e:
                            print(f"[WARNING] Invalid constraint {constraint_key}: {e}")

            await loop.run_in_executor(None, add_hard_constraints)
            perf_timings['hard_constraints'] = time.time() - perf_start
            print(f"[PERF] Hard constraints: {perf_timings['hard_constraints']:.3f}s")

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Building objective...', 'step': 6, 'totalSteps': 10})}\n\n"

            # Build objective (run in thread pool)
            perf_start = time.time()
            def build_objective():
                builder = ObjectiveBuilder()

                # Always add minimize_units as the core base objective
                from optimizer.objectives import MinimizeUnits
                builder.add(MinimizeUnits(), key="minimize_units")

                # Use provided objectives or defaults
                if request.objectives:
                    # Use user-provided objectives
                    print(f"[OPTIMIZER] Using {len(request.objectives)} user-provided objectives:")
                    for obj_config in request.objectives:
                        try:
                            obj = instantiate_objective(obj_config.key, obj_config.parameters)
                            builder.add(obj, key=obj_config.key)
                            print(f"  - {obj_config.key}: {obj_config.parameters}")
                        except ValueError as e:
                            print(f"[WARNING] Invalid objective {obj_config.key}: {e}")
                else:
                    # Use default objectives
                    print("[OPTIMIZER] Using default objectives")
                    for key, params in get_default_objectives():
                        obj = instantiate_objective(key, params)
                        builder.add(obj, key=key)
                        print(f"  - {key}: {params}")

                # Extract marked course IDs from markers
                marked_course_ids = set(m.courseId for m in request.markers) if request.markers else set()

                print(f"[OPTIMIZER] Objective tiers: {request.objectiveTiers}")
                print(f"[OPTIMIZER] Requirement tiers: {request.requirementTiers}")
                print(f"[OPTIMIZER] Marked courses: {marked_course_ids}")
                print(f"[OPTIMIZER] Course-to-requirements mapping: {len(course_to_requirements)} courses mapped")
                if course_to_requirements:
                    # Show a sample
                    sample = list(course_to_requirements.items())[:3]
                    for course_idx, paths in sample:
                        course_id = courses_df[course_idx, 'subject_id']
                        print(f"  - {course_id} -> {len(paths)} requirement paths")

                objective = builder.build(
                    model,
                    take_vars,
                    courses_df,
                    planning_year_start,
                    objective_tiers=request.objectiveTiers,
                    requirement_tiers=request.requirementTiers,
                    marked_course_ids=marked_course_ids,
                    course_to_requirements=course_to_requirements
                )
                model.Minimize(objective)
                return builder

            builder = await loop.run_in_executor(None, build_objective)
            perf_timings['objective_building'] = time.time() - perf_start
            print(f"[PERF] Objective building: {perf_timings['objective_building']:.3f}s")

            msg = {'type': 'progress', 'message': 'Solving...', 'step': 7, 'totalSteps': 10}
            print(f"[SSE] Sending: {msg}")
            yield f"data: {json.dumps(msg)}\n\n"

            # Create queue for solutions
            solution_queue = queue.Queue()

            # Extract marked course IDs from markers
            marked_course_ids = set(m.courseId for m in request.markers) if request.markers else set()

            # Create callback with builder for cost breakdown
            callback = StreamingCallback(
                take_vars,
                courses_df,
                solution_queue,
                builder=builder,
                model=model,
                planning_year_start=planning_year_start,
                objective_tiers=request.objectiveTiers,
                requirement_tiers=request.requirementTiers,
                marked_course_ids=marked_course_ids
            )

            # Configure solver
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 20
            #solver.parameters.relative_gap_limit = 0.05  # this is a hack, but it makes things a lil faster




            # Multi-threading configuration
            # NOTE: enumerate_all_solutions is incompatible with multi-threading
            # Multi-threading finds one good solution fast, enumeration finds all solutions slowly
            if ENABLE_MULTITHREADING:
                # Multi-threaded mode: find best solution quickly using parallel workers
                solver.parameters.enumerate_all_solutions = False
                num_workers = int(os.getenv("CPSAT_NUM_WORKERS", "0"))  # 0 = auto-detect (uses all cores)
                solver.parameters.num_search_workers = num_workers
                print(f"[SSE] Multi-threading ENABLED: {num_workers} workers, enumerate=False")
            else:
                # Single-threaded enumeration mode (finds multiple diverse solutions)
                solver.parameters.enumerate_all_solutions = False
                solver.parameters.num_search_workers = 1
                print("[SSE] Multi-threading DISABLED: single worker, enumerate=True")

            # Run solver in thread pool (non-blocking)
            print("[SSE] Starting solver...")
            solver_done = threading.Event()
            result = cp_model.MODEL_INVALID  # Initialize with default value
            solve_start_time = time.time()

            def run_solver():
                nonlocal result
                result = solver.Solve(model, callback)
                solve_time = time.time() - solve_start_time
                solution_queue.put({
                    '__done__': True,
                    'result': result,
                    'count': callback.solution_count,
                    'solve_time': solve_time
                })
                solver_done.set()

            solver_thread = threading.Thread(target=run_solver)
            solver_thread.start()

            # Stream solutions as they arrive in the queue
            solve_time_seconds = None
            while not solver_done.is_set() or not solution_queue.empty():
                try:
                    solution = solution_queue.get(timeout=0.1)

                    # Check for completion signal
                    if '__done__' in solution:
                        result = solution['result']
                        solve_time_seconds = solution['solve_time']
                        print(f"[SSE] Solver finished with status: {result}, found {solution['count']} solutions in {solve_time_seconds:.2f}s")
                        break

                    # Stream the solution
                    print(f"[SSE] Streaming solution {solution['step']}")
                    yield f"data: {json.dumps(solution)}\n\n"

                except queue.Empty:
                    # No solution yet, yield control
                    await asyncio.sleep(0.05)

            # Make sure solver thread completes
            solver_thread.join()

            # Calculate total time
            perf_timings['solving'] = solve_time_seconds if solve_time_seconds is not None else 0.0
            perf_timings['total'] = time.time() - perf_start_total

            # Print performance summary
            print("\n" + "="*60)
            print("PERFORMANCE SUMMARY")
            print("="*60)
            print(f"Data fetch:          {perf_timings['data_fetch']:>8.3f}s  ({perf_timings['data_fetch']/perf_timings['total']*100:>5.1f}%)")
            print(f"Model creation:      {perf_timings['model_creation']:>8.3f}s  ({perf_timings['model_creation']/perf_timings['total']*100:>5.1f}%)")
            print(f"Requirements:        {perf_timings['requirements']:>8.3f}s  ({perf_timings['requirements']/perf_timings['total']*100:>5.1f}%)")
            print(f"Prerequisites:       {perf_timings['prerequisites']:>8.3f}s  ({perf_timings['prerequisites']/perf_timings['total']*100:>5.1f}%)")
            print(f"Markers:             {perf_timings['markers']:>8.3f}s  ({perf_timings['markers']/perf_timings['total']*100:>5.1f}%)")
            print(f"Hard constraints:    {perf_timings['hard_constraints']:>8.3f}s  ({perf_timings['hard_constraints']/perf_timings['total']*100:>5.1f}%)")
            print(f"Objective building:  {perf_timings['objective_building']:>8.3f}s  ({perf_timings['objective_building']/perf_timings['total']*100:>5.1f}%)")
            print(f"Solving:             {perf_timings['solving']:>8.3f}s  ({perf_timings['solving']/perf_timings['total']*100:>5.1f}%)")
            print("-"*60)
            print(f"TOTAL:               {perf_timings['total']:>8.3f}s")
            print("="*60 + "\n")

            # Export to .road file for debugging
            if result in [cp_model.OPTIMAL, cp_model.FEASIBLE] and callback.best_solution_nodes:
                from pathlib import Path

                road_data = {
                    "coursesOfStudy": [],
                    "progressAssertions": {},
                    "selectedSubjects": [
                        {
                            "subject_id": node["courseId"],
                            "semester": int(node["section"]) + 1 if isinstance(node["section"], int) else 1,  # Convert back to 1-indexed
                            "title": node.get("title", ""),
                            "units": 12,
                            "overrideWarnings": False
                        }
                        for node in callback.best_solution_nodes
                    ]
                }

                output_path = Path("optimization_result.road")
                with open(output_path, "w") as f:
                    json.dump(road_data, f, indent=2)
                print(f"[SSE] Exported best solution (objective={callback.best_objective_value}) to {output_path}")

            # Send completion
            status_map = {
                cp_model.OPTIMAL: "OPTIMAL",
                cp_model.FEASIBLE: "FEASIBLE",
                cp_model.INFEASIBLE: "INFEASIBLE",
                cp_model.MODEL_INVALID: "MODEL_INVALID"
            }

            warnings = []
            if result == cp_model.FEASIBLE:
                warnings.append("Solution found but may not be optimal (time limit reached)")
            elif result == cp_model.INFEASIBLE:
                warnings.append("No feasible solution found - constraints may be too strict")
                if marker_result.errors:
                    warnings.extend(marker_result.errors[:3])

            completion_msg = {
                'type': 'complete',
                'status': status_map.get(result, 'MODEL_INVALID'),
                'solutionCount': callback.solution_count,
                'warnings': warnings,
                'solveTimeSeconds': solve_time_seconds,
                'multithreaded': ENABLE_MULTITHREADING,
                'performanceTimings': perf_timings
            }
            yield f"data: {json.dumps(completion_msg)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'details': type(e).__name__})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/optimize/objectives")
async def get_objectives():
    """
    Get all available optimization objectives with metadata.

    Returns:
        List of objectives with their keys, names, descriptions, parameters, etc.
    """
    objectives = get_all_objectives()

    # Convert to dict format for JSON response
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

    # Also include default configuration
    defaults = get_default_objectives()
    default_config = [
        {"key": key, "parameters": params}
        for key, params in defaults
    ]

    return {
        "objectives": result,
        "defaultConfiguration": default_config
    }



@router.get("/optimize/constraints")
async def get_hard_constraints():
    """
    Get all available hard constraints.

    Returns:
        List of hard constraint metadata with keys, names, descriptions.
    """
    constraints = get_all_constraints()

    # Convert to dict format for JSON response
    result = []
    for constraint in constraints:
        result.append({
            "key": constraint.key,
            "name": constraint.name,
            "description": constraint.description,
            "category": constraint.category,
            "defaultEnabled": constraint.default_enabled,
        })

    return {
        "constraints": result
    }


@router.post("/optimize/course-categories")
async def get_course_categories(request: OptimizationRequest):
    """
    Get which requirement categories each course can satisfy.

    This is used by the frontend to display category tier stars on courses.

    Returns:
        Dictionary mapping course IDs to lists of requirement paths they satisfy
    """
    try:
        # Get data
        loop = asyncio.get_event_loop()
        courses_data = await loop.run_in_executor(None, get_courses_data)
        requirements_data = await loop.run_in_executor(None, get_requirements, tuple(request.requirements))
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        # Get planning year
        planning_year = request.planningYear
        if not planning_year:
            _, planning_year = find_current_school_year()
        planning_year_start = int(planning_year.split('-')[0])

        # Create a minimal model just to build requirement constraints
        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, planning_year_start, request.maxSemesters, request.markers)

        # Build requirement constraints to get course-to-requirement mapping
        def build_mappings():
            course_to_requirements = {}
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
                            # Merge this mapping into the combined dict
                            for course_idx, req_paths in mapping.items():
                                if course_idx not in course_to_requirements:
                                    course_to_requirements[course_idx] = set()
                                course_to_requirements[course_idx].update(req_paths)
            return course_to_requirements

        course_to_requirements = await loop.run_in_executor(None, build_mappings)

        # Convert to course ID -> requirement paths
        result = {}
        for course_idx, req_paths in course_to_requirements.items():
            course_id = courses_df[course_idx, 'subject_id']
            result[course_id] = list(req_paths)

        return result

    except Exception as e:
        return {"error": str(e), "details": type(e).__name__}
