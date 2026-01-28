"""
Core optimization logic for the worker.
"""

import base64
import json
import logging
import os
import threading
import time
from collections.abc import AsyncIterator
from ctypes import c_double, c_int
from dataclasses import dataclass
from multiprocessing import Value
from threading import RLock
from typing import Any

import janus
import polars as pl
import sentry_sdk
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
from shared.services.cache import (
    get_courses_data,
    get_parsed_prerequisites_by_index,
    get_requirements,
)
from shared.utils import find_current_school_year

logger = logging.getLogger("uvicorn.error")

# Attribute columns to include for frontend marker matching
ATTRIBUTE_COLUMNS = ('hass_attribute', 'gir_attribute', 'communication_requirement')


def _log_infeasibility_to_sentry(
    request: "OptimizationRequest",
    marker_errors: list[str],
    marker_warnings: list[str],
    planning_year_start: int,
    perf_timings: dict[str, float],
) -> None:
    from shared.utils import get_current_semester_index

    # Build markers data in a format similar to .road file
    markers_data = [
        {
            "courseId": m.courseId,
            "section": m.section,
            "status": m.status,
        }
        for m in (request.markers or [])
    ]

    # Compute current semester for context
    current_semester = get_current_semester_index(planning_year_start)

    # Group markers by type for easier analysis
    pinned_markers = [m for m in markers_data if m["status"] == "pin"]
    banished_markers = [m for m in markers_data if m["status"] == "banish"]
    override_markers = [m for m in markers_data if m["status"] == "override"]

    # Count markers in past vs future semesters
    past_pins = [m for m in pinned_markers if 0 <= m["section"] < current_semester]
    future_pins = [m for m in pinned_markers if m["section"] >= current_semester]

    sentry_sdk.set_context("infeasibility_debug", {
        "planning_year": request.planningYear,
        "planning_year_start": planning_year_start,
        "current_semester": current_semester,
        "lock_past_semesters": request.lockPastSemesters,
        "max_semesters": request.maxSemesters,
        "requirements": request.requirements,
        "num_markers_total": len(markers_data),
        "num_pinned": len(pinned_markers),
        "num_banished": len(banished_markers),
        "num_override": len(override_markers),
        "num_past_pins": len(past_pins),
        "num_future_pins": len(future_pins),
        "marker_errors": marker_errors,
        "marker_warnings": marker_warnings,
        "perf_timings": perf_timings,
    })

    # Set the full markers as an attachment-like context
    sentry_sdk.set_context("markers_full", {
        "pinned": pinned_markers,
        "banished": banished_markers,
        "override": override_markers,
    })

    # Set objectives and constraints context
    sentry_sdk.set_context("optimization_config", {
        "objectives": [{"key": o.key, "parameters": o.parameters} for o in (request.objectives or [])],
        "hard_constraints": [{"key": c.key, "parameters": c.parameters} for c in (request.hardConstraints or [])],
        "requirement_tiers": request.requirementTiers,
        "objective_tiers": request.objectiveTiers,
        "requirement_sources": request.requirementSources,
    })

    # Capture the event
    sentry_sdk.capture_message(
        f"Optimization INFEASIBLE: {len(markers_data)} markers, {len(request.requirements)} requirements, "
        f"lockPast={request.lockPastSemesters}, year={request.planningYear}",
        level="error",
    )


@dataclass
class VariableInfo:
    var_index: int
    course_idx: int
    semester: int

    def to_dict(self) -> dict[str, int]:
        return {"var_index": self.var_index, "course_idx": self.course_idx, "semester": self.semester}


@dataclass
class CourseMetadata:
    subject_id: str
    title: str
    units: int
    attributes: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"subject_id": self.subject_id, "title": self.title, "units": self.units}
        if self.attributes:
            d["attributes"] = self.attributes
        return d


@dataclass
class ObjectiveComponent:
    """Serialized objective component for cost breakdown."""
    name: str
    var_indices: list[int]
    coefficients: list[int]
    offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "var_indices": self.var_indices,
            "coefficients": self.coefficients,
            "offset": self.offset,
        }


