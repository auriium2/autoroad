"""
Core optimization logic for the worker.
"""

import asyncio
import json
import os
import queue
import threading
import time
from collections.abc import AsyncIterator
from ctypes import c_double, c_int
from multiprocessing import Value
from threading import RLock

import polars as pl
from ortools.sat.python import cp_model

from shared.courses.requirements.parser import parse_fireroad_response
from shared.courses.requirements.validator import validate_and_prune
from shared.models.requests import OptimizationRequest
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
from shared.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
from shared.utils import find_current_school_year


class StreamingCallback(cp_model.CpSolverSolutionCallback):
    """Thread-safe CP-SAT callback for multi-threaded solving."""

    def __init__(
        self,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        courses_df: pl.DataFrame,
        solution_queue: queue.Queue[object],
        builder: ObjectiveBuilder | None = None,
    ):
        super().__init__()
        self.take_vars = take_vars
        self.courses_df = courses_df
        self.solution_queue = solution_queue
        self.builder = builder

        self._solution_count = Value(c_int, 0)
        self._best_lock = RLock()
        self._best_objective_value = Value(c_double, float('inf'))
        self._best_solution_nodes: list[dict[str, object]] = []

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
        nodes = []
        for (course_idx, semester), var in self.take_vars.items():
            if self.Value(var) != 0:
                course_id = self.courses_df[course_idx, 'subject_id']
                title = self.courses_df[course_idx, 'title'] if 'title' in self.courses_df.columns else None
                section = semester - 1 if semester >= 0 else semester
                units = self.courses_df[course_idx, 'total_units'] if 'total_units' in self.courses_df.columns else 12

                nodes.append({
                    "courseId": course_id,
                    "section": section,
                    "title": title,
                    "units": units
                })

        current_objective = self.ObjectiveValue()

        cost_breakdown = None
        if self.builder:
            try:
                cost_breakdown = self.builder.calculate_cost_breakdown(self)
            except Exception as e:
                print(f"[WARNING] Failed to calculate cost breakdown: {e}")

        with self._solution_count.get_lock():
            self._solution_count.value += 1
            solution_num = self._solution_count.value

        if current_objective < self._best_objective_value.value:
            with self._best_lock:
                if current_objective < self._best_objective_value.value:
                    self._best_objective_value.value = current_objective
                    self._best_solution_nodes = nodes

        solution = {
            "type": "solution",
            "step": solution_num,
            "solutionNumber": solution_num,
            "nodes": nodes,
            "objectiveValue": current_objective,
            "costBreakdown": cost_breakdown
        }

        self.solution_queue.put(solution)


async def run_optimization(request: OptimizationRequest) -> AsyncIterator[dict[str, object]]:
    """Run the optimization and yield events as they occur."""
    try:
        perf_timings: dict[str, float] = {}
        perf_start_total = time.time()

        yield {'type': 'progress', 'message': 'Initializing...', 'step': 1, 'totalSteps': 10}

        # Fetch data
        perf_start = time.time()
        courses_data = get_courses_data()
        requirements_data = get_requirements(
            tuple(request.requirements),
            requirement_sources=request.requirementSources
        )
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
        perf_timings['data_fetch'] = time.time() - perf_start

        # Get planning year
        planning_year = request.planningYear
        if not planning_year:
            _, planning_year = find_current_school_year()
        planning_year_start = int(planning_year.split('-')[0])
        max_semesters = request.maxSemesters

        yield {'type': 'progress', 'message': 'Creating model...', 'step': 2, 'totalSteps': 10}

        # Create model
        perf_start = time.time()
        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, planning_year_start, max_semesters, request.markers)
        add_basic_constraints(model, take_vars, courses_df, max_semesters)

        if request.lockPastSemesters:
            add_past_semester_constraints(model, take_vars, courses_df, planning_year_start, request.markers)
        perf_timings['model_creation'] = time.time() - perf_start

        yield {'type': 'progress', 'message': 'Adding requirements...', 'step': 3, 'totalSteps': 10}

        # Add requirement constraints
        perf_start = time.time()
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
        perf_timings['requirements'] = time.time() - perf_start

        yield {'type': 'progress', 'message': 'Adding prerequisites...', 'step': 4, 'totalSteps': 10}

        # Add prerequisite constraints
        perf_start = time.time()
        prereq_trees = get_parsed_prerequisites(courses_df)
        override_course_ids = {m.courseId for m in request.markers if m.status == 'override'}
        add_prerequisite_constraints(model, take_vars, courses_df, planning_year_start, prereq_trees, override_course_ids)
        perf_timings['prerequisites'] = time.time() - perf_start

        yield {'type': 'progress', 'message': 'Adding markers...', 'step': 5, 'totalSteps': 10}

        # Add marker constraints
        perf_start = time.time()
        marker_result = add_marker_constraints(model, take_vars, request.markers, courses_df, planning_year_start)
        perf_timings['markers'] = time.time() - perf_start

        # Add hard constraints
        perf_start = time.time()
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
        perf_timings['hard_constraints'] = time.time() - perf_start

        yield {'type': 'progress', 'message': 'Building objective...', 'step': 6, 'totalSteps': 10}

        # Build objective
        perf_start = time.time()
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
        perf_timings['objective_building'] = time.time() - perf_start

        yield {'type': 'progress', 'message': 'Solving...', 'step': 7, 'totalSteps': 10}

        # Create queue and callback
        solution_queue: queue.Queue[object] = queue.Queue()
        callback = StreamingCallback(take_vars, courses_df, solution_queue, builder=builder)

        # Configure solver
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 20
        solver.parameters.enumerate_all_solutions = False
        num_workers = int(os.environ.get("CPSAT_NUM_WORKERS", "0"))
        solver.parameters.num_search_workers = num_workers

        # Run solver in thread
        solver_done = threading.Event()
        result = cp_model.MODEL_INVALID
        solve_start_time = time.time()

        def run_solver():
            nonlocal result
            result = solver.Solve(model, callback)
            solution_queue.put({'__done__': True, 'result': result})
            solver_done.set()

        solver_thread = threading.Thread(target=run_solver)
        solver_thread.start()

        # Yield solutions as they arrive
        while not solver_done.is_set() or not solution_queue.empty():
            try:
                solution = solution_queue.get(timeout=0.1)
                if isinstance(solution, dict) and '__done__' in solution:
                    result = solution['result']
                    break
                if isinstance(solution, dict):
                    yield solution
            except queue.Empty:
                await asyncio.sleep(0.05)

        solver_thread.join()

        perf_timings['solving'] = time.time() - solve_start_time
        perf_timings['total'] = time.time() - perf_start_total

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
            warnings.append("No feasible solution found. Markers or constraints may be too strict.")
            if marker_result.errors:
                warnings.extend(marker_result.errors[:3])

        yield {
            'type': 'complete',
            'status': status_map.get(result, 'MODEL_INVALID'),
            'solutionCount': callback.solution_count,
            'warnings': warnings,
            'solveTimeSeconds': perf_timings['solving'],
            'performanceTimings': perf_timings
        }

    except Exception as e:
        yield {'type': 'error', 'error': str(e), 'details': type(e).__name__}


async def event_stream(request: OptimizationRequest) -> AsyncIterator[str]:
    """Wrap run_optimization to yield SSE-formatted strings."""
    async for event in run_optimization(request):
        yield f"data: {json.dumps(event)}\n\n"
