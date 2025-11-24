"""
End-to-end integration tests for the full optimizer with real degrees.

These tests verify that common degree combinations remain feasible after
the missing prerequisite fix (NewConstant(0) instead of NewConstant(1)).

Tests use the actual optimizer functions (create_take_vars, add_basic_constraints, etc.)
to mirror the real optimization flow.
"""

import polars as pl
import pytest
from ortools.sat.python import cp_model

from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.constraints.basic import add_basic_constraints, create_take_vars
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints
from tests.test_helpers import (
    assert_solution_quality,
    convert_take_vars_format,
    run_optimizer_test,
    setup_optimizer_with_objectives,
)


@pytest.mark.e2e
@pytest.mark.slow
class TestFullOptimizerE2E:
    """End-to-end tests using real optimizer flow."""

    def test_course_6_3_new_girs_feasible(self):
        """
        Test that Course 6-3 (new) + GIRs remains feasible.
        
        This is a critical test - Course 6-3 is one of the most popular majors.
        """
        # Fetch real data
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major6-3new', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        # Create model using actual optimizer functions
        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

        print(f"\n[TEST] Created {len(take_vars)} take variables")

        # Add prerequisites
        override_courses = set()
        prereq_result = add_prerequisite_constraints(
            model, take_vars, courses_df, 2024, prereq_trees, override_courses
        )
        print(f"[TEST] Prerequisite constraints: {prereq_result.constraints_added}")
        print(f"[TEST] Prerequisite warnings: {len(prereq_result.warnings)}")

        # Add requirements
        for req_key in ['major6-3new', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        aux_vars, debug_names, course_to_reqs = add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )
                        print(f"[TEST] {req_key} added (aux_vars: {len(aux_vars)})")

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        print("[TEST] Starting solve...")
        status = solver.Solve(model)
        print(f"[TEST] Solver status: {status}")

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 6-3 (new) + GIRs should be feasible, got status {status}"

    def test_course_18_girs_feasible(self):
        """
        Test that Course 18 (Math) + GIRs remains feasible.
        """
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major18pm', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

        prereq_result = add_prerequisite_constraints(
            model, take_vars, courses_df, 2024, prereq_trees, set()
        )
        print(f"\n[TEST] Prerequisite constraints: {prereq_result.constraints_added}")

        for req_key in ['major18pm', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        aux_vars, debug_names, course_to_reqs = add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)
        print(f"[TEST] Solver status: {status}")

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 18 + GIRs should be feasible, got status {status}"

    def test_course_12_with_untakeable_courses(self):
        """
        Test Course 12 (Earth Science) which references untakeable courses.
        
        Course 12 references 12.306 and 12.348 which have missing prerequisites (5.60).
        Should still be feasible due to flexible requirements.
        """
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major12', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

        prereq_result = add_prerequisite_constraints(
            model, take_vars, courses_df, 2024, prereq_trees, set()
        )
        print(f"\n[TEST] Prerequisite constraints: {prereq_result.constraints_added}")
        print(f"[TEST] Prerequisite warnings: {len(prereq_result.warnings)}")

        # Check for warnings about untakeable courses
        untakeable_warnings = [w for w in prereq_result.warnings if '12.306' in w or '12.348' in w]
        print(f"[TEST] Warnings about untakeable courses in Course 12: {len(untakeable_warnings)}")

        for req_key in ['major12', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        aux_vars, debug_names, course_to_reqs = add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)
        print(f"[TEST] Solver status: {status}")

        # Should still be feasible despite untakeable courses
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 12 should remain feasible despite untakeable courses, got status {status}"

    def test_course_2_with_2_013_prerequisites(self):
        """
        Test Course 2 (Mechanical Engineering) with 2.013.
        
        This tests that 2.013 prerequisite constraints work correctly after the fix.
        2.013 requires (2.001, 2.003, (2.005/2.051), (2.00B/2.670/2.678))
        where 2.051 is missing from the dataset.
        
        CRITICAL: This test verifies the actual bug fix - that 2.005 is taken before 2.013,
        and 2.051 (missing course) doesn't bypass the prerequisite.
        """
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        # Get course indices
        subject_ids = courses_df['subject_id'].to_list()
        course_2_013_idx = subject_ids.index('2.013') if '2.013' in subject_ids else None
        course_2_001_idx = subject_ids.index('2.001') if '2.001' in subject_ids else None
        course_2_003_idx = subject_ids.index('2.003') if '2.003' in subject_ids else None
        course_2_005_idx = subject_ids.index('2.005') if '2.005' in subject_ids else None
        course_2_00B_idx = subject_ids.index('2.00B') if '2.00B' in subject_ids else None

        if not all([course_2_013_idx, course_2_001_idx, course_2_003_idx, course_2_005_idx]):
            pytest.skip("Required courses not found in dataset")

        requirements_data = get_requirements(('major2', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

        prereq_result = add_prerequisite_constraints(
            model, take_vars, courses_df, 2024, prereq_trees, set()
        )
        print(f"\n[TEST] Prerequisite constraints: {prereq_result.constraints_added}")

        # Check for 2.051 warnings (missing course in 2.013 prereqs)
        missing_2_051_warnings = [w for w in prereq_result.warnings if '2.051' in w]
        print(f"[TEST] Warnings about missing 2.051: {len(missing_2_051_warnings)}")
        assert len(missing_2_051_warnings) > 0, "Should warn about missing 2.051"

        for req_key in ['major2', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        aux_vars, debug_names, course_to_reqs = add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)
        print(f"[TEST] Solver status: {status}")

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 2 + GIRs should be feasible, got status {status}"

        # CRITICAL VERIFICATION: Check that if 2.013 is taken, its prerequisites are satisfied
        semester_2_013_taken = None
        for semester in range(1, 9):
            if (course_2_013_idx, semester) in take_vars:
                if solver.Value(take_vars[(course_2_013_idx, semester)]) == 1:
                    semester_2_013_taken = semester
                    print(f"[TEST] 2.013 taken in semester {semester}")
                    break

        if semester_2_013_taken:
            # Verify prerequisites are taken BEFORE 2.013
            prereqs_satisfied = {
                '2.001': False,
                '2.003': False,
                '2.005_or_2.051': False,
                '2.00B_or_others': False
            }

            for semester in range(1, semester_2_013_taken):
                if (course_2_001_idx, semester) in take_vars:
                    if solver.Value(take_vars[(course_2_001_idx, semester)]) == 1:
                        prereqs_satisfied['2.001'] = True
                        print(f"[TEST] ✓ 2.001 taken in semester {semester}")

                if (course_2_003_idx, semester) in take_vars:
                    if solver.Value(take_vars[(course_2_003_idx, semester)]) == 1:
                        prereqs_satisfied['2.003'] = True
                        print(f"[TEST] ✓ 2.003 taken in semester {semester}")

                if (course_2_005_idx, semester) in take_vars:
                    if solver.Value(take_vars[(course_2_005_idx, semester)]) == 1:
                        prereqs_satisfied['2.005_or_2.051'] = True
                        print(f"[TEST] ✓ 2.005 taken in semester {semester}")

                if course_2_00B_idx and (course_2_00B_idx, semester) in take_vars:
                    if solver.Value(take_vars[(course_2_00B_idx, semester)]) == 1:
                        prereqs_satisfied['2.00B_or_others'] = True
                        print(f"[TEST] ✓ 2.00B taken in semester {semester}")

            # Verify ALL prerequisites are satisfied
            print(f"[TEST] Prerequisites satisfied: {prereqs_satisfied}")
            assert prereqs_satisfied['2.001'], "2.001 must be taken before 2.013"
            assert prereqs_satisfied['2.003'], "2.003 must be taken before 2.013"
            assert prereqs_satisfied['2.005_or_2.051'], "2.005 (or 2.051) must be taken before 2.013"
            # Note: 2.00B might not be required by all Course 2 tracks

            print("[TEST] ✅ All prerequisites correctly satisfied before 2.013!")


    def test_course_1_civil_engineering(self):
        """Test Course 1 (Civil and Environmental Engineering) remains feasible."""
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major1', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, set())

        for req_key in ['major1', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 1 + GIRs should be feasible, got status {status}"

    def test_course_6_2_eecs(self):
        """Test Course 6-2 (Electrical Engineering and Computer Science) remains feasible."""
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major6-2new', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, set())

        for req_key in ['major6-2new', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 6-2 (new) + GIRs should be feasible, got status {status}"

    def test_course_7_biology(self):
        """Test Course 7 (Biology) remains feasible.
        
        Note: Course 7 requires 10 semesters due to the prerequisite chain for 7.19
        (Biology Capstone Subject), which requires 7.06, which requires 7.03 and 7.05.
        """
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major7', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=10, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=10)

        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, set())

        for req_key in ['major7', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 7 + GIRs should be feasible, got status {status}"

    def test_course_15_management(self):
        """Test Course 15 (Management) remains feasible."""
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major15-1', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, set())

        for req_key in ['major15-1', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 15 + GIRs should be feasible, got status {status}"

    def test_double_major_6_3_and_15(self):
        """Test popular double major: Course 6-3 + Course 15 + GIRs."""
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major6-3new', 'major15-1', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        # Double major needs more semesters
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=12, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=12)

        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, set())

        for req_key in ['major6-3new', 'major15-1', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 120.0  # Double major needs more time
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Double major 6-3 + 15 + GIRs should be feasible, got status {status}"

    def test_major_with_minor(self):
        """Test Course 6-3 + Economics minor remains feasible."""
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

        requirements_data = get_requirements(('major6-3new', 'minor14', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, set())

        for req_key in ['major6-3new', 'minor14', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(
                            model, take_vars, validation.pruned_tree,
                            courses_df, 2024, enforce=True
                        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 90.0
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            f"Course 6-3 + Economics minor + GIRs should be feasible, got status {status}"

    def test_course_18c_girs_feasible(self, optimizer_config):
        """Test Course 18C (Math with Computer Science) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major18c', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_18am_girs_feasible(self, optimizer_config):
        """Test Course 18AM (Math with Applied Math) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major18am', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_3_girs_feasible(self, optimizer_config):
        """Test Course 3 (Materials Science) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major3', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_4_girs_feasible(self, optimizer_config):
        """Test Course 4 (Architecture) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major4', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_3c_girs_feasible(self, optimizer_config):
        """Test Course 3C (Archaeology and Materials) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major3c', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_3a_girs_feasible(self, optimizer_config):
        """Test Course 3A (Materials Science Flexible) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major3a', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_6_4_girs_feasible(self, optimizer_config):
        """Test Course 6-4 (AI and Decision Making) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major6-4', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    @pytest.mark.skip(reason="major6-5 does not exist in Fireroad API (400 error)")
    def test_course_6_5_girs_feasible(self, optimizer_config):
        """Test Course 6-5 (Computer Science and Molecular Biology) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major6-5', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_6_7_girs_feasible(self, optimizer_config):
        """Test Course 6-7 (Computer Science and Molecular Biology) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major6-7', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_6_9_girs_feasible(self, optimizer_config):
        """Test Course 6-9 (Computation and Cognition) + GIRs."""
        courses_data = get_courses_data()
        courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
        requirements_data = get_requirements(('major6-9', 'girs'))
        prereq_trees = get_parsed_prerequisites(courses_df)

        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, optimizer_config.start_year, max_semesters=optimizer_config.max_semesters, markers=None)
        add_basic_constraints(model, take_vars, courses_df, max_semesters=optimizer_config.max_semesters)
        add_prerequisite_constraints(model, take_vars, courses_df, optimizer_config.start_year, prereq_trees, set())

        for req_key in ['major6-9', 'girs']:
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                if isinstance(req_data, dict):
                    req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        add_requirement_constraints(model, take_vars, validation.pruned_tree, courses_df, optimizer_config.start_year, enforce=True)

        # Add objective function (mimic actual backend)
        setup_optimizer_with_objectives(model, take_vars, courses_df, optimizer_config.start_year)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = optimizer_config.solver_timeout_seconds
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], f"Course 6-9 + GIRs should be feasible, got status {status}"

        # Use test helpers for comprehensive validation
        degree_config = optimizer_config.get_config_for_degree('major6-9')
        take_vars_nested = convert_take_vars_format(take_vars)
        assert_solution_quality(
            solver,
            take_vars_nested,
            courses_df,
            prereq_trees,
            min_courses=degree_config['min_expected_courses'],
            max_courses=degree_config['max_expected_courses'],
            max_courses_per_semester=optimizer_config.max_courses_per_semester,
            max_semesters=optimizer_config.max_semesters
        )

    def test_course_6_14_girs_feasible(self, optimizer_config):
        """Test Course 6-14 (Computer Science, Economics, and Data Science) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major6-14', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_8_girs_feasible(self, optimizer_config):
        """Test Course 8 (Physics) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major8', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_9_girs_feasible(self, optimizer_config):
        """Test Course 9 (Brain and Cognitive Sciences) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major9', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_11_girs_feasible(self, optimizer_config):
        """Test Course 11 (Urban Studies and Planning) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major11', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_16_girs_feasible(self, optimizer_config):
        """Test Course 16 (Aerospace Engineering) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major16', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )

    def test_course_20_girs_feasible(self, optimizer_config):
        """Test Course 20 (Biological Engineering) + GIRs."""
        run_optimizer_test(
            requirement_keys=('major20', 'girs'),
            max_semesters=optimizer_config.max_semesters,
            start_year=optimizer_config.start_year,
            solver_timeout=optimizer_config.solver_timeout_seconds
        )


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


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
