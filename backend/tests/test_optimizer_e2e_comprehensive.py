"""
Comprehensive end-to-end integration tests for the optimizer.

These tests use a standardized framework to ensure:
1. Degrees are feasible with realistic parameters
2. Solutions have reasonable course counts
3. Prerequisites are properly satisfied
4. Semester distributions are realistic
5. All edge cases from bug reports are covered

This replaces the simple feasibility-only tests with comprehensive validation.
"""

import polars as pl
from ortools.sat.python import cp_model

from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.constraints.basic import add_basic_constraints, create_take_vars
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints

from .test_helpers import assert_solution_quality


class TestOptimizerE2EComprehensive:
    """Comprehensive E2E tests with quality validation."""

    def _test_degree_with_girs(
        self,
        degree_id: str,
        optimizer_config,
        expected_feasible: bool = True
    ):
        """
        Standard test template for degree + GIRs feasibility and quality.

        This template ensures all tests validate:
        - Feasibility
        - Course count within reasonable range
        - Prerequisite satisfaction
        - Semester distribution

        Args:
            degree_id: Degree requirement key (e.g., 'major6-3new')
            optimizer_config: Test configuration fixture
            expected_feasible: Whether we expect a feasible solution
        """
        # Get degree-specific configuration
        degree_config = optimizer_config.get_config_for_degree(degree_id)
        max_semesters = degree_config['max_semesters']
        min_courses = degree_config['min_expected_courses']
        max_courses = degree_config['max_expected_courses']

        print(f"\n[TEST] Testing {degree_id} ({degree_config['description']})")
        print(f"[TEST] Expected {min_courses}-{max_courses} courses over {max_semesters} semesters")

        # Load real data
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
        requirements_data = get_requirements((degree_id, 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        # Build optimization model
        model = cp_model.CpModel()
        take_vars = create_take_vars(
            model, courses_df, optimizer_config.start_year,
            max_semesters=max_semesters, markers=None
        )
        add_basic_constraints(model, take_vars, courses_df, max_semesters=max_semesters)
        add_prerequisite_constraints(
            model, take_vars, courses_df, optimizer_config.start_year,
            prereq_trees, set()
        )

        # Add degree requirements
        for req_key in [degree_id, 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({
                        'reqs': req_data.get('reqs', []),
                        'title': req_key
                    })
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, optimizer_config.start_year, enforce=True
                        )

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = optimizer_config.solver_timeout_seconds
        status = solver.Solve(model)

        print(f"[TEST] Solver status: {status}")

        # Validate result
        if expected_feasible:
            assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
                f"{degree_id} + GIRs should be feasible, got status {status}"

            # Comprehensive quality checks
            assert_solution_quality(
                solver=solver,
                take_vars=take_vars,
                courses_df=courses_df,
                prereq_trees=prereq_trees,
                min_courses=min_courses,
                max_courses=max_courses,
                max_courses_per_semester=optimizer_config.max_courses_per_semester,
                max_semesters=max_semesters
            )

            print(f"[TEST] ✅ {degree_id} passes all quality checks")
        else:
            assert status == cp_model.INFEASIBLE, \
                f"{degree_id} should be infeasible, got status {status}"
            print(f"[TEST] ✅ {degree_id} correctly marked as infeasible")

    def test_course_6_3_computer_science(self, optimizer_config):
        """Test Course 6-3 (Computer Science + EE) with GIRs."""
        self._test_degree_with_girs('major6-3new', optimizer_config)

    def test_course_7_biology(self, optimizer_config):
        """
        Test Course 7 (Biology) with GIRs.

        Regression test: Course 7 requires 10 semesters due to
        prerequisite chain for 7.19 (Biology Capstone).
        """
        self._test_degree_with_girs('major7', optimizer_config)

    def test_course_18_mathematics(self, optimizer_config):
        """Test Course 18 (Mathematics) with GIRs."""
        self._test_degree_with_girs('major18', optimizer_config)

    def test_course_1_civil_engineering(self, optimizer_config):
        """
        Test Course 1 (Civil Engineering) with GIRs.

        Regression test: Course 1.091 has 'Permission of instructor'
        which should not block feasibility.
        """
        self._test_degree_with_girs('major1', optimizer_config)

    def test_course_2_mechanical_engineering(self, optimizer_config):
        """Test Course 2 (Mechanical Engineering) with GIRs."""
        self._test_degree_with_girs('major2', optimizer_config)

    def test_course_6_2_eecs(self, optimizer_config):
        """Test Course 6-2 (EECS) with GIRs."""
        self._test_degree_with_girs('major6-2new', optimizer_config)

    def test_course_15_management(self, optimizer_config):
        """Test Course 15 (Management) with GIRs."""
        self._test_degree_with_girs('major15-1', optimizer_config)

    def test_double_major_6_3_and_15(self, optimizer_config):
        """
        Test double major: Course 6-3 + Course 15.

        This should be feasible but require more semesters.
        """
        degree_ids = ['major6-3new', 'major15-1']

        # Double major needs more semesters
        max_semesters = 12
        min_courses = 30
        max_courses = 45

        print("\n[TEST] Testing double major: 6-3 + 15")
        print(f"[TEST] Expected {min_courses}-{max_courses} courses over {max_semesters} semesters")

        # Load data
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
        requirements_data = get_requirements(tuple(degree_ids + ['girs']))
        prereq_trees = get_parsed_prerequisites(courses_df)

        # Build model
        model = cp_model.CpModel()
        take_vars = create_take_vars(
            model, courses_df, optimizer_config.start_year,
            max_semesters=max_semesters, markers=None
        )
        add_basic_constraints(model, take_vars, courses_df, max_semesters=max_semesters)
        add_prerequisite_constraints(
            model, take_vars, courses_df, optimizer_config.start_year,
            prereq_trees, set()
        )

        # Add both degree requirements + GIRs
        for req_key in degree_ids + ['girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({
                        'reqs': req_data.get('reqs', []),
                        'title': req_key
                    })
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, optimizer_config.start_year, enforce=True
                        )

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = optimizer_config.solver_timeout_seconds
        status = solver.Solve(model)

        print(f"[TEST] Solver status: {status}")

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Double major 6-3 + 15 should be feasible, got status {status}"

        # Quality checks
        assert_solution_quality(
            solver=solver,
            take_vars=take_vars,
            courses_df=courses_df,
            prereq_trees=prereq_trees,
            min_courses=min_courses,
            max_courses=max_courses,
            max_courses_per_semester=optimizer_config.max_courses_per_semester,
            max_semesters=max_semesters
        )

        print("[TEST] ✅ Double major passes all quality checks")


