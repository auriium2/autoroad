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
