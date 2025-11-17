import asyncio
import json
import queue
import threading
from collections.abc import Sequence

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ortools.sat.python import cp_model

from api.models.requests import Marker, OptimizationRequest
from api.services.cache import get_courses_data, get_requirements
from courses.prerequisites.parser import parse_fireroad
from courses.prerequisites.types import PrereqNode
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.marker_constraint_builder import add_marker_constraints
from optimizer.objectives import ObjectiveBuilder
from optimizer.objectives.registry import (
    get_all_objectives,
    get_default_objectives,
    instantiate_objective,
)
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints
from utils.utils import find_current_school_year, is_valid_class_semester

router = APIRouter()


class StreamingCallback(cp_model.CpSolverSolutionCallback):
    """
    CP-SAT callback that puts solutions into a queue for real-time streaming.
    """

    def __init__(self, take_vars: dict[tuple[int, int], cp_model.IntVar], courses_df: pd.DataFrame, solution_queue: queue.Queue[object]):
        super().__init__()
        self.take_vars: dict[tuple[int, int], cp_model.IntVar] = take_vars
        self.courses_df: pd.DataFrame = courses_df
        self.solution_count: int = 0
        self.solution_queue: queue.Queue[object] = solution_queue
        self.best_solution_nodes: list[dict[str, object]] = []  # Track best solution for .road export
        self.best_objective_value: float | None = None

    def on_solution_callback(self) -> None:
        self.solution_count += 1
        nodes = []

        for (course_idx, semester), var in self.take_vars.items():
            if self.Value(var) != 0:
                course_id = self.courses_df.at[course_idx, 'subject_id']
                title = self.courses_df.at[course_idx, 'title'] if 'title' in self.courses_df.columns else None

                # Convert semester to section for frontend
                # Special semesters (-2, -1) stay as-is, regular semesters (1-12) become 0-based (0-11)
                if semester < 0:
                    section = semester  # Keep special semesters as-is
                else:
                    section = semester - 1  # Convert regular semesters to 0-based

                nodes.append({
                    "courseId": course_id,
                    "section": section,
                    "title": title
                })

        current_objective = self.ObjectiveValue()

        # Track best solution for .road export (lower objective = better)
        if self.best_objective_value is None or current_objective < self.best_objective_value:
            self.best_objective_value = current_objective
            self.best_solution_nodes = nodes
            print(f"[SSE] Callback: New best solution #{self.solution_count} with objective={current_objective}")

        solution = {
            "type": "solution",
            "step": self.solution_count,
            "solutionNumber": self.solution_count,  # Explicit sequence number for ordering
            "nodes": nodes,
            "objectiveValue": current_objective
        }

        # Put solution in queue immediately (thread-safe)
        self.solution_queue.put(solution)
        print(f"[SSE] Callback: Solution {self.solution_count} queued with objective={current_objective}, {len(nodes)} courses")
        # Debug: print first 5 courses with their sections
        for node in nodes[:5]:
            print(f"  - {node['courseId']} @ section {node['section']}")


def create_take_vars(model: cp_model.CpModel, courses_df: pd.DataFrame, planning_year_start: int, max_semesters: int, markers: Sequence[Marker] | None = None) -> dict[tuple[int, int], cp_model.IntVar]:
    """Create decision variables for taking courses."""
    take_vars = {}

    # Build a set of course_ids for ASE markers only
    # Must Take (section=-2) is handled as a requirement constraint, not a placement
    # ASE (section=-1) creates a special semester variable
    ase_courses = set()
    if markers:
        print(f"[DEBUG] Processing {len(markers)} markers")
        for marker in markers:
            print(f"[DEBUG] Marker: {marker.courseId} section={marker.section} status={marker.status}")
            if marker.section == -1:  # ASE
                ase_courses.add(marker.courseId)
                print(f"[DEBUG] Added {marker.courseId} to ASE semester -1")

    for course_idx in courses_df.index:
        subject_id = courses_df.at[course_idx, 'subject_id']

        # For regular semesters (1 to max_semesters)
        for semester in range(1, max_semesters + 1):
            if is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
                var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
                take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)

        # For ASE semester, only create var if there's an ASE marker
        if subject_id in ase_courses:
            var_name = f"take_{subject_id.replace('.', '_')}_s-1"
            take_vars[(course_idx, -1)] = model.NewBoolVar(var_name)

    return take_vars


