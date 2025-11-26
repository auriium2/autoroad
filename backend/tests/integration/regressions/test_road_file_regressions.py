"""
Regression tests using .road files.

This module provides a testing harness for .road files that have failed in the past.
Each test case loads a .road file (which contains markers representing a user's
existing course selections) and verifies that the optimizer can still find a
feasible, quality solution.

To add a new regression test:
1. Save the failing .road file to tests/fixtures/road_files/
2. Add a test case below using the _test_road_file helper

.road file format:
{
    "coursesOfStudy": ["major6-3new", "girs"],
    "selectedSubjects": [
        {"subject_id": "6.100A", "semester": 1, ...},
        ...
    ],
    "progressAssertions": {}
}
"""

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from ortools.sat.python import cp_model

from api.models.requests import Marker
from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
from courses.requirements.parser import parse_fireroad_response
from courses.requirements.validator import validate_and_prune
from optimizer.constraints.basic import add_basic_constraints, create_take_vars
from optimizer.marker_constraint_builder import add_marker_constraints
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirements.builder import add_requirement_constraints
from tests.conftest import OptimizerTestConfig
from tests.test_helpers import setup_optimizer_with_objectives

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "road_files"


def graduation_year_to_start_year(graduation_year: int) -> int:
    """
    Convert graduation year to planning start year.
    
    Matches frontend logic: graduationYearToPlanningYear
    Class of 2028 -> freshman fall 2024 -> start_year = 2024
    """
    return graduation_year - 4


def load_road_file(filename: str) -> dict[str, Any]:
    """Load a .road file from the fixtures directory."""
    path = FIXTURES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Road file not found: {path}")
    with open(path) as f:
        return json.load(f)


def road_to_markers(road_data: dict[str, Any]) -> list[Marker]:
    """
    Convert a .road file's selectedSubjects to Marker objects.

    In .road files, selectedSubjects represent courses the user has already
    placed. We convert these to markers to lock them in place.

    .road file semester mapping:
    - semester 0: ASE (prior credit) -> section -1
    - semester 1-12: regular semesters -> section 0-11

    .road file overrideWarnings mapping:
    - overrideWarnings=True -> status="override" (skip prerequisite checking)
    - overrideWarnings=False -> status="pin"
    """
    markers = []
    for subject in road_data.get("selectedSubjects", []):
        subject_id = subject.get("subject_id")
        semester = subject.get("semester")
        if subject_id and semester is not None:
            # Convert .road semester to marker section
            # .road uses: 0=ASE, 1-12=regular semesters
            # markers use: -1=ASE, 0-11=regular semesters
            if semester == 0:
                section = -1  # ASE
            else:
                section = semester - 1  # Regular semesters: 1->0, 2->1, etc.

            # overrideWarnings=True means skip prerequisite checking
            status = "override" if subject.get("overrideWarnings", False) else "pin"

            markers.append(Marker(
                courseId=subject_id,
                section=section,
                status=status
            ))
    return markers


def get_requirements_from_road(road_data: dict[str, Any]) -> tuple[str, ...]:
    """Extract requirement keys from a .road file."""
    courses_of_study = road_data.get("coursesOfStudy", [])
    if not courses_of_study:
        # Default to major6-3new + girs if not specified
        return ("major6-3new", "girs")
    return tuple(courses_of_study)