@dataclass
class SerializedModel:
    """Serialized CpModel with metadata for C++ worker."""
    cpmodel_proto: bytes
    variable_mapping: list[VariableInfo]
    courses_metadata: list[CourseMetadata]
    solver_params: dict[str, Any]
    objective_components: list[ObjectiveComponent]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpmodel_proto": base64.b64encode(self.cpmodel_proto).decode('ascii'),
            "variable_mapping": [v.to_dict() for v in self.variable_mapping],
            "courses_metadata": [c.to_dict() for c in self.courses_metadata],
            "solver_params": self.solver_params,
            "objective_components": [c.to_dict() for c in self.objective_components],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def serialize_model(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
    builder: "ObjectiveBuilder",
    max_time_seconds: float = 20.0,
    num_workers: int = 8,
) -> SerializedModel:
    """
    Serialize a CpModel and its metadata for the C++ worker.

    The C++ worker needs:
    1. The CpModel protobuf (the mathematical structure)
    2. Variable mapping: which variable index corresponds to which (course_idx, semester)
    3. Course metadata: subject_id, title, units for each course_idx
    4. Objective components: coefficients for cost breakdown calculation
    """
    proto = model.Proto()
    cpmodel_proto = proto.SerializeToString()

    variable_mapping: list[VariableInfo] = []
    var_name2idx: dict[str, int] = {}
    for idx, var in enumerate(proto.variables):
        var_name2idx[var.name] = idx

    for (course_idx, semester), var in take_vars.items():
        var_name = var.Name()
        if var_name in var_name2idx:
            variable_mapping.append(VariableInfo(
                var_index=var_name2idx[var_name],
                course_idx=course_idx,
                semester=semester,
            ))

    course_indices = sorted(set(v.course_idx for v in variable_mapping))
    max_course_idx = max(course_indices) if course_indices else 0

    courses_metadata: list[CourseMetadata] = []
    for idx in range(max_course_idx + 1):
        if idx < len(courses_df):
            subject_id = str(courses_df[idx, 'subject_id'])
            title = str(courses_df[idx, 'title']) if 'title' in courses_df.columns else ""
            units = int(courses_df[idx, 'total_units']) if 'total_units' in courses_df.columns else 12

            # Collect non-null attributes
            attrs: dict[str, str] = {}
            for col in ATTRIBUTE_COLUMNS:
                if col in courses_df.columns:
                    val = courses_df[idx, col]
                    if val is not None:
                        attrs[col] = str(val)
        else:
            subject_id = f"UNKNOWN_{idx}"
            title = ""
            units = 12
            attrs = {}
        courses_metadata.append(CourseMetadata(subject_id=subject_id, title=title, units=units, attributes=attrs if attrs else None))

    solver_params = {
        "max_time_seconds": max_time_seconds,
        "num_workers": num_workers,
    }

    # Serialize objective components for cost breakdown
    objective_components: list[ObjectiveComponent] = []
    for name, expr in builder.component_expressions:
        linear_expr_proto = model.parse_linear_expression(expr)
        objective_components.append(ObjectiveComponent(
            name=name,
            var_indices=list(linear_expr_proto.vars),
            coefficients=list(linear_expr_proto.coeffs),
            offset=linear_expr_proto.offset,
        ))

    return SerializedModel(
        cpmodel_proto=cpmodel_proto,
        variable_mapping=variable_mapping,
        courses_metadata=courses_metadata,
        solver_params=solver_params,
        objective_components=objective_components,
    )


