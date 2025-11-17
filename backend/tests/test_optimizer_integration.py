"""
Integration tests for the optimizer with real-world scenarios.

These tests cover bugs we've encountered and fixed:
- ASE courses satisfying prerequisites
- Override courses not requiring prerequisites (renamed from "solo")
- Override courses NOT blocking other courses in same semester (critical bug fix)
- Pinned courses in special semesters
- Marker constraint handling
- Must Take courses satisfying prerequisites
"""

import pandas as pd
from ortools.sat.python import cp_model

from courses.prerequisites.types import PrereqCourse
from optimizer.marker_constraint_builder import Marker, add_marker_constraints
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints


def create_simple_courses_df():
    """Create a simple course catalog for testing."""
    return pd.DataFrame({
        'subject_id': ['18.01', '18.02', '8.01', '8.02', '6.100'],
        'title': ['Calculus I', 'Calculus II', 'Physics I', 'Physics II', 'Intro to CS'],
        'total_units': [12, 12, 12, 12, 12],
        'gir_attribute': ['CAL1', 'CAL2', 'PHY1', 'PHY2', None],
        'offered_fall': [True, True, True, True, True],
        'offered_spring': [True, True, True, True, True],
        'offered_IAP': [False, False, False, False, False],
    })


def create_take_vars_simple(model, courses_df, markers=None):
    """Simplified create_take_vars for testing."""
    take_vars = {}

    # Build set of courses in special semesters
    special_semester_courses = set()
    if markers:
        for marker in markers:
            if marker.section == -2:  # Must Take
                special_semester_courses.add((marker.course_id, -2))
            elif marker.section == -1:  # ASE
                special_semester_courses.add((marker.course_id, -1))

    for course_idx in courses_df.index:
        subject_id = courses_df.at[course_idx, 'subject_id']

        # Regular semesters 1-12
        for semester in range(1, 13):
            var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
            take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)

        # Special semesters only if marker exists
        if (subject_id, -2) in special_semester_courses:
            take_vars[(course_idx, -2)] = model.NewBoolVar(f"take_{subject_id.replace('.', '_')}_s-2")
        if (subject_id, -1) in special_semester_courses:
            take_vars[(course_idx, -1)] = model.NewBoolVar(f"take_{subject_id.replace('.', '_')}_s-1")

    return take_vars


