"""
Test helper functions for validating optimizer solutions.

These helpers provide comprehensive validation beyond just checking
if a solution is feasible. They verify solution quality, prerequisite
satisfaction, and realistic constraints.

Key functions:
- build_optimizer_model(): Unified model builder for all integration tests
- validate_solution_against_fireroad(): Validate solution against Fireroad API
- run_optimizer_quality_test(): Full quality test with validation
- assert_solution_quality(): Comprehensive solution validation
"""

from dataclasses import dataclass
from typing import Any

import polars as pl
import requests
from ortools.sat.python import cp_model

from shared.courses.prerequisites.types import PrereqCourse, PrereqGroup, PrereqNode
from shared.courses.requirements.parser import parse_fireroad_response
from shared.courses.requirements.validator import validate_and_prune
from shared.models.requests import Marker
from shared.optimizer.constraints.basic import add_basic_constraints, create_take_vars
from shared.optimizer.objectives.builder import ObjectiveBuilder
from shared.optimizer.objectives.registry import get_default_objectives, instantiate_objective
from shared.optimizer.objectives.units import MinimizeUnits
from shared.optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from shared.optimizer.requirements.builder import add_requirement_constraints
from shared.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements


@dataclass
class OptimizerModelResult:
    """Result from build_optimizer_model containing all test artifacts."""
    model: cp_model.CpModel
    take_vars: dict[tuple[int, int], cp_model.IntVar]
    courses_df: pl.DataFrame
    prereq_trees: dict[int, PrereqNode]
    course_to_requirements: dict[int, set[str]]
    requirements_data: dict[str, Any]


@dataclass
class FireroadValidationResult:
    """Result from Fireroad API validation."""
    all_satisfied: bool
    requirement_results: dict[str, bool]  # req_key -> fulfilled
    details: dict[str, Any]  # req_key -> full Fireroad response


def build_optimizer_model(
    requirement_keys: tuple[str, ...],
    markers: list[Marker] | None = None,
    start_year: int = 2025,
    max_semesters: int = 12,
    with_objectives: bool = True,
    freeze_past_semesters: bool = False,
    cached_data: Any = None,
) -> OptimizerModelResult:
    """
    Build a complete optimizer model - unified helper for all integration tests.

    This is the single source of truth for building optimizer models in tests.
    All integration tests should use this function to ensure consistent behavior.

    Args:
        requirement_keys: Tuple of requirement keys (e.g., ('major6-3new', 'girs'))
        markers: Optional list of markers (pins, overrides, banishes)
        start_year: Planning start year
        max_semesters: Maximum number of semesters
        with_objectives: Whether to add objective functions (default True)
        freeze_past_semesters: Whether to add past semester constraints
        cached_data: Optional CachedCourseData from conftest fixture

    Returns:
        OptimizerModelResult with model, variables, and data
    """
    # Load data (use cache if provided)
    if cached_data is not None:
        courses_df = cached_data.courses_df
        prereq_trees = cached_data.prereq_trees
        requirements_data = cached_data.get_requirements(requirement_keys)
    else:
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
        requirements_data = get_requirements(requirement_keys)
        prereq_trees = get_parsed_prerequisites(courses_df)

    # Create model
    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, start_year, max_semesters, markers)
    add_basic_constraints(model, take_vars, courses_df, max_semesters)

    # Add past semester constraints if requested
    if freeze_past_semesters and markers:
        from shared.optimizer.constraints.basic import add_past_semester_constraints
        add_past_semester_constraints(model, take_vars, courses_df, start_year, markers)

    # Add marker constraints if markers provided
    if markers:
        from shared.optimizer.marker_constraint_builder import add_marker_constraints
        add_marker_constraints(model, take_vars, markers, courses_df, start_year)

    # Add prerequisite constraints (with override courses skipping prereqs)
    override_course_ids = set()
    if markers:
        override_course_ids = {m.courseId for m in markers if m.status == 'override'}
    add_prerequisite_constraints(model, take_vars, courses_df, start_year, prereq_trees, override_course_ids)

    # Add requirement constraints using req_2 parser and builder
    course_to_requirements: dict[int, set[str]] = {}
    for req_key in requirement_keys:
        if req_key in requirements_data:
            req_data = requirements_data[req_key]
            if isinstance(req_data, dict):
                # Parse directly to req_2 types
                req_tree = parse_fireroad_response(req_data)
                # Validate and prune
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                if validation.pruned_tree is not None:
                    _aux_vars, _debug_names, mapping = add_requirement_constraints(
                        model, take_vars, validation.pruned_tree,
                        courses_df, req_key, enforce=True
                    )
                    # Merge course->requirements mappings
                    for course_idx, req_paths in mapping.items():
                        if course_idx not in course_to_requirements:
                            course_to_requirements[course_idx] = set()
                        course_to_requirements[course_idx].update(req_paths)

    # Add objectives if requested
    if with_objectives:
        setup_optimizer_with_objectives(
            model, take_vars, courses_df, start_year, course_to_requirements
        )

    return OptimizerModelResult(
        model=model,
        take_vars=take_vars,
        courses_df=courses_df,
        prereq_trees=prereq_trees,
        course_to_requirements=course_to_requirements,
        requirements_data=requirements_data,
    )