@pytest.mark.slow
class TestRoadFileRegressions:
    """Regression tests using .road files that have failed in the past."""

    def _test_road_file(
        self,
        filename: str,
        optimizer_config: OptimizerTestConfig,
        graduation_year: int,
        min_courses: int = 20,
        max_courses: int = 50,
        min_objective_value: int | None = None,
        max_objective_value: int | None = None,
        expected_feasible: bool = True,
        description: str = ""
    ):
        """
        Test harness for .road file regression tests.

        Args:
            filename: Name of the .road file in fixtures/road_files/
            optimizer_config: Test configuration fixture
            graduation_year: Graduation year (e.g., 2028 for Class of 2028)
            min_courses: Minimum expected courses in solution
            max_courses: Maximum expected courses in solution
            min_objective_value: Minimum acceptable objective value (default from config)
            max_objective_value: Maximum acceptable objective value (default from config)
            expected_feasible: Whether we expect a feasible solution
            description: Human-readable description of the test case
        """
        # Use config defaults if not specified
        if min_objective_value is None:
            min_objective_value = optimizer_config.min_objective_value
        if max_objective_value is None:
            max_objective_value = optimizer_config.max_objective_value
        print(f"\n[TEST] Testing .road file: {filename}")
        if description:
            print(f"[TEST] Description: {description}")

        # Load road file
        road_data = load_road_file(filename)
        markers = road_to_markers(road_data)
        requirement_keys = get_requirements_from_road(road_data)

        print(f"[TEST] Requirements: {requirement_keys}")
        print(f"[TEST] Markers from .road file: {len(markers)}")
        for m in markers:
            print(f"[TEST]   Marker: {m.courseId} section={m.section} status={m.status}")

        # Load real data
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
        requirements_data = get_requirements(requirement_keys)
        prereq_trees = get_parsed_prerequisites(courses_df)

        # Build optimization model
        model = cp_model.CpModel()
        max_semesters = optimizer_config.max_semesters
        start_year = graduation_year_to_start_year(graduation_year)

        take_vars = create_take_vars(
            model, courses_df, start_year,
            max_semesters=max_semesters, markers=markers
        )
        add_basic_constraints(model, take_vars, courses_df, max_semesters=max_semesters)

        # Add requirement constraints (must come before prereqs, matching backend order)
        for req_key in requirement_keys:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_fireroad_response(req_data)
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, req_key, enforce=True
                        )

        # Add prerequisite constraints (override courses skip prereqs)
        override_course_ids = {m.courseId for m in markers if m.status == 'override'}
        add_prerequisite_constraints(
            model, take_vars, courses_df, start_year,
            prereq_trees, override_course_ids
        )

        # Add marker constraints (must come after requirements and prereqs, matching backend order)
        marker_result = add_marker_constraints(model, take_vars, markers, courses_df, start_year)
        print(f"[TEST] Marker constraints added: {marker_result.constraints_added}")
        if marker_result.warnings:
            print(f"[TEST] Marker warnings: {marker_result.warnings}")
        if marker_result.errors:
            print(f"[TEST] Marker errors: {marker_result.errors}")

        # Add objectives
        setup_optimizer_with_objectives(model, take_vars, courses_df, start_year)

        # Solve
        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        print(f"[TEST] Solver status: {status}")

        if expected_feasible:
            assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
                f"Expected feasible solution for {filename}, got status {status}"

            # Count courses taken
            courses_taken = 0
            for (course_idx, semester), var in take_vars.items():
                if solver.Value(var) == 1:
                    courses_taken += 1

            print(f"[TEST] Courses in solution: {courses_taken}")

            assert min_courses <= courses_taken <= max_courses, \
                f"Expected {min_courses}-{max_courses} courses, got {courses_taken}"

            # Check objective value is in reasonable range
            objective_value = solver.ObjectiveValue()
            print(f"[TEST] Objective value: {objective_value}")

            assert objective_value >= min_objective_value, \
                f"Objective value {objective_value} is below minimum {min_objective_value}"
            assert objective_value <= max_objective_value, \
                f"Objective value {objective_value} is above maximum {max_objective_value}"

            print(f"[TEST] ✅ {filename} passed")
        else:
            assert status == cp_model.INFEASIBLE, \
                f"Expected infeasible for {filename}, got status {status}"
            print(f"[TEST] ✅ {filename} correctly infeasible")

    # =========================================================================
    # Add regression tests below. Each test loads a .road file that previously
    # caused issues and verifies the optimizer handles it correctly.
    # =========================================================================

    def test_example_placeholder(self, optimizer_config: OptimizerTestConfig):
        """
        Placeholder test - remove this when adding real regression tests.

        To add a real test:
        1. Save the .road file to tests/fixtures/road_files/your_file.road
        2. Add a test method like:

            def test_your_regression_case(self, optimizer_config):
                self._test_road_file(
                    filename="your_file.road",
                    optimizer_config=optimizer_config,
                    min_courses=20,
                    max_courses=35,
                    description="Description of what this test verifies"
                )
        """
        # Skip this placeholder test
        pytest.skip("Placeholder test - add real .road file regression tests")

    def test_autoroad3_equivalent_courses_bug(self, optimizer_config: OptimizerTestConfig):
        """
        Regression test for equivalent courses penalty not being avoided.
        
        The optimizer was choosing to take equivalent courses despite the 50,000+ 
        penalty, indicating the equivalent courses constraint is broken.
        
        Root cause: The requirement_constraint_builder was only checking semesters 1-12,
        not ASE semester (-1). So courses placed in ASE weren't satisfying requirements,
        forcing the optimizer to take equivalent courses to satisfy GIRs.
        
        Fix: Changed range(1, 13) to VALID_SEMESTERS (which is [-1] + list(range(1, 13)))
        in _build_course, _build_hass_any, and _build_attribute_requirement.
        """
        self._test_road_file(
            filename="autoroad-3.road",
            optimizer_config=optimizer_config,
            graduation_year=2028,
            min_courses=16,
            max_courses=50,
            description="Test that ASE courses satisfy requirements and equivalent penalty is avoided"
        )