class TestOptimizerIntegration:
    """Integration tests for optimizer with real scenarios."""

    def test_ase_course_with_pinned_courses(self):
        """
        Regression test: ASE course + pinned courses should be feasible.
        
        Scenario: 18.01 in ASE, 18.02 and 8.01 pinned in Freshman Fall.
        This was marked as infeasible due to semester conversion bug.
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(course_id='18.01', status='pin', section=-1),  # ASE
            Marker(course_id='18.02', status='pin', section=0),   # Freshman Fall
            Marker(course_id='8.01', status='pin', section=0),    # Freshman Fall
        ]

        take_vars = create_take_vars_simple(model, courses_df, markers)

        # Add marker constraints
        result = add_marker_constraints(model, take_vars, markers, courses_df, 2024)

        assert result.constraints_added == 3
        assert len(result.errors) == 0

        # Should be feasible
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Should be feasible with ASE + pinned courses"

    def test_ase_satisfies_prerequisite(self):
        """
        Regression test: ASE courses should satisfy prerequisites.
        
        Scenario: 18.01 as ASE should satisfy 18.02's prerequisite.
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(course_id='18.01', status='pin', section=-1),  # ASE
            Marker(course_id='18.02', status='pin', section=0),   # Freshman Fall
        ]

        take_vars = create_take_vars_simple(model, courses_df, markers)

        # Add marker constraints
        add_marker_constraints(model, take_vars, markers, courses_df, 2024)

        # Add prerequisite: 18.02 requires 18.01
        prereq_trees = {0: PrereqCourse('18.01')}  # course_idx 0 is 18.01, but we want 18.02
        # Find 18.02 index
        course_18_02_idx = courses_df.index[courses_df['subject_id'] == '18.02'].tolist()[0]
        prereq_trees = {course_18_02_idx: PrereqCourse('18.01')}

        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees)

        # Should be feasible
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], "ASE should satisfy prerequisite"

    def test_override_course_ignores_prerequisites(self):
        """
        Regression test: Override courses should not require prerequisites.
        
        Scenario: 18.02 marked as override should not need 18.01.
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(course_id='18.02', status='override', section=0),  # Freshman Fall, override
        ]

        take_vars = create_take_vars_simple(model, courses_df, markers)

        # Add marker constraints
        add_marker_constraints(model, take_vars, markers, courses_df, 2024)

        # Add prerequisite: 18.02 requires 18.01
        course_18_02_idx = courses_df.index[courses_df['subject_id'] == '18.02'].tolist()[0]
        prereq_trees = {course_18_02_idx: PrereqCourse('18.01')}

        # Pass override courses to skip prerequisite checking
        override_course_ids = {'18.02'}
        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, override_course_ids)

        # Should be feasible even without 18.01
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Override course should ignore prerequisites"

    def test_must_take_satisfies_prerequisite(self):
        """
        Test: Must Take courses should satisfy prerequisites.
        
        Scenario: Course in Must Take section should satisfy prerequisites for later courses.
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(course_id='18.01', status='pin', section=-2),  # Must Take
            Marker(course_id='18.02', status='pin', section=0),   # Freshman Fall
        ]

        take_vars = create_take_vars_simple(model, courses_df, markers)

        # Add marker constraints
        add_marker_constraints(model, take_vars, markers, courses_df, 2024)

        # Add prerequisite: 18.02 requires 18.01
        course_18_02_idx = courses_df.index[courses_df['subject_id'] == '18.02'].tolist()[0]
        prereq_trees = {course_18_02_idx: PrereqCourse('18.01')}

        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees)

        # Should be feasible
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Must Take should satisfy prerequisite"

    def test_banish_prevents_specific_semester_only(self):
        """
        Regression test: Banish should only prevent course in specific semester.
        
        Scenario: 18.01 banished from Freshman Fall should still be takeable in Freshman Spring.
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(course_id='18.01', status='banish', section=0),  # Banish from Freshman Fall
        ]

        take_vars = create_take_vars_simple(model, courses_df, markers)

        # Add marker constraints
        result = add_marker_constraints(model, take_vars, markers, courses_df, 2024)

        assert result.constraints_added == 1

        # Force taking the course in another semester
        course_18_01_idx = courses_df.index[courses_df['subject_id'] == '18.01'].tolist()[0]
        model.Add(take_vars[(course_18_01_idx, 2)] == 1)  # Freshman Spring

        # Should be feasible
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], "Banish should only block specific semester"

    def test_optimizer_doesnt_place_in_special_semesters(self):
        """
        Regression test: Optimizer should not place courses in special semesters.
        
        Scenario: Without markers, optimizer should not use special semesters.
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        # No markers - so no special semester vars should be created
        take_vars = create_take_vars_simple(model, courses_df, markers=None)

        # Check that no special semester vars exist
        for (course_idx, semester), var in take_vars.items():
            assert semester >= 1, f"Found variable for semester {semester}, should only have regular semesters"

        # Force taking at least one course
        model.Add(sum(take_vars.values()) >= 1)

        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Verify solution doesn't use special semesters
        for (course_idx, semester), var in take_vars.items():
            if solver.Value(var) == 1:
                assert semester >= 1, f"Optimizer placed course in semester {semester}"

    def test_override_does_not_block_other_courses(self):
        """
        REGRESSION TEST: Override markers should NOT prevent other courses in same semester.
        
        This was a critical bug - the old implementation forced all other courses
        in the semester to be 0. Override should ONLY:
        1. Pin the course to that semester
        2. Skip prerequisite checking
        
        It should NOT prevent other courses from being in that semester.
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        # Override 18.02 in Freshman Fall AND pin 18.01 in Freshman Fall
        # Both should be able to coexist in the same semester
        markers = [
            Marker(course_id='18.02', status='override', section=0),  # Freshman Fall
            Marker(course_id='18.01', status='pin', section=0),       # Freshman Fall
        ]

        take_vars = create_take_vars_simple(model, courses_df, markers)

        # Add marker constraints
        result = add_marker_constraints(model, take_vars, markers, courses_df, 2024)

        # Should add exactly 2 constraints (one per marker)
        assert result.constraints_added == 2, f"Expected 2 constraints, got {result.constraints_added}"
        assert len(result.errors) == 0, f"Should have no errors, got {result.errors}"

        # Should be feasible - both courses can be in semester 1
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Override should NOT block other courses in same semester"

        # Verify both courses are actually in semester 1
        course_18_01_idx = courses_df.index[courses_df['subject_id'] == '18.01'].tolist()[0]
        course_18_02_idx = courses_df.index[courses_df['subject_id'] == '18.02'].tolist()[0]

        assert solver.Value(take_vars[(course_18_01_idx, 1)]) == 1, "18.01 should be in semester 1"
        assert solver.Value(take_vars[(course_18_02_idx, 1)]) == 1, "18.02 should be in semester 1"

    def test_override_allows_multiple_courses_in_semester(self):
        """
        REGRESSION TEST: Override with 3+ courses in same semester.
        
        Verifies that override truly doesn't block other courses.
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        # Put 3 courses in Freshman Fall, one is override
        markers = [
            Marker(course_id='18.01', status='pin', section=0),
            Marker(course_id='18.02', status='override', section=0),  # Override
            Marker(course_id='8.01', status='pin', section=0),
        ]

        take_vars = create_take_vars_simple(model, courses_df, markers)
        result = add_marker_constraints(model, take_vars, markers, courses_df, 2024)

        assert result.constraints_added == 3
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Should be feasible to have multiple courses with override in semester"

        # Verify all 3 courses are in semester 1
        course_18_01_idx = courses_df.index[courses_df['subject_id'] == '18.01'].tolist()[0]
        course_18_02_idx = courses_df.index[courses_df['subject_id'] == '18.02'].tolist()[0]
        course_8_01_idx = courses_df.index[courses_df['subject_id'] == '8.01'].tolist()[0]

        assert solver.Value(take_vars[(course_18_01_idx, 1)]) == 1
        assert solver.Value(take_vars[(course_18_02_idx, 1)]) == 1
        assert solver.Value(take_vars[(course_8_01_idx, 1)]) == 1

    def test_override_skips_prerequisites_but_pins_semester(self):
        """
        REGRESSION TEST: Override should skip prereq checking AND pin to semester.
        
        Verifies both behaviors work correctly:
        1. Course is pinned to specified semester
        2. Prerequisite checking is skipped for that course
        """
        courses_df = create_simple_courses_df()
        model = cp_model.CpModel()

        # 18.02 requires 18.01, but we mark 18.02 as override in Freshman Fall
        # WITHOUT taking 18.01 first (or at all)
        markers = [
            Marker(course_id='18.02', status='override', section=0),  # Freshman Fall, no prereqs needed
        ]

        take_vars = create_take_vars_simple(model, courses_df, markers)

        # Add marker constraints
        add_marker_constraints(model, take_vars, markers, courses_df, 2024)

        # Add prerequisite: 18.02 requires 18.01
        course_18_02_idx = courses_df.index[courses_df['subject_id'] == '18.02'].tolist()[0]
        prereq_trees = {course_18_02_idx: PrereqCourse('18.01')}

        # Pass override courses to skip prerequisite checking
        override_course_ids = {'18.02'}
        add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, override_course_ids)

        # Should be feasible even without 18.01
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Override should skip prerequisite checking"

        # Verify 18.02 is in semester 1 (pinned)
        assert solver.Value(take_vars[(course_18_02_idx, 1)]) == 1, \
            "Override should pin course to specified semester"

        # Verify 18.01 is NOT required to be taken
        course_18_01_idx = courses_df.index[courses_df['subject_id'] == '18.01'].tolist()[0]
        total_18_01 = sum(
            solver.Value(take_vars[(course_18_01_idx, s)])
            for s in range(1, 13)
            if (course_18_01_idx, s) in take_vars
        )
        # 18.01 doesn't need to be taken (could be 0 or 1, we don't force it)