def solve_model(
    model: cp_model.CpModel,
    timeout_seconds: float = 20.0,
    random_seed: int = 42,
) -> tuple[cp_model.CpSolver, int]:
    """
    Solve a model with deterministic settings.

    Args:
        model: CP-SAT model to solve
        timeout_seconds: Solver timeout
        random_seed: Random seed for deterministic behavior

    Returns:
        Tuple of (solver, status)
    """
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    solver.parameters.random_seed = random_seed
    status = int(solver.Solve(model))
    return solver, status


def extract_solution_courses(
    solver: cp_model.CpSolver,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
) -> list[dict[str, Any]]:
    """
    Extract solution courses from a solved model.

    Args:
        solver: Solved CP-SAT solver
        take_vars: Decision variables
        courses_df: DataFrame of courses

    Returns:
        List of course dicts with subject_id, title, units, semester
    """
    solution_courses = []
    for (course_idx, semester_internal), var in take_vars.items():
        if solver.Value(var) == 1:
            course_id = courses_df[course_idx, 'subject_id']
            title = courses_df[course_idx, 'title'] if 'title' in courses_df.columns else course_id
            units = courses_df[course_idx, 'total_units'] if 'total_units' in courses_df.columns else 12

            # Convert internal semester to Fireroad format
            # Internal: -1 for ASE, 1-12 for regular semesters
            # Fireroad: 0 for ASE, 1-12 for regular semesters
            if semester_internal == -1:
                semester_fireroad = 0  # ASE
            else:
                semester_fireroad = semester_internal

            solution_courses.append({
                'subject_id': course_id,
                'title': title,
                'units': int(units) if units else 12,
                'semester': semester_fireroad
            })
    return solution_courses