class StreamingCallback(cp_model.CpSolverSolutionCallback):
    """Thread-safe CP-SAT callback for multi-threaded solving."""

    def __init__(
        self,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        courses_df: pl.DataFrame,
        solution_queue: janus.SyncQueue[object],
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

                # Collect non-null attributes for marker matching
                attrs = {}
                for col in ATTRIBUTE_COLUMNS:
                    if col in self.courses_df.columns:
                        val = self.courses_df[course_idx, col]
                        if val is not None:
                            attrs[col] = val

                node: dict[str, object] = {
                    "courseId": course_id,
                    "section": section,
                    "title": title,
                    "units": units,
                }
                if attrs:
                    node["attributes"] = attrs

                nodes.append(node)

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

        # Set Sentry context for this optimization
        sentry_sdk.set_context("optimization_request", {
            "requirements": request.requirements,
            "num_markers": len(request.markers) if request.markers else 0,
            "max_semesters": request.maxSemesters,
            "num_objectives": len(request.objectives) if request.objectives else 0,
            "num_hard_constraints": len(request.hardConstraints) if request.hardConstraints else 0,
        })

        yield {'type': 'progress', 'message': 'Initializing...', 'step': 1, 'totalSteps': 10}

        # Fetch data
        with sentry_sdk.start_span(op="db.query", name="fetch_courses_and_requirements") as span:
            perf_start = time.time()
            courses_data = await get_courses_data()
            requirements_data = await get_requirements(
                tuple(request.requirements),
                requirement_sources=request.requirementSources
            )
            courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
            perf_timings['data_fetch'] = time.time() - perf_start
            span.set_data("num_courses", len(courses_data))
            span.set_data("num_requirements", len(requirements_data))
            span.set_data("duration_seconds", perf_timings['data_fetch'])

        # Get planning year
        planning_year = request.planningYear
        if not planning_year:
            _, planning_year = find_current_school_year()
        planning_year_start = int(planning_year.split('-')[0])
        max_semesters = request.maxSemesters

        yield {'type': 'progress', 'message': 'Creating model...', 'step': 2, 'totalSteps': 10}

        # Create model
        with sentry_sdk.start_span(op="optimizer", name="create_model") as span:
            perf_start = time.time()
            model = cp_model.CpModel()
            take_vars = create_take_vars(model, courses_df, planning_year_start, max_semesters, request.markers)
            add_basic_constraints(model, take_vars, courses_df, max_semesters)

            if request.lockPastSemesters:
                add_past_semester_constraints(model, take_vars, courses_df, planning_year_start, request.markers)
            perf_timings['model_creation'] = time.time() - perf_start
            span.set_data("num_variables", len(take_vars))
            span.set_data("duration_seconds", perf_timings['model_creation'])

        yield {'type': 'progress', 'message': 'Adding requirements...', 'step': 3, 'totalSteps': 10}

        # Add requirement constraints
        with sentry_sdk.start_span(op="optimizer", name="add_requirements") as span:
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
            span.set_data("num_requirements_processed", len(request.requirements))
            span.set_data("duration_seconds", perf_timings['requirements'])

        yield {'type': 'progress', 'message': 'Adding prerequisites...', 'step': 4, 'totalSteps': 10}

        custom_equivalencies: dict[str, list[str]] | None = None
        if request.objectives:
            for obj_config in request.objectives:
                if obj_config.key == 'discourage_equivalent_courses' and obj_config.parameters:
                    custom_equivalencies = obj_config.parameters.get('custom_equivalencies')
                    break

        if custom_equivalencies is None:
            from shared.optimizer.objectives.registry import get_objective_metadata
            meta = get_objective_metadata('discourage_equivalent_courses')
            if meta:
                custom_equivalencies = meta.default_parameters.get('custom_equivalencies')

        # Add prerequisite constraints
        with sentry_sdk.start_span(op="optimizer", name="add_prerequisites") as span:
            perf_start = time.time()
            prereq_trees = await get_parsed_prerequisites_by_index(courses_df)
            override_course_ids = {m.courseId for m in request.markers if m.status == 'override'}
            add_prerequisite_constraints(model, take_vars, courses_df, planning_year_start, prereq_trees, override_course_ids, custom_equivalencies)
            perf_timings['prerequisites'] = time.time() - perf_start
            span.set_data("duration_seconds", perf_timings['prerequisites'])

        yield {'type': 'progress', 'message': 'Adding markers...', 'step': 5, 'totalSteps': 10}

        # Add marker constraints
        with sentry_sdk.start_span(op="optimizer", name="add_markers") as span:
            perf_start = time.time()
            marker_result = add_marker_constraints(model, take_vars, request.markers, courses_df, planning_year_start)
            perf_timings['markers'] = time.time() - perf_start
            span.set_data("num_markers", len(request.markers) if request.markers else 0)
            span.set_data("duration_seconds", perf_timings['markers'])

        # Add hard constraints
        with sentry_sdk.start_span(op="optimizer", name="add_hard_constraints") as span:
            perf_start = time.time()

            # Use exactly what the frontend sends - no defaults
            constraint_configs = request.hardConstraints or []
            constraint_keys = [c.key for c in constraint_configs]

            if constraint_configs:
                # Fetch Hydrant schedule data for constraints that need it
                hydrant_extra: dict[str, object] = {}
                needs_hydrant_data = 'no_schedule_conflicts' in constraint_keys or 'schedule_free_time' in constraint_keys

                if needs_hydrant_data:
                    from shared.optimizer.constraints.conflicts import (
                        fetch_hydrant_data_for_semesters,
                    )

                    # Get extrapolate parameter from constraints that need hydrant data
                    conflicts_config = next((c for c in constraint_configs if c.key == 'no_schedule_conflicts'), None)
                    free_time_config = next((c for c in constraint_configs if c.key == 'schedule_free_time'), None)

                    # Use extrapolate if either constraint has it enabled
                    extrapolate = (
                        (conflicts_config and bool(conflicts_config.parameters.get('extrapolate', False))) or
                        (free_time_config and bool(free_time_config.parameters.get('extrapolate', False)))
                    )

                    hydrant_data = await fetch_hydrant_data_for_semesters(
                        take_vars, courses_df, planning_year_start, max_semesters, extrapolate
                    )

                    hydrant_extra['hydrant_schedule_data'] = {
                        'semester_to_slots': hydrant_data.semester_to_slots,
                        'semester_to_section_options': hydrant_data.semester_to_section_options,
                    }

                constraint_context = ConstraintContext(
                    planning_year_start=planning_year_start,
                    courses_df=courses_df,
                    max_semesters=max_semesters,
                    markers=request.markers,
                    extra=hydrant_extra if hydrant_extra else None,
                )
                for constraint_config in constraint_configs:
                    try:
                        constraint = instantiate_constraint(constraint_config.key, constraint_config.parameters)
                        constraint.add_to_model(model, take_vars, constraint_context)
                    except ValueError as e:
                        logger.warning("Failed to instantiate constraint '%s': %s", constraint_config.key, e)
            perf_timings['hard_constraints'] = time.time() - perf_start
            span.set_data("num_constraints", len(constraint_configs))
            span.set_data("duration_seconds", perf_timings['hard_constraints'])

        yield {'type': 'progress', 'message': 'Building objective...', 'step': 6, 'totalSteps': 10}

        # Build objective
        with sentry_sdk.start_span(op="optimizer", name="build_objective") as span:
            perf_start = time.time()
            builder = ObjectiveBuilder()

            from shared.optimizer.objectives.units import MinimizeUnits
            builder.add(MinimizeUnits(), key="minimize_units")

            if request.objectives:
                for obj_config in request.objectives:
                    try:
                        obj = instantiate_objective(obj_config.key, obj_config.parameters)
                        builder.add(obj, key=obj_config.key)
                    except ValueError as e:
                        logger.warning("Failed to instantiate objective '%s': %s", obj_config.key, e)
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
            span.set_data("num_objectives", len(request.objectives) if request.objectives else 0)
            span.set_data("duration_seconds", perf_timings['objective_building'])

        yield {'type': 'progress', 'message': 'Solving...', 'step': 7, 'totalSteps': 10}

        # Create janus queue for thread-safe async/sync communication
        queue: janus.Queue[object] = janus.Queue()
        callback = StreamingCallback(take_vars, courses_df, queue.sync_q, builder=builder)

        # Configure solver
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 20
        solver.parameters.enumerate_all_solutions = False
        solver.parameters.log_search_progress = False
        num_workers = int(os.environ.get("CPSAT_NUM_WORKERS", "0"))
        solver.parameters.num_search_workers = num_workers
        print(f"[PYTHON SOLVER] Starting with num_workers={num_workers}")

        # Run solver in thread
        result = cp_model.MODEL_INVALID
        solve_start_time = time.time()

        def run_solver() -> None:
            nonlocal result
            result = solver.Solve(model, callback)
            queue.sync_q.put({'__done__': True, 'result': result})

        solver_thread = threading.Thread(target=run_solver)
        solver_thread.start()

        # Yield solutions as they arrive using async queue (no polling needed)
        try:
            while True:
                solution = await queue.async_q.get()
                if isinstance(solution, dict) and '__done__' in solution:
                    result = solution['result']
                    break
                if isinstance(solution, dict):
                    yield solution
        finally:
            solver_thread.join()
            queue.close()
            await queue.wait_closed()

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

            # Log infeasibility to Sentry with full context for debugging
            _log_infeasibility_to_sentry(
                request=request,
                marker_errors=marker_result.errors,
                marker_warnings=marker_result.warnings,
                planning_year_start=planning_year_start,
                perf_timings=perf_timings,
            )

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
