"""
Fireroad validation tests for optimizer solutions.

These tests verify that optimizer solutions actually satisfy requirements
according to Fireroad's progress API - the source of truth.

This catches bugs where:
- Our constraint builder thinks requirements are satisfied but Fireroad disagrees
- We're counting subgroup contributions incorrectly
- Edge cases in requirement parsing/building

Note: These tests require network access to call Fireroad API.
"""

import pytest
from ortools.sat.python import cp_model

from tests.test_helpers import (
    build_optimizer_model,
    extract_solution_courses,
    solve_model,
    validate_solution_against_fireroad,
)


def run_fireroad_validation_test(
    requirement_keys: tuple[str, ...],
    degree_id: str,
    start_year: int = 2025,
    max_semesters: int = 12,
    timeout_seconds: float = 30.0,
) -> None:
    """
    Build optimizer, solve, and validate against Fireroad API.

    Raises AssertionError if:
    - Optimizer cannot find feasible solution
    - Fireroad says requirements are not satisfied
    """
    # Build and solve
    result = build_optimizer_model(
        requirement_keys=requirement_keys,
        start_year=start_year,
        max_semesters=max_semesters,
        with_objectives=True,
    )

    solver, status = solve_model(result.model, timeout_seconds)

    assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        f"Optimizer should find feasible solution for {degree_id}, got status {status}"

    # Extract solution
    solution_courses = extract_solution_courses(solver, result.take_vars, result.courses_df)

    print(f"[FIREROAD] {degree_id}: {len(solution_courses)} courses in solution")

    # Validate against Fireroad
    fireroad_result = validate_solution_against_fireroad(
        solution_courses, requirement_keys, verbose=True
    )

    if not fireroad_result.all_satisfied:
        failed_reqs = [k for k, v in fireroad_result.requirement_results.items() if not v]

        # Print detailed info for debugging
        for req_key in failed_reqs:
            details = fireroad_result.details.get(req_key, {})
            progress = details.get('progress', 0)
            max_val = details.get('max', '?')
            print(f"[FIREROAD] FAILED: {req_key} - {progress}/{max_val}")

        raise AssertionError(
            f"Fireroad validation failed for {degree_id}. "
            f"Failed requirements: {failed_reqs}. "
            "Optimizer reported FEASIBLE but Fireroad says requirements NOT satisfied."
        )

    print(f"[FIREROAD] {degree_id}: All requirements satisfied")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.fireroad