def validate_solution_against_fireroad(
    solution_courses: list[dict[str, Any]],
    requirement_keys: tuple[str, ...],
    timeout: float = 30.0,
    verbose: bool = False,
) -> FireroadValidationResult:
    """
    Validate a solution against the Fireroad API.

    This is the "ground truth" validation - Fireroad is the source of truth
    for whether requirements are satisfied. Use this to verify our constraint
    builder matches actual Fireroad behavior.

    Args:
        solution_courses: List of course dicts from extract_solution_courses()
        requirement_keys: Tuple of requirement keys to validate
        timeout: HTTP request timeout
        verbose: Print detailed progress info

    Returns:
        FireroadValidationResult with satisfaction status for each requirement

    Raises:
        requests.RequestException: If Fireroad API is unreachable
    """
    requirement_results: dict[str, bool] = {}
    details: dict[str, Any] = {}

    for req_key in requirement_keys:
        req_payload = {
            'coursesOfStudy': [req_key],
            'selectedSubjects': solution_courses,
            'progressAssertions': {}
        }

        # Fireroad API requires trailing slash
        response = requests.post(
            f'https://fireroad.mit.edu/requirements/progress/{req_key}/',
            json=req_payload,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=timeout
        )

        if response.status_code != 200:
            raise requests.RequestException(
                f"Fireroad API error for {req_key}: {response.status_code} - {response.text}"
            )

        fireroad_result = response.json()
        details[req_key] = fireroad_result

        # Check if top-level requirement is fulfilled
        fulfilled = fireroad_result.get('fulfilled', False)
        requirement_results[req_key] = fulfilled

        if verbose:
            status = "✓" if fulfilled else "✗"
            progress = fireroad_result.get('progress', 0)
            max_val = fireroad_result.get('max', '?')
            print(f"  {status} {req_key}: {progress}/{max_val}")

    all_satisfied = all(requirement_results.values())

    return FireroadValidationResult(
        all_satisfied=all_satisfied,
        requirement_results=requirement_results,
        details=details,
    )


def run_full_optimizer_test(
    requirement_keys: tuple[str, ...],
    markers: list[Marker] | None = None,
    optimizer_config: Any = None,
    validate_fireroad: bool = False,
    verbose: bool = False,
    cached_data: Any = None,
) -> tuple[cp_model.CpSolver, OptimizerModelResult]:
    """
    Run a complete optimizer test with optional Fireroad validation.

    This is the highest-level test helper that:
    1. Builds the model
    2. Solves it
    3. Optionally validates against Fireroad

    Args:
        requirement_keys: Tuple of requirement keys
        markers: Optional markers
        optimizer_config: OptimizerTestConfig from conftest (or None for defaults)
        validate_fireroad: Whether to validate against Fireroad API
        verbose: Print progress info
        cached_data: Optional CachedCourseData from conftest fixture

    Returns:
        Tuple of (solver, model_result)

    Raises:
        AssertionError: If solution is infeasible or Fireroad validation fails
    """
    # Get config values
    start_year = optimizer_config.start_year if optimizer_config else 2025
    max_semesters = optimizer_config.max_semesters if optimizer_config else 12
    timeout = optimizer_config.solver_timeout_seconds if optimizer_config else 20.0
    seed = optimizer_config.solver_random_seed if optimizer_config else 42

    # Build model
    result = build_optimizer_model(
        requirement_keys=requirement_keys,
        markers=markers,
        start_year=start_year,
        max_semesters=max_semesters,
        with_objectives=True,
        freeze_past_semesters=markers is not None,
        cached_data=cached_data,
    )

    # Solve
    solver, status = solve_model(result.model, timeout, seed)

    assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        f"Expected feasible solution for {requirement_keys}, got status {status}"

    if verbose:
        print(f"Solution found with {solver.ObjectiveValue()} objective value")

    # Validate against Fireroad if requested
    if validate_fireroad:
        solution_courses = extract_solution_courses(solver, result.take_vars, result.courses_df)

        if verbose:
            print(f"Validating {len(solution_courses)} courses against Fireroad...")

        fireroad_result = validate_solution_against_fireroad(
            solution_courses, requirement_keys, verbose=verbose
        )

        if not fireroad_result.all_satisfied:
            failed_reqs = [k for k, v in fireroad_result.requirement_results.items() if not v]
            raise AssertionError(
                f"Fireroad validation failed for: {failed_reqs}. "
                "Optimizer reported FEASIBLE but Fireroad says requirements NOT satisfied."
            )

    return solver, result


