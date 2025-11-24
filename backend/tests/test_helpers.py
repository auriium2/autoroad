"""
Test helper functions for validating optimizer solutions.

These helpers provide comprehensive validation beyond just checking
if a solution is feasible. They verify solution quality, prerequisite
satisfaction, and realistic constraints.
"""

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from courses.prerequisites.types import PrereqCourse, PrereqGroup, PrereqNode
from optimizer.objectives import MinimizeUnits, ObjectiveBuilder
from optimizer.objectives.registry import get_default_objectives, instantiate_objective


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
    from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
    from courses.requirements.parser import parse_requirement
    from courses.requirements.validator import validate_and_prune
    from optimizer.constraints.basic import add_basic_constraints, create_take_vars
    from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
    from optimizer.requirement_constraint_builder import add_requirement_constraints

    # Fetch data
    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    requirements_data = get_requirements(requirement_keys)
    prereq_trees = get_parsed_prerequisites(courses_df)

    # Create model
    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, start_year, max_semesters=max_semesters, markers=None)
    add_basic_constraints(model, take_vars, courses_df, max_semesters=max_semesters)
    add_prerequisite_constraints(model, take_vars, courses_df, start_year, prereq_trees, set())

    # Add requirements
    for req_key in requirement_keys:
        if req_key in requirements_data:
            req_data = requirements_data[req_key]
            if isinstance(req_data, dict):
                req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                if validation.pruned_tree is not None:
                    add_requirement_constraints(model, take_vars, validation.pruned_tree, courses_df, start_year, enforce=True)

    # Add objectives
    setup_optimizer_with_objectives(model, take_vars, courses_df, start_year)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solver_timeout
    status = solver.Solve(model)

    assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        f"Expected feasible solution for {requirement_keys}, got status {status}"

    return solver


def run_optimizer_quality_test(
    requirement_keys: tuple[str, ...],
    degree_id: str,
    optimizer_config: Any,
    max_semesters: int | None = None,
    start_year: int | None = None,
    solver_timeout: float | None = None
) -> tuple[cp_model.CpSolver, dict[tuple[int, int], cp_model.IntVar], pl.DataFrame, dict]:
    """
    Run a comprehensive optimizer quality test.

    Sets up the optimizer, finds a solution, and validates solution quality including:
    - Reasonable course count
    - Prerequisites satisfied
    - Distribution across semesters

    Args:
        requirement_keys: Tuple of requirement keys (e.g., ('major6-9', 'girs'))
        degree_id: Degree ID for looking up expected course counts
        optimizer_config: OptimizerTestConfig from conftest
        max_semesters: Override max semesters (defaults to optimizer_config)
        start_year: Override start year (defaults to optimizer_config)
        solver_timeout: Override solver timeout (defaults to optimizer_config)

    Returns:
        Tuple of (solver, take_vars, courses_df, prereq_trees)

    Raises:
        AssertionError: If solution quality checks fail
    """
    from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
    from courses.requirements.parser import parse_requirement
    from courses.requirements.validator import validate_and_prune
    from optimizer.constraints.basic import add_basic_constraints, create_take_vars
    from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
    from optimizer.requirement_constraint_builder import add_requirement_constraints

    # Use config values or overrides
    max_semesters = max_semesters or optimizer_config.max_semesters
    start_year = start_year or optimizer_config.start_year
    solver_timeout = solver_timeout or optimizer_config.solver_timeout_seconds

    # Fetch data
    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    requirements_data = get_requirements(requirement_keys)
    prereq_trees = get_parsed_prerequisites(courses_df)

    # Create model
    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, start_year, max_semesters=max_semesters, markers=None)
    add_basic_constraints(model, take_vars, courses_df, max_semesters=max_semesters)
    add_prerequisite_constraints(model, take_vars, courses_df, start_year, prereq_trees, set())

    # Add requirements
    for req_key in requirement_keys:
        if req_key in requirements_data:
            req_data = requirements_data[req_key]
            if isinstance(req_data, dict):
                req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                if validation.pruned_tree is not None:
                    add_requirement_constraints(model, take_vars, validation.pruned_tree, courses_df, start_year, enforce=True)

    # Add objectives
    setup_optimizer_with_objectives(model, take_vars, courses_df, start_year)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solver_timeout
    status = solver.Solve(model)

    assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        f"Expected feasible solution for {requirement_keys}, got status {status}"

    # Validate solution quality
    degree_config = optimizer_config.get_config_for_degree(degree_id)
    take_vars_nested = convert_take_vars_format(take_vars)
    assert_solution_quality(
        solver,
        take_vars_nested,
        courses_df,
        prereq_trees,
        min_courses=int(degree_config['min_expected_courses']),
        max_courses=int(degree_config['max_expected_courses']),
        max_courses_per_semester=optimizer_config.max_courses_per_semester,
        max_semesters=max_semesters,
        min_objective_value=int(degree_config['min_objective_value']),
        max_objective_value=int(degree_config['max_objective_value'])
    )

    return solver, take_vars, courses_df, prereq_trees


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