class TestFireroadValidation:
    """
    Validate optimizer solutions against Fireroad API.

    These are the "ground truth" tests that verify our constraint builder
    matches actual Fireroad behavior.

    Run with: pytest -m fireroad
    """

    def test_fireroad_course_6_3(self):
        """Validate Course 6-3 (Computer Science) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major6-3new', 'girs'),
            degree_id='major6-3new',
        )

    @pytest.mark.skip(reason="Bug with direct-threshold parsing on fireroad clipig")
    def test_fireroad_course_6_2_new(self):
        """Validate Course 6-2new (EECS) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major6-2new', 'girs'),
            degree_id='major6-2new',
        )

    @pytest.mark.skip(reason="Bug with direct-threshold parsing on fireroad clipig")
    def test_fireroad_course_6_4(self):
        """Validate Course 6-4 (AI and Decision Making) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major6-4', 'girs'),
            degree_id='major6-4',
        )

    def test_fireroad_course_6_9(self):
        """Validate Course 6-9 (Computation and Cognition) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major6-9', 'girs'),
            degree_id='major6-9',
        )

    def test_fireroad_course_6_14(self):
        """Validate Course 6-14 (CS, Economics, Data Science) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major6-14', 'girs'),
            degree_id='major6-14',
        )

    @pytest.mark.skip(reason="Elective units/plainstring bug, known, will be solved later")
    def test_fireroad_course_18pm(self):
        """Validate Course 18 (Pure Mathematics) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major18pm', 'girs'),
            degree_id='major18pm',
        )

    @pytest.mark.skip(reason="Elective units/plainstring bug, known, will be solved later")
    def test_fireroad_course_18c(self):
        """Validate Course 18C (Mathematics with CS) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major18c', 'girs'),
            degree_id='major18c',
        )

    @pytest.mark.skip(reason="Elective units/plainstring bug, known, will be solved later")
    def test_fireroad_course_18am(self):
        """Validate Course 18AM (Applied Mathematics) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major18am', 'girs'),
            degree_id='major18am',
        )

    def test_fireroad_course_7(self):
        """Validate Course 7 (Biology) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major7', 'girs'),
            degree_id='major7',
            max_semesters=10,  # Biology needs more semesters for prereq chain
        )

    def test_fireroad_course_2(self):
        """Validate Course 2 (Mechanical Engineering) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major2', 'girs'),
            degree_id='major2',
        )

    @pytest.mark.skip(reason="Elective units/plainstring bug, known, will be solved later")
    def test_fireroad_course_1(self):
        """Validate Course 1 (Civil Engineering) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major1', 'girs'),
            degree_id='major1',
        )

    @pytest.mark.skip(reason="Elective units/plainstring bug, known, will be solved later")
    def test_fireroad_course_8(self):
        """Validate Course 8 (Physics) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major8', 'girs'),
            degree_id='major8',
        )

    def test_fireroad_course_9(self):
        """Validate Course 9 (Brain and Cognitive Sciences) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major9', 'girs'),
            degree_id='major9',
        )

    @pytest.mark.skip(reason="Elective units/plainstring bug, known, will be solved later")
    def test_fireroad_course_15(self):
        """Validate Course 15 (Management) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major15-1', 'girs'),
            degree_id='major15-1',
        )

    @pytest.mark.skip(reason="Bug with direct-threshold parsing on fireroad clipig")
    def test_fireroad_course_16(self):
        """Validate Course 16 (Aerospace Engineering) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major16', 'girs'),
            degree_id='major16',
        )


    # Course 16 is not getting skipped because the skip decorator is placed
    # immediately above the test function definition, which is correct.
    # However, if pytest is not respecting the skip, check that:
    # - The decorator is not being overridden elsewhere
    # - The test function name matches exactly (pytest discovers by name)
    # - There are no indentation or syntax errors
    # - pytest is being run with the correct markers enabled/disabled
    # - The skip reason is not being ignored by a custom pytest config

    # Example: The following is correctly skipped by pytest
    # @pytest.mark.skip(reason="Bug with direct-threshold parsing on fireroad")
    # def test_fireroad_course_16(self):
    #     ...

    # If you want to ensure skipping, you can also use pytest.skip() inside the test:
    # def test_fireroad_course_16(self):
    #     pytest.skip("Bug with direct-threshold parsing on fireroad")
    #     ...

    # But in your code, the decorator is correct and should work.
    def test_fireroad_course_20(self):
        """Validate Course 20 (Biological Engineering) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major20', 'girs'),
            degree_id='major20',
        )

    def test_fireroad_course_3(self):
        """Validate Course 3 (Materials Science) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major3', 'girs'),
            degree_id='major3',
        )

    def test_fireroad_course_4(self):
        """Validate Course 4 (Architecture) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major4', 'girs'),
            degree_id='major4',
        )

    @pytest.mark.skip(reason="Elective units/plainstring bug, known, will be solved later")
    def test_fireroad_course_11(self):
        """Validate Course 11 (Urban Studies) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major11', 'girs'),
            degree_id='major11',
        )

    def test_fireroad_course_12(self):
        """Validate Course 12 (Earth Science) solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('major12', 'girs'),
            degree_id='major12',
        )


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.fireroad
class TestFireroadValidationGirsOnly:
    """
    Validate GIRs-only solutions against Fireroad.

    This tests that our GIR constraint builder matches Fireroad.
    """

    def test_fireroad_girs_only(self):
        """Validate GIRs-only solution against Fireroad."""
        run_fireroad_validation_test(
            requirement_keys=('girs',),
            degree_id='girs',
        )