def setup_optimizer_with_objectives(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
    planning_year_start: int,
    course_to_requirements: dict[int, set[str]] | None = None
) -> None:
    """
    Add objective function to model using default objectives (mimics actual backend).

    This function replicates what the backend does in optimize.py:
    1. Creates ObjectiveBuilder
    2. Adds MinimizeUnits as base objective
    3. Adds all default objectives
    4. Builds and minimizes

    Args:
        model: CP-SAT model to add objectives to
        take_vars: Decision variables mapping (course_idx, semester) to bool vars
        courses_df: DataFrame of courses
        planning_year_start: Start year for planning
        course_to_requirements: Optional mapping of course indices to requirement paths
    """
    builder = ObjectiveBuilder()

    # Always add minimize_units as the core base objective
    builder.add(MinimizeUnits(), key="minimize_units")

    # Add default objectives
    for key, params in get_default_objectives():
        obj = instantiate_objective(key, params)
        builder.add(obj, key=key)

    # Build and minimize
    objective = builder.build(
        model,
        take_vars,
        courses_df,
        planning_year_start,
        objective_tiers=None,
        requirement_tiers=None,
        marked_course_ids=set(),
        course_to_requirements=course_to_requirements or {}
    )
    model.Minimize(objective)


def run_optimizer_test(
    requirement_keys: tuple[str, ...],
    max_semesters: int = 12,
    start_year: int = 2025,
    solver_timeout: float = 60.0
) -> cp_model.CpSolver:
    """
    Run a basic optimizer feasibility test.

    Sets up the optimizer with the given requirements and verifies it finds
    a feasible solution. This is a lightweight test for regression checking.

    Args:
        requirement_keys: Tuple of requirement keys (e.g., ('major6-9', 'girs'))
        max_semesters: Maximum number of semesters
        start_year: Start year for planning
        solver_timeout: Solver timeout in seconds

    Returns:
        Solved CpSolver instance

    Raises:
        AssertionError: If no feasible solution found
    """
    # Use unified helper
    result = build_optimizer_model(
        requirement_keys=requirement_keys,
        markers=None,
        start_year=start_year,
        max_semesters=max_semesters,
        with_objectives=True,
    )

    solver, status = solve_model(result.model, solver_timeout)

    assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        f"Expected feasible solution for {requirement_keys}, got status {status}"

    return solver


