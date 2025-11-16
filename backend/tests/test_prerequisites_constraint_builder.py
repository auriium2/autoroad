"""
Tests for the prerequisite constraint builder.
"""

import pandas as pd
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
        df = pd.DataFrame({
            'subject_id': ['6.100A', '6.100B', '18.01'],
            'gir_attribute': [None, None, 'CAL1'],
        })
        schedule = CourseSchedule(df, 2024)

        assert schedule.get_course_index('6.100A') == 0
        assert schedule.get_course_index('18.01') == 2
        assert schedule.get_course_index('MISSING') is None

    def test_get_courses_by_gir(self):
        """Test finding courses by GIR attribute."""
        df = pd.DataFrame({
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
        df = pd.DataFrame({
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
        df = pd.DataFrame({
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
                    f"take_{df.at[course_idx, 'subject_id']}_s{semester}"
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
        df = pd.DataFrame({
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
                    f"take_{df.at[course_idx, 'subject_id']}_s{semester}"
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
        df = pd.DataFrame({
            'subject_id': ['6.UAT', '21M.011', '21H.102'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, 'HASS-A', 'HASS-H'],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df.at[course_idx, 'subject_id']}_s{semester}"
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
        df = pd.DataFrame({
            'subject_id': ['6.1010', '6.100A', '6.100B'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df.at[course_idx, 'subject_id']}_s{semester}"
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
        df = pd.DataFrame({
            'subject_id': ['6.1010', '6.100A', '6.100B'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df.at[course_idx, 'subject_id']}_s{semester}"
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
        df = pd.DataFrame({
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
        df = pd.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df.at[course_idx, 'subject_id']}_s{semester}"
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
        df = pd.DataFrame({
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
        df = pd.DataFrame({
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
        df = pd.DataFrame({
            'subject_id': ['8.02', '8.01'],
            'gir_attribute': [None, 'PHY1'],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        # Create take variables for both courses in ASE semester (-1)
        for course_idx in range(2):
            take_vars[(course_idx, -1)] = model.NewBoolVar(
                f"take_{df.at[course_idx, 'subject_id']}_s-1"
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
        df = pd.DataFrame({
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

    def test_solo_courses_skip_prereq_constraints(self):
        """Test that solo courses don't have prerequisite constraints added."""
        df = pd.DataFrame({
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
                    f"take_{df.at[course_idx, 'subject_id']}_s{semester}"
                )

        # 8.02 requires 8.01, but 8.02 is marked as solo
        prereq_trees = {0: PrereqCourse("8.01")}
        solo_course_ids = {'8.02'}

        result = add_prerequisite_constraints(
            model, take_vars, df, 2024, prereq_trees, solo_course_ids
        )

        # No constraints should be added since 8.02 is solo
        assert result.constraints_added == 0
        assert not result.has_issues