def add_basic_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pd.DataFrame,
    max_units_per_semester: int,
    max_units_iap: int,
    max_semesters: int
) -> None:
    """Add basic constraints like max units per semester, taking course once, etc."""

    # Constraint: Take each course at most once in regular semesters
    # Note: Special semesters (-2, -1) are only used via markers, optimizer can't place there
    # A course in Must Take/ASE can be retaken in regular semesters if needed
    for course_idx in courses_df.index:
        regular_semester_takes = [
            take_vars[(course_idx, s)]
            for s in range(1, max_semesters + 1)
            if (course_idx, s) in take_vars
        ]
        if regular_semester_takes:
            model.Add(sum(regular_semester_takes) <= 1)

    # Constraint: Max units per semester
    for semester in range(1, max_semesters + 1):
        # Determine max units for this semester
        is_iap = (semester - 2) % 3 == 0 and semester >= 2 and semester <= 11
        max_units = max_units_iap if is_iap else max_units_per_semester

        semester_takes = [
            take_vars[(c, semester)] * courses_df.at[c, 'total_units']
            for c in courses_df.index
            if (c, semester) in take_vars and 'total_units' in courses_df.columns and pd.notna(courses_df.at[c, 'total_units'])
        ]
        if semester_takes:
            model.Add(sum(semester_takes) <= max_units)