def run_optimizer_quality_test(
    requirement_keys: tuple[str, ...],
    degree_id: str,
    optimizer_config: Any,
    max_semesters: int | None = None,
    start_year: int | None = None,
    solver_timeout: float | None = None,
    validate_fireroad: bool = False,
    cached_data: Any = None,
) -> tuple[cp_model.CpSolver, dict[tuple[int, int], cp_model.IntVar], pl.DataFrame, dict[int, PrereqNode]]:
    """
    Run a comprehensive optimizer quality test.

    Sets up the optimizer, finds a solution, and validates solution quality including:
    - Reasonable course count
    - Prerequisites satisfied
    - Distribution across semesters
    - Optionally validates against Fireroad API

    Args:
        requirement_keys: Tuple of requirement keys (e.g., ('major6-9', 'girs'))
        degree_id: Degree ID for looking up expected course counts
        optimizer_config: OptimizerTestConfig from conftest
        max_semesters: Override max semesters (defaults to optimizer_config)
        start_year: Override start year (defaults to optimizer_config)
        solver_timeout: Override solver timeout (defaults to optimizer_config)
        validate_fireroad: Whether to validate solution against Fireroad API
        cached_data: Optional CachedCourseData from conftest fixture

    Returns:
        Tuple of (solver, take_vars, courses_df, prereq_trees)

    Raises:
        AssertionError: If solution quality checks fail or Fireroad validation fails
    """
    # Use config values or overrides
    max_semesters_val: int = max_semesters if max_semesters is not None else optimizer_config.max_semesters
    start_year_val: int = start_year if start_year is not None else optimizer_config.start_year
    solver_timeout_val: float = solver_timeout if solver_timeout is not None else optimizer_config.solver_timeout_seconds

    # Use unified helper to build model
    result = build_optimizer_model(
        requirement_keys=requirement_keys,
        markers=None,
        start_year=start_year_val,
        max_semesters=max_semesters_val,
        with_objectives=True,
        cached_data=cached_data,
    )

    # Solve with deterministic settings
    solver = cp_model.CpSolver()
    optimizer_config.configure_solver(solver)
    status = solver.Solve(result.model)

    assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        f"Expected feasible solution for {requirement_keys}, got status {status}"

    # Validate solution quality
    degree_config = optimizer_config.get_config_for_degree(degree_id)
    take_vars_nested = convert_take_vars_format(result.take_vars)
    assert_solution_quality(
        solver,
        take_vars_nested,
        result.courses_df,
        result.prereq_trees,
        min_courses=int(degree_config['min_expected_courses']),
        max_courses=int(degree_config['max_expected_courses']),
        max_courses_per_semester=optimizer_config.max_courses_per_semester,
        max_semesters=max_semesters_val,
        min_objective_value=int(degree_config['min_objective_value']),
        max_objective_value=int(degree_config['max_objective_value'])
    )

    # Optionally validate against Fireroad
    if validate_fireroad:
        solution_courses = extract_solution_courses(solver, result.take_vars, result.courses_df)
        fireroad_result = validate_solution_against_fireroad(solution_courses, requirement_keys)

        if not fireroad_result.all_satisfied:
            failed_reqs = [k for k, v in fireroad_result.requirement_results.items() if not v]
            raise AssertionError(
                f"Fireroad validation failed for: {failed_reqs}. "
                "Optimizer reported FEASIBLE but Fireroad says requirements NOT satisfied."
            )

    return solver, result.take_vars, result.courses_df, result.prereq_trees


def convert_take_vars_format(
    take_vars: dict[tuple[int, int], cp_model.IntVar]
) -> dict[int, dict[int, cp_model.IntVar]]:
    """
    Convert take_vars from new flat format to nested format for test helpers.

    New format: dict[(course_idx, semester)] -> IntVar
    Old format: dict[course_idx][semester] -> IntVar

    Args:
        take_vars: Take variables in new flat format

    Returns:
        Take variables in nested format
    """
    nested = {}
    for (course_idx, semester), var in take_vars.items():
        if course_idx not in nested:
            nested[course_idx] = {}
        nested[course_idx][semester] = var
    return nested


def count_courses_in_solution(
    solver: cp_model.CpSolver,
    take_vars: dict[int, dict[int, cp_model.IntVar]],
    courses_df: pl.DataFrame
) -> int:
    """
    Count total number of courses taken in the solution.

    Args:
        solver: Solved CP-SAT solver
        take_vars: Take variables indexed by [course_idx][semester]
        courses_df: DataFrame with course information

    Returns:
        Total number of courses scheduled
    """
    total_courses = 0
    for course_idx in range(len(courses_df)):
        if course_idx in take_vars:
            for semester in take_vars[course_idx]:
                if solver.Value(take_vars[course_idx][semester]) == 1:
                    total_courses += 1
    return total_courses


def get_semester_distribution(
    solver: cp_model.CpSolver,
    take_vars: dict[int, dict[int, cp_model.IntVar]],
    courses_df: pl.DataFrame,
    max_semesters: int
) -> dict[int, int]:
    """
    Get distribution of courses across semesters.

    Args:
        solver: Solved CP-SAT solver
        take_vars: Take variables indexed by [course_idx][semester]
        courses_df: DataFrame with course information
        max_semesters: Maximum number of semesters

    Returns:
        Dictionary mapping semester -> course count
    """
    distribution = {}

    for course_idx in range(len(courses_df)):
        if course_idx in take_vars:
            for semester in take_vars[course_idx]:
                if solver.Value(take_vars[course_idx][semester]) == 1:
                    if semester not in distribution:
                        distribution[semester] = 0
                    distribution[semester] += 1

    return distribution


