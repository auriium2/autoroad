"""
Tests for the prerequisite constraint builder.
"""

import polars as pl
from ortools.sat.python import cp_model

from courses.prerequisites.types import PrereqCourse, PrereqGroup
from optimizer.prerequisite_constraint_builder import (
    ConstraintContext,
    CourseSchedule,
    PrerequisiteConstraintBuilder,
    add_prerequisite_constraints,
)


class TestCourseSchedule:
    """Tests for CourseSchedule helper class."""

    def test_get_course_index(self):
        """Test looking up course index by course ID."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B', '18.01'],
            'gir_attribute': [None, None, 'CAL1'],
        })
        schedule = CourseSchedule(df, 2024)

        assert schedule.get_course_index('6.100A') == 0
        assert schedule.get_course_index('18.01') == 2
        assert schedule.get_course_index('MISSING') is None

    def test_get_courses_by_gir(self):
        """Test finding courses by GIR attribute."""
        df = pl.DataFrame({
            'subject_id': ['18.01', '18.02', '6.100A'],
            'gir_attribute': ['CAL1', 'CAL2', None],
        })
        schedule = CourseSchedule(df, 2024)

        cal1_courses = schedule.get_courses_by_gir('CAL1')
        assert cal1_courses == [0]

        cal2_courses = schedule.get_courses_by_gir('CAL2')
        assert cal2_courses == [1]

    def test_get_courses_by_hass(self):
        """Test finding courses by HASS attribute."""
        df = pl.DataFrame({
            'subject_id': ['21M.011', '21H.102', '6.100A'],
            'hass_attribute': ['HASS-A', 'HASS-H', None],
        })
        schedule = CourseSchedule(df, 2024)

        hass_a_courses = schedule.get_courses_by_hass('HASS-A')
        assert hass_a_courses == [0]


class TestPrerequisiteConstraintBuilder:
    """Tests for PrerequisiteConstraintBuilder."""

    def test_simple_course_prereq(self):
        """Test a simple prerequisite: course A requires course B."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for both courses in semesters 1-3
        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # Course 0 (6.100A) requires Course 1 (6.100B)
        prereq_tree = PrereqCourse("6.100B")
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        # Should add 3 constraints (one per semester for course 0)
        assert result.constraints_added == 3
        assert not result.has_issues

    def test_gir_prereq(self):
        """Test a GIR prerequisite: course requires GIR:CAL1."""
        df = pl.DataFrame({
            'subject_id': ['8.01', '18.01', '18.02'],
            'gir_attribute': [None, 'CAL1', 'CAL2'],
            'hass_attribute': [None, None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables
        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # Course 0 (8.01) requires GIR:CAL1
        prereq_tree = PrereqCourse("GIR:CAL1")
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        assert result.constraints_added == 3
        assert not result.has_issues

    def test_hass_prereq(self):
        """Test a HASS prerequisite: course requires HASS:A."""
        df = pl.DataFrame({
            'subject_id': ['6.UAT', '21M.011', '21H.102'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, 'HASS-A', 'HASS-H'],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # Course 0 requires HASS:A (which is HASS-A in the database)
        prereq_tree = PrereqCourse("HASS:HASS-A")
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        assert result.constraints_added == 3
        assert not result.has_issues

    def test_and_prereq(self):
        """Test AND prerequisite: course requires A AND B."""
        df = pl.DataFrame({
            'subject_id': ['6.1010', '6.100A', '6.100B'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # Course 0 requires both Course 1 AND Course 2
        prereq_tree = PrereqGroup(
            threshold=2,  # Both required
            items=(PrereqCourse("6.100A"), PrereqCourse("6.100B"))
        )
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        assert result.constraints_added == 3
        assert not result.has_issues

    def test_or_prereq(self):
        """Test OR prerequisite: course requires A OR B."""
        df = pl.DataFrame({
            'subject_id': ['6.1010', '6.100A', '6.100B'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # Course 0 requires Course 1 OR Course 2
        prereq_tree = PrereqGroup(
            threshold=1,  # One required
            items=(PrereqCourse("6.100A"), PrereqCourse("6.100B"))
        )
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        assert result.constraints_added == 3
        assert not result.has_issues

    def test_missing_course_warning(self):
        """Test that missing prerequisite courses generate warnings."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_6.100A_s{semester}")

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # Course 0 requires a course that doesn't exist
        prereq_tree = PrereqCourse("MISSING.COURSE")
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        # Should still add constraints, but with warnings
        assert result.constraints_added == 3
        assert len(result.warnings) > 0
        assert "MISSING.COURSE" in result.warnings[0]


class TestAddPrerequisiteConstraints:
    """Tests for the convenience function."""

    def test_add_prerequisite_constraints(self):
        """Test the top-level function for adding constraints."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        # Course 0 requires Course 1
        prereq_trees = {0: PrereqCourse("6.100B")}

        result = add_prerequisite_constraints(
            model, take_vars, df, 2024, prereq_trees
        )

        assert result.constraints_added == 3
        assert not result.has_issues


class TestASEAndMustTake:
    """Tests for ASE and Must Take special semesters."""

    def test_ase_satisfies_prereq(self):
        """Test that ASE courses (semester -1) can satisfy prerequisites."""
        df = pl.DataFrame({
            'subject_id': ['8.02', '8.01'],
            'gir_attribute': [None, 'PHY1'],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for 8.01 in ASE semester (-1)
        take_vars[(1, -1)] = model.NewBoolVar("take_8.01_s-1")

        # Create take variables for 8.02 in regular semesters
        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_8.02_s{semester}")

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # 8.02 requires 8.01
        prereq_trees = {0: PrereqCourse("8.01")}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        # Should add 3 constraints (one per semester for 8.02)
        assert result.constraints_added == 3
        assert not result.has_issues

        # Solve to verify: if 8.01 is taken as ASE, then 8.02 can be taken in semester 1
        model.Add(take_vars[(1, -1)] == 1)  # Take 8.01 as ASE
        model.Add(take_vars[(0, 1)] == 1)   # Take 8.02 in semester 1

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status == cp_model.OPTIMAL or status == cp_model.FEASIBLE

    def test_must_take_satisfies_prereq(self):
        """Test that Must Take courses (semester -2) can satisfy prerequisites."""
        df = pl.DataFrame({
            'subject_id': ['6.100B', '6.100A'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for 6.100A in Must Take semester (-2)
        take_vars[(1, -2)] = model.NewBoolVar("take_6.100A_s-2")

        # Create take variables for 6.100B in regular semesters
        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_6.100B_s{semester}")

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # 6.100B requires 6.100A
        prereq_trees = {0: PrereqCourse("6.100A")}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        assert result.constraints_added == 3
        assert not result.has_issues

        # Solve to verify: if 6.100A is in Must Take, then 6.100B can be taken in semester 1
        model.Add(take_vars[(1, -2)] == 1)  # Mark 6.100A as Must Take
        model.Add(take_vars[(0, 1)] == 1)   # Take 6.100B in semester 1

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status == cp_model.OPTIMAL or status == cp_model.FEASIBLE

    def test_ase_no_prereq_constraints_added(self):
        """Test that ASE courses don't have prerequisite constraints added."""
        df = pl.DataFrame({
            'subject_id': ['8.02', '8.01'],
            'gir_attribute': [None, 'PHY1'],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for both courses in ASE semester (-1)
        for course_idx in range(2):
            take_vars[(course_idx, -1)] = model.NewBoolVar(
                f"take_{df[course_idx, 'subject_id']}_s-1"
            )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # 8.02 requires 8.01
        prereq_trees = {0: PrereqCourse("8.01")}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        # No constraints should be added since we only iterate semesters 1-12
        assert result.constraints_added == 0
        assert not result.has_issues

    def test_ase_gir_satisfies_prereq(self):
        """Test that ASE courses with GIR attributes can satisfy GIR prerequisites."""
        df = pl.DataFrame({
            'subject_id': ['8.02', '18.01'],
            'gir_attribute': [None, 'CAL1'],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for 18.01 in ASE semester (-1)
        take_vars[(1, -1)] = model.NewBoolVar("take_18.01_s-1")

        # Create take variables for 8.02 in regular semesters
        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_8.02_s{semester}")

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # 8.02 requires GIR:CAL1
        prereq_trees = {0: PrereqCourse("GIR:CAL1")}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        assert result.constraints_added == 3
        assert not result.has_issues

        # Solve to verify: if 18.01 is taken as ASE, then 8.02 can be taken in semester 1
        model.Add(take_vars[(1, -1)] == 1)  # Take 18.01 as ASE
        model.Add(take_vars[(0, 1)] == 1)   # Take 8.02 in semester 1

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status == cp_model.OPTIMAL or status == cp_model.FEASIBLE

    def test_override_courses_skip_prereq_constraints(self):
        """Test that override courses don't have prerequisite constraints added."""
        df = pl.DataFrame({
            'subject_id': ['8.02', '8.01'],
            'gir_attribute': [None, 'PHY1'],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for both courses
        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        # 8.02 requires 8.01, but 8.02 is marked as override
        prereq_trees = {0: PrereqCourse("8.01")}
        override_course_ids = {'8.02'}

        result = add_prerequisite_constraints(
            model, take_vars, df, 2024, prereq_trees, override_course_ids
        )

        # No constraints should be added since 8.02 is override
        assert result.constraints_added == 0
        assert not result.has_issues


class TestComplexPrerequisites:
    """Tests for complex prerequisite scenarios that have caused bugs."""

    def test_missing_course_returns_unsatisfied(self):
        """
        Unit test: Missing courses should return NewConstant(0) (unsatisfied).
        
        This is the core fix for the 2.013 bug.
        """
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_6.100A_s{semester}")

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # Course 0 requires a course that doesn't exist
        prereq_tree = PrereqCourse("MISSING.COURSE")
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)

        # Should add constraints and generate warnings
        assert result.constraints_added == 3
        assert len(result.warnings) == 3  # One per semester
        assert "MISSING.COURSE" in result.warnings[0]

        # Try to take the course - should be INFEASIBLE
        model.Add(take_vars[(0, 1)] == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Must be infeasible - cannot take course with missing prerequisite
        assert status == cp_model.INFEASIBLE, \
            "Course with missing prerequisite should be untakeable"

    def test_missing_course_in_or_group_forces_alternative(self):
        """
        Regression test: Missing course in OR group should force the alternative.
        
        This is the 2.013 bug scenario: (2.005 OR 2.051) where 2.051 is missing.
        Should force taking 2.005.
        """
        df = pl.DataFrame({
            'subject_id': ['ADVANCED', 'PREREQ_A'],  # PREREQ_B doesn't exist at all
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables
        for course_idx in range(2):
            for semester in range(1, 5):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # ADVANCED requires (PREREQ_A OR PREREQ_B_MISSING)
        # PREREQ_B_MISSING doesn't exist in the dataset
        prereq_tree = PrereqGroup(
            threshold=1,
            items=(PrereqCourse("PREREQ_A"), PrereqCourse("PREREQ_B_MISSING"))
        )
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)
        assert result.constraints_added == 4
        assert len(result.warnings) > 0  # Warning about PREREQ_B_MISSING
        assert "PREREQ_B_MISSING" in result.warnings[0]

        # Test 1: Try to take ADVANCED in semester 3 without PREREQ_A
        # Should be INFEASIBLE (missing course doesn't count, must take PREREQ_A)
        model.Add(take_vars[(0, 3)] == 1)
        model.Add(take_vars[(1, 1)] == 0)
        model.Add(take_vars[(1, 2)] == 0)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status == cp_model.INFEASIBLE, \
            "Should be infeasible without taking the valid alternative (PREREQ_A)"

    def test_all_missing_in_or_group_makes_untakeable(self):
        """
        Regression test: If ALL courses in OR group are missing, course is untakeable.
        
        Example: (5.60 OR 5.61) where both are missing.
        """
        df = pl.DataFrame({
            'subject_id': ['ADVANCED'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_ADVANCED_s{semester}")

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # ADVANCED requires (MISSING_A OR MISSING_B)
        prereq_tree = PrereqGroup(
            threshold=1,
            items=(PrereqCourse("MISSING_A"), PrereqCourse("MISSING_B"))
        )
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)
        assert result.constraints_added == 3
        assert len(result.warnings) > 0

        # Try to take the course - should be INFEASIBLE
        model.Add(take_vars[(0, 1)] == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE, \
            "Course should be untakeable when all prerequisites in OR group are missing"

    def test_missing_in_and_group_makes_untakeable(self):
        """
        Regression test: Missing course in AND group makes entire course untakeable.
        
        Example: (5.60 AND 10.213) where 5.60 is missing.
        """
        df = pl.DataFrame({
            'subject_id': ['ADVANCED', 'PREREQ_A'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # ADVANCED requires (PREREQ_A AND MISSING_B)
        prereq_tree = PrereqGroup(
            threshold=2,  # Both required
            items=(PrereqCourse("PREREQ_A"), PrereqCourse("MISSING_B"))
        )
        prereq_trees = {0: prereq_tree}

        result = builder.add_all_prerequisite_constraints(prereq_trees)
        assert result.constraints_added == 3
        assert len(result.warnings) > 0

        # Try to take ADVANCED with PREREQ_A satisfied but MISSING_B not available
        model.Add(take_vars[(1, 1)] == 1)  # Take PREREQ_A
        model.Add(take_vars[(0, 2)] == 1)  # Try to take ADVANCED

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE, \
            "Course should be untakeable when any prerequisite in AND group is missing"

    def test_2013_bug_full_integration(self):
        """
        Full integration test reproducing the 2.013 bug with real course data.
        
        This test fetches real courses and requirements from fireroad API
        and runs the full optimizer to see if 2.013 can be incorrectly placed
        without prerequisites.
        """
        import requests

        from courses.prerequisites.parser import parse_fireroad

        # Fetch real course data
        response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
        response.raise_for_status()
        courses_data = response.json()

        # Filter to non-historical courses
        courses = [c for c in courses_data if not c.get('is_historical')]

        # Convert to DataFrame
        df = pl.DataFrame(courses)

        # Find 2.013 and its prerequisites
        subject_ids = df['subject_id'].to_list()
        try:
            course_2013_idx = subject_ids.index('2.013')
        except ValueError:
            # Course doesn't exist in dataset, skip test
            return

        # Get prerequisite string for 2.013
        prereq_str = df[course_2013_idx, 'prerequisites']
        if not prereq_str:
            # No prerequisites defined, skip test
            return

        print(f"\n2.013 Prerequisites: {prereq_str}")

        # Parse prerequisite
        prereq_tree = parse_fireroad(prereq_str)
        print(f"Parsed tree: {prereq_tree}")

        # Create model and take_vars
        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for all courses in semesters 1-8
        for course_idx in range(len(df)):
            for semester in range(1, 9):
                course_id = df[course_idx, 'subject_id']
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{course_id.replace('.', '_')}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = PrerequisiteConstraintBuilder(ctx)

        # Add prerequisite constraints for 2.013
        prereq_trees = {course_2013_idx: prereq_tree}
        result = builder.add_all_prerequisite_constraints(prereq_trees)

        print(f"Constraints added: {result.constraints_added}")
        print(f"Warnings: {result.warnings}")
        print(f"Errors: {result.errors}")

        # Force 2.013 in semester 7
        model.Add(take_vars[(course_2013_idx, 7)] == 1)

        # Force all prerequisite courses to NOT be taken
        prereq_course_ids = ['2.001', '2.003', '2.005', '2.051', '2.00B', '2.670', '2.678']
        for prereq_id in prereq_course_ids:
            try:
                prereq_idx = subject_ids.index(prereq_id)
                for semester in range(1, 9):
                    if (prereq_idx, semester) in take_vars:
                        model.Add(take_vars[(prereq_idx, semester)] == 0)
            except ValueError:
                pass  # Course not in dataset

        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        print(f"Solver status: {status}")

        # This MUST be infeasible
        assert status == cp_model.INFEASIBLE, \
            f"Bug reproduced! Solver allowed 2.013 in semester 7 without prerequisites (status={status})"

    def test_2013_complex_and_group_prerequisites(self):
        """
        Test that course 2.013 cannot be placed without satisfying its prerequisites.
        
        Reproduces bug where solver places 2.013 in Senior Fall without any prerequisites.
        
        2.013 requires: (2.001, 2.003, (2.005/2.051), (2.00B/2.670/2.678))
        This means ALL of:
        - 2.001 (Mechanics and Materials I)
        - 2.003 (Dynamics and Control I)
        - 2.005 OR 2.051 (one required)
        - 2.00B OR 2.670 OR 2.678 (one required)
        """
        df = pl.DataFrame({
            'subject_id': ['2.013', '2.001', '2.003', '2.005', '2.051', '2.00B', '2.670', '2.678'],
            'gir_attribute': [None, None, None, None, None, None, None, None],
            'hass_attribute': [None, None, None, None, None, None, None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for all courses across 8 semesters
        for course_idx in range(len(df)):
            for semester in range(1, 9):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        # Build the prerequisite tree for 2.013 (course_idx 0)
        # Requires ALL of: 2.001, 2.003, (2.005 OR 2.051), (2.00B OR 2.670 OR 2.678)
        prereq_tree = PrereqGroup(
            threshold=4,  # All 4 items required
            items=(
                PrereqCourse("2.001"),
                PrereqCourse("2.003"),
                PrereqGroup(
                    threshold=1,  # One of these
                    items=(PrereqCourse("2.005"), PrereqCourse("2.051"))
                ),
                PrereqGroup(
                    threshold=1,  # One of these
                    items=(PrereqCourse("2.00B"), PrereqCourse("2.670"), PrereqCourse("2.678"))
                )
            )
        )

        prereq_trees = {0: prereq_tree}

        result = add_prerequisite_constraints(
            model, take_vars, df, 2024, prereq_trees
        )

        # Should add constraints for 2.013 in semesters 1-8
        assert result.constraints_added == 8
        assert not result.has_issues

        # Test 1: Try to take 2.013 in semester 7 with NO prerequisites
        # This should be INFEASIBLE
        model.Add(take_vars[(0, 7)] == 1)  # Force 2.013 in semester 7

        # Ensure NO prerequisites are taken
        for course_idx in range(1, 8):  # All prereq courses
            for semester in range(1, 9):
                model.Add(take_vars[(course_idx, semester)] == 0)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # This MUST be infeasible - cannot take 2.013 without prerequisites
        assert status == cp_model.INFEASIBLE, \
            "Bug reproduced! Solver allowed 2.013 without prerequisites"

    def test_2013_with_satisfied_prerequisites(self):
        """
        Test that 2.013 CAN be placed when prerequisites are satisfied.
        """
        df = pl.DataFrame({
            'subject_id': ['2.013', '2.001', '2.003', '2.005', '2.051', '2.00B', '2.670', '2.678'],
            'gir_attribute': [None, None, None, None, None, None, None, None],
            'hass_attribute': [None, None, None, None, None, None, None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(len(df)):
            for semester in range(1, 9):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        prereq_tree = PrereqGroup(
            threshold=4,
            items=(
                PrereqCourse("2.001"),
                PrereqCourse("2.003"),
                PrereqGroup(threshold=1, items=(PrereqCourse("2.005"), PrereqCourse("2.051"))),
                PrereqGroup(threshold=1, items=(PrereqCourse("2.00B"), PrereqCourse("2.670"), PrereqCourse("2.678")))
            )
        )

        prereq_trees = {0: prereq_tree}
        result = add_prerequisite_constraints(model, take_vars, df, 2024, prereq_trees)

        assert result.constraints_added == 8
        assert not result.has_issues

        # Take all prerequisites in earlier semesters
        model.Add(take_vars[(1, 1)] == 1)  # 2.001 in semester 1
        model.Add(take_vars[(2, 2)] == 1)  # 2.003 in semester 2
        model.Add(take_vars[(3, 3)] == 1)  # 2.005 in semester 3 (satisfies OR group)
        model.Add(take_vars[(5, 4)] == 1)  # 2.00B in semester 4 (satisfies OR group)

        # Now try to take 2.013 in semester 7
        model.Add(take_vars[(0, 7)] == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