def parse_prerequisites_for_all_courses(courses_df: pd.DataFrame) -> dict[int, PrereqNode]:
    """Parse prerequisites for all courses."""
    prereq_trees: dict[int, PrereqNode] = {}

    for course_idx in courses_df.index:
        prereq_str = courses_df.at[course_idx, 'prerequisites']

        if pd.notna(prereq_str) and prereq_str:
            try:
                prereq_tree = parse_fireroad(prereq_str)
                if prereq_tree is not None:
                    prereq_trees[course_idx] = prereq_tree
            except Exception:
                pass

    return prereq_trees


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
            # Send initial progress
            msg = {'type': 'progress', 'message': 'Initializing...', 'step': 1, 'totalSteps': 10}
            print(f"[SSE] Sending: {msg}")
            yield f"data: {json.dumps(msg)}\n\n"

            # Get data (run in thread pool to not block)
            loop = asyncio.get_event_loop()
            print("[SSE] Fetching courses and requirements...")
            courses_data = await loop.run_in_executor(None, get_courses_data)
            requirements_data = await loop.run_in_executor(None, get_requirements, tuple(request.requirements))
            courses_df = pd.DataFrame(courses_data)
            print(f"[SSE] Loaded {len(courses_df)} courses")

            # Get planning year
            planning_year = request.planningYear
            if not planning_year:
                _, planning_year = find_current_school_year()
            planning_year_start = int(planning_year.split('-')[0])

            # Extract constraints
            max_semesters = request.constraints.maxSemesters
            max_units_per_semester = request.constraints.maxUnitsPerSemester
            max_units_iap = request.constraints.maxUnitsIAP

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Creating model...', 'step': 2, 'totalSteps': 10})}\n\n"

            # Create model (run in thread pool)
            def create_model():
                model = cp_model.CpModel()
                take_vars = create_take_vars(model, courses_df, planning_year_start, max_semesters, request.markers)
                add_basic_constraints(model, take_vars, courses_df, max_units_per_semester, max_units_iap, max_semesters)
                return model, take_vars

            model, take_vars = await loop.run_in_executor(None, create_model)

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding requirements...', 'step': 3, 'totalSteps': 10})}\n\n"

            # Add requirement constraints (run in thread pool)
            def add_requirements():
                for req_key in request.requirements:
                    if req_key in requirements_data:
                        req_data = requirements_data[req_key]
                        if isinstance(req_data, dict):
                            req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                            if req_tree is not None:
                                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                                if validation.pruned_tree is not None:
                                    add_requirement_constraints(
                                        model, take_vars, validation.pruned_tree,
                                        courses_df, planning_year_start, enforce=True
                                    )

            await loop.run_in_executor(None, add_requirements)

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding prerequisites...', 'step': 4, 'totalSteps': 10})}\n\n"

            # Add prerequisite constraints (run in thread pool)
            def add_prereqs():
                prereq_trees = parse_prerequisites_for_all_courses(courses_df)
                # Get override marker course IDs to skip prerequisite enforcement
                override_course_ids = set()
                for m in request.markers:
                    if m.status == 'override':
                        override_course_ids.add(m.courseId)
                add_prerequisite_constraints(model, take_vars, courses_df, planning_year_start, prereq_trees, override_course_ids)

            await loop.run_in_executor(None, add_prereqs)

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Adding markers...', 'step': 5, 'totalSteps': 10})}\n\n"

            # Add marker constraints (run in thread pool)
            def add_markers():
                return add_marker_constraints(model, take_vars, request.markers, courses_df, planning_year_start)

            marker_result = await loop.run_in_executor(None, add_markers)

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Building objective...', 'step': 6, 'totalSteps': 10})}\n\n"

            # Build objective (run in thread pool)
            def build_objective():
                builder = ObjectiveBuilder()

                # Use provided objectives or defaults
                if request.objectives:
                    # Use user-provided objectives
                    for obj_config in request.objectives:
                        try:
                            obj = instantiate_objective(obj_config.key, obj_config.parameters)
                            builder.add(obj, weight=obj_config.weight)
                        except ValueError as e:
                            print(f"[WARNING] Invalid objective {obj_config.key}: {e}")
                else:
                    # Use default objectives
                    for key, weight, params in get_default_objectives():
                        obj = instantiate_objective(key, params)
                        builder.add(obj, weight=weight)

                objective = builder.build(model, take_vars, courses_df, planning_year_start)
                model.Minimize(objective)

            await loop.run_in_executor(None, build_objective)

            msg = {'type': 'progress', 'message': 'Solving...', 'step': 7, 'totalSteps': 10}
            print(f"[SSE] Sending: {msg}")
            yield f"data: {json.dumps(msg)}\n\n"

            # Create queue for solutions
            solution_queue = queue.Queue()

            # Create callback
            callback = StreamingCallback(take_vars, courses_df, solution_queue)

            # Configure solver
            solver = cp_model.CpSolver()
            solver.parameters.enumerate_all_solutions = True
            solver.parameters.max_time_in_seconds = 30

            # Run solver in thread pool (non-blocking)
            print("[SSE] Starting solver...")
            solver_done = threading.Event()
            result = cp_model.MODEL_INVALID  # Initialize with default value

            def run_solver():
                nonlocal result
                result = solver.Solve(model, callback)
                solution_queue.put({'__done__': True, 'result': result, 'count': callback.solution_count})
                solver_done.set()

            solver_thread = threading.Thread(target=run_solver)
            solver_thread.start()

            # Stream solutions as they arrive in the queue
            while not solver_done.is_set() or not solution_queue.empty():
                try:
                    solution = solution_queue.get(timeout=0.1)

                    # Check for completion signal
                    if '__done__' in solution:
                        result = solution['result']
                        print(f"[SSE] Solver finished with status: {result}, found {solution['count']} solutions")
                        break

                    # Stream the solution
                    print(f"[SSE] Streaming solution {solution['step']}")
                    yield f"data: {json.dumps(solution)}\n\n"

                except queue.Empty:
                    # No solution yet, yield control
                    await asyncio.sleep(0.05)

            # Make sure solver thread completes
            solver_thread.join()

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

            yield f"data: {json.dumps({'type': 'complete', 'status': status_map.get(result, 'MODEL_INVALID'), 'solutionCount': callback.solution_count, 'warnings': warnings})}\n\n"

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
        })

    # Also include default configuration
    defaults = get_default_objectives()
    default_config = [
        {"key": key, "weight": weight, "parameters": params}
        for key, weight, params in defaults
    ]

    return {
        "objectives": result,
        "defaultConfiguration": default_config
    }


@router.get("/optimize/requirements")
async def get_requirements_list():
    """
    Get all available requirements from Fireroad API.

    Returns:
        Dictionary mapping requirement IDs to their metadata (titles, etc.)
    """
    import requests
    response = requests.get('https://fireroad.mit.edu/requirements/list_reqs')
    response.raise_for_status()
    return response.json()