def verify_prerequisites_satisfied(
    solver: cp_model.CpSolver,
    take_vars: dict[int, dict[int, cp_model.IntVar]],
    courses_df: pl.DataFrame,
    prereq_trees: dict[int, PrereqNode]
) -> tuple[bool, list[str]]:
    """
    Verify all prerequisites are satisfied in the schedule.

    For each course taken, check that:
    1. All prerequisite courses are taken in earlier semesters
    2. Prerequisite groups satisfy their thresholds

    Args:
        solver: Solved CP-SAT solver
        take_vars: Take variables
        courses_df: DataFrame with course information
        prereq_trees: Parsed prerequisite trees

    Returns:
        Tuple of (all_satisfied, list of violation messages)
    """
    violations = []

    # Build schedule: course_idx -> semester taken
    schedule = {}
    for course_idx in range(len(courses_df)):
        if course_idx in take_vars:
            for semester in take_vars[course_idx]:
                if solver.Value(take_vars[course_idx][semester]) == 1:
                    schedule[course_idx] = semester
                    break

    # Check prerequisites for each scheduled course
    for course_idx, semester_taken in schedule.items():
        if course_idx not in prereq_trees:
            continue

        prereq_tree = prereq_trees[course_idx]
        if prereq_tree is None:
            continue

        # Check if prerequisites are satisfied before this semester
        if not _check_prereq_node_satisfied(
            prereq_tree, schedule, semester_taken, courses_df, course_idx, violations
        ):
            course_id = courses_df.row(course_idx, named=True)['subject_id']
            violations.append(
                f"Course {course_id} taken in semester {semester_taken} "
                f"has unsatisfied prerequisites"
            )

    return len(violations) == 0, violations


def _check_prereq_node_satisfied(
    node: PrereqNode,
    schedule: dict[int, int],
    semester_taken: int,
    courses_df: pl.DataFrame,
    current_course_idx: int,
    violations: list[str]
) -> bool:
    """Helper to recursively check if a prerequisite node is satisfied."""
    if isinstance(node, PrereqCourse):
        course_id = node.course_id

        # Handle GIR prerequisites (e.g., GIR:CAL1, GIR:PHY1)
        if course_id.startswith('GIR:'):
            gir_code = course_id.split(':', 1)[1]
            # Check if ANY course with this GIR attribute was taken before
            for idx, sem in schedule.items():
                if sem < semester_taken:
                    # Check if this course satisfies the GIR
                    if 'gir_attribute' in courses_df.columns:
                        course_gir = courses_df[idx, 'gir_attribute']
                        if course_gir == gir_code:
                            return True
            return False

        # Handle HASS prerequisites (e.g., HASS:A, HASS:H)
        if course_id.startswith('HASS:'):
            hass_code = course_id.split(':', 1)[1]
            # Check if ANY course with this HASS attribute was taken before
            for idx, sem in schedule.items():
                if sem < semester_taken:
                    if 'hass_attribute' in courses_df.columns:
                        course_hass = courses_df[idx, 'hass_attribute']
                        if course_hass == f'HASS-{hass_code}':
                            return True
            return False

        # Handle CI prerequisites (e.g., CI-H, CI-HW)
        if course_id.startswith('CI-'):
            # Check if ANY course with this CI attribute was taken before
            for idx, sem in schedule.items():
                if sem < semester_taken:
                    if 'communication_requirement' in courses_df.columns:
                        course_ci = courses_df[idx, 'communication_requirement']
                        if course_ci == course_id:
                            return True
            return False

        # Regular course prerequisite
        course_rows = courses_df.with_row_index().filter(
            pl.col('subject_id') == course_id
        )

        if len(course_rows) == 0:
            # Course doesn't exist - can't be satisfied
            return False

        prereq_course_idx = course_rows.row(0, named=True)['index']

        # Check if this prerequisite was taken before current course
        if prereq_course_idx not in schedule:
            return False

        if schedule[prereq_course_idx] >= semester_taken:
            return False

        return True

    elif isinstance(node, PrereqGroup):
        # Check how many children are satisfied
        satisfied_count = 0
        for child in node.items:
            if _check_prereq_node_satisfied(
                child, schedule, semester_taken, courses_df, current_course_idx, violations
            ):
                satisfied_count += 1

        # Check if threshold is met
        return satisfied_count >= node.threshold

    return False