class TestRegressionBugs:
    """
    Regression tests for specific bugs found during development.

    These tests should never be removed - they document and prevent
    regressions of critical bugs.
    """

    def test_regression_course_1_091_permission_of_instructor(self):
        """
        Regression test: Course 1.091 with 'Permission of instructor' prerequisite.

        Bug: Parser returned PrereqGroup(threshold=0, items=()) which was treated
        as unsatisfiable, making Course 1 infeasible with 6+ courses.

        Fix: Parser now returns None for unparseable prerequisites.
        """
        from courses.prerequisites.parser import parse_fireroad

        # Test 1: Parser returns None for unparseable prerequisites
        result = parse_fireroad("''Permission of instructor''")
        assert result is None, \
            "Parser should return None for 'Permission of instructor'"

        # Test 2: Course 1 should be feasible (integration test would go here)
        # This is covered by test_course_1_civil_engineering above

    def test_regression_course_7_requires_10_semesters(self, optimizer_config):
        """
        Regression test: Course 7 requires 10 semesters, not 8.

        Bug: Test used max_semesters=8 but Course 7.19 (Biology Capstone)
        has prerequisite chain 7.19 → 7.06 → (7.03, 7.05) requiring 10 semesters.

        Fix: Updated test configuration to use 10 semesters for Course 7.
        """
        degree_config = optimizer_config.get_config_for_degree('major7')

        assert degree_config['max_semesters'] >= 10, \
            "Course 7 configuration must allow at least 10 semesters"

        print(f"[TEST] ✅ Course 7 correctly configured for {degree_config['max_semesters']} semesters")

    def test_regression_empty_prereq_groups_never_created(self):
        """
        Regression test: Parser should never create empty PrereqGroups.

        Bug: Empty groups were treated as unsatisfiable.

        Fix: Parser returns None instead.
        """
        from courses.prerequisites.parser import parse_fireroad
        from courses.prerequisites.types import PrereqGroup

        test_cases = [
            "",
            "   ",
            "''permission of instructor''",
            "''Permission required''",
        ]

        for test_str in test_cases:
            result = parse_fireroad(test_str)

            # Should be None, not an empty group
            if result is not None:
                assert not (isinstance(result, PrereqGroup) and len(result.items) == 0), \
                    f"Parser should not return empty PrereqGroup for '{test_str}'"

        print("[TEST] ✅ Parser never returns empty PrereqGroups")