def verify_degree_requirements_met(
    solver: cp_model.CpSolver,
    take_vars: dict[int, dict[int, cp_model.IntVar]],
    courses_df: pl.DataFrame,
    requirement_data: dict[str, Any]
) -> tuple[bool, list[str]]:
    """
    Verify degree requirements are satisfied.

    This is a basic check - just verifies some courses from the requirement
    are actually scheduled. Full validation happens in constraint builder.

    Args:
        solver: Solved CP-SAT solver
        take_vars: Take variables
        courses_df: DataFrame with course information
        requirement_data: Requirement specification

    Returns:
        Tuple of (requirements_met, list of issues)
    """
    issues = []

    # Get list of courses actually taken
    taken_courses = set()
    for course_idx in range(len(courses_df)):
        if course_idx in take_vars:
            for semester in take_vars[course_idx]:
                if solver.Value(take_vars[course_idx][semester]) == 1:
                    course_id = courses_df.row(course_idx, named=True)['subject_id']
                    taken_courses.add(course_id)

    # Basic sanity check: should have some courses
    if len(taken_courses) == 0:
        issues.append("No courses scheduled")
        return False, issues

    return True, issues


def assert_solution_quality(
    solver: cp_model.CpSolver,
    take_vars: dict[int, dict[int, cp_model.IntVar]],
    courses_df: pl.DataFrame,
    prereq_trees: dict[int, PrereqNode],
    min_courses: int,
    max_courses: int,
    max_courses_per_semester: int,
    max_semesters: int,
    min_objective_value: int | None = None,
    max_objective_value: int | None = None
):
    """
    Comprehensive assertion of solution quality.

    This is the main validation function that should be called in E2E tests.
    It checks multiple aspects of solution quality.

    Raises:
        AssertionError: If any quality check fails
    """
    # 1. Check course count
    total_courses = count_courses_in_solution(solver, take_vars, courses_df)
    assert min_courses <= total_courses <= max_courses, \
        f"Expected {min_courses}-{max_courses} courses, got {total_courses}"

    # 2. Check semester distribution
    distribution = get_semester_distribution(
        solver, take_vars, courses_df, max_semesters
    )

    for semester, count in distribution.items():
        assert count <= max_courses_per_semester, \
            f"Semester {semester} has {count} courses (max {max_courses_per_semester})"

    # 3. Verify prerequisites
    prereqs_ok, violations = verify_prerequisites_satisfied(
        solver, take_vars, courses_df, prereq_trees
    )

    if not prereqs_ok:
        violation_msg = "\n  ".join(violations)
        assert False, f"Prerequisite violations found:\n  {violation_msg}"

    # 4. Check for reasonable distribution (not all in one semester)
    non_empty_semesters = [s for s, c in distribution.items() if c > 0]
    assert len(non_empty_semesters) >= 3, \
        f"Courses should be spread across at least 3 semesters, got {len(non_empty_semesters)}"

    # 5. Check objective value is in reasonable range
    if min_objective_value is not None or max_objective_value is not None:
        objective_value = solver.ObjectiveValue()
        if min_objective_value is not None:
            assert objective_value >= min_objective_value, \
                f"Objective value {objective_value} is below minimum {min_objective_value}"
        if max_objective_value is not None:
            assert objective_value <= max_objective_value, \
                f"Objective value {objective_value} is above maximum {max_objective_value}"
