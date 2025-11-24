"""
Tests for the requirement constraint builder.
"""

import polars as pl
from ortools.sat.python import cp_model

from courses.requirements.types import (
    RequirementCourse,
    RequirementGroup,
    RequirementPlainString,
    RequirementThreshold,
)
from optimizer.requirement_constraint_builder import (
    ConstraintContext,
    CourseSchedule,
    RequirementConstraintBuilder,
    add_requirement_constraints,
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

    def test_get_courses_by_attribute(self):
        """Test finding courses by attribute value."""
        df = pl.DataFrame({
            'subject_id': ['18.01', '18.02', '6.100A'],
            'gir_attribute': ['CAL1', 'CAL2', None],
        })
        schedule = CourseSchedule(df, 2024)

        cal1_courses = schedule.get_courses_by_attribute('gir_attribute', 'CAL1')
        assert cal1_courses == [0]

        cal2_courses = schedule.get_courses_by_attribute('gir_attribute', 'CAL2')
        assert cal2_courses == [1]

        # Non-existent attribute
        missing = schedule.get_courses_by_attribute('missing_attr', 'value')
        assert missing == []

    def test_get_courses_by_hass_any(self):
        """Test finding courses with any HASS attribute."""
        df = pl.DataFrame({
            'subject_id': ['21M.011', '21H.102', '6.100A', '24.00'],
            'hass_attribute': ['HASS-A', 'HASS-H', None, 'HASS-S'],
        })
        schedule = CourseSchedule(df, 2024)

        hass_courses = schedule.get_courses_by_hass_any()
        assert set(hass_courses) == {0, 1, 3}


class TestRequirementConstraintBuilder:
    """Tests for RequirementConstraintBuilder."""

    def test_simple_course_requirement(self):
        """Test a simple course requirement."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
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

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Require course 6.100A
        req = RequirementCourse(course_id="6.100A")
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None
        assert not result.has_issues

    def test_missing_course(self):
        """Test that missing courses generate errors."""
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
        builder = RequirementConstraintBuilder(ctx)

        # Require a course that doesn't exist
        req = RequirementCourse(course_id="MISSING.COURSE")
        result = builder.build(req)

        assert not result.is_valid
        assert result.satisfied_var is None
        assert len(result.errors) > 0
        assert "MISSING.COURSE" in result.errors[0]

    def test_gir_requirement(self):
        """Test a GIR requirement (e.g., GIR:CAL1)."""
        df = pl.DataFrame({
            'subject_id': ['18.01', '18.02', '6.100A'],
            'gir_attribute': ['CAL1', 'CAL2', None],
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
        builder = RequirementConstraintBuilder(ctx)

        # Require GIR:CAL1 (satisfied by 18.01)
        req = RequirementCourse(course_id="GIR:CAL1")
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None
        assert not result.has_issues

    def test_hass_requirement(self):
        """Test a specific HASS requirement (e.g., HASS-A)."""
        df = pl.DataFrame({
            'subject_id': ['21M.011', '21H.102', '6.100A'],
            'gir_attribute': [None, None, None],
            'hass_attribute': ['HASS-A', 'HASS-H', None],
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
        builder = RequirementConstraintBuilder(ctx)

        # Require HASS-A (satisfied by 21M.011)
        req = RequirementCourse(course_id="HASS-A")
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None
        assert not result.has_issues

    def test_ci_requirement(self):
        """Test a CI requirement (e.g., CI-H)."""
        df = pl.DataFrame({
            'subject_id': ['6.UAT', '6.UAR', '6.100A'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
            'communication_requirement': ['CI-H', 'CI-HW', None],
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
        builder = RequirementConstraintBuilder(ctx)

        # Require CI-H (satisfied by 6.UAT)
        req = RequirementCourse(course_id="CI-H")
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None
        assert not result.has_issues

    def test_generic_hass_requirement(self):
        """Test the generic HASS requirement (any HASS course)."""
        df = pl.DataFrame({
            'subject_id': ['21M.011', '21H.102', '6.100A'],
            'gir_attribute': [None, None, None],
            'hass_attribute': ['HASS-A', 'HASS-H', None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(3):
            for semester in range(1, 13):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Require generic HASS (requires 8 HASS courses)
        req = RequirementCourse(course_id="HASS")
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None

    def test_plain_string_requirement(self):
        """Test plain-string requirements (always satisfied with warning)."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Plain string requirement
        req = RequirementPlainString(description="Must maintain a GPA above 4.0")
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None
        assert len(result.warnings) > 0
        assert "cannot be validated" in result.warnings[0]

    def test_group_all_connection(self):
        """Test a group with ALL connection (all children required)."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B', '6.1010'],
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
        builder = RequirementConstraintBuilder(ctx)

        # Group requiring all courses
        req = RequirementGroup(
            title="Intro Programming",
            connection_type="all",
            items=(
                RequirementCourse(course_id="6.100A"),
                RequirementCourse(course_id="6.100B"),
            )
        )
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None
        assert "Intro Programming" in ctx.aux_vars

    def test_group_any_connection(self):
        """Test a group with ANY connection (at least one child required)."""
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

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Group requiring any course
        req = RequirementGroup(
            title="Programming Choice",
            connection_type="any",
            items=(
                RequirementCourse(course_id="6.100A"),
                RequirementCourse(course_id="6.100B"),
            )
        )
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None

    def test_threshold_requirement(self):
        """Test a threshold requirement (N of M courses)."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B', '6.1010', '6.1020'],
            'gir_attribute': [None, None, None, None],
            'hass_attribute': [None, None, None, None],
        })

        model = cp_model.CpModel()
        take_vars = {}

        for course_idx in range(4):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Require 2 of 4 courses
        req = RequirementGroup(
            title="Electives",
            threshold=RequirementThreshold(
                type="GTE",
                cutoff=2,
                criterion="subjects"
            ),
            items=(
                RequirementCourse(course_id="6.100A"),
                RequirementCourse(course_id="6.100B"),
                RequirementCourse(course_id="6.1010"),
                RequirementCourse(course_id="6.1020"),
            )
        )
        result = builder.build(req)

        assert result.is_valid
        assert result.satisfied_var is not None

    def test_infeasible_threshold(self):
        """Test threshold requirement where not enough valid courses exist."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Require 2 courses but only 1 exists in database
        req = RequirementGroup(
            title="Electives",
            threshold=RequirementThreshold(
                type="GTE",
                cutoff=2,
                criterion="subjects"
            ),
            items=(
                RequirementCourse(course_id="6.100A"),
                RequirementCourse(course_id="MISSING.COURSE"),
            )
        )
        result = builder.build(req)

        # Should build with errors
        assert result.is_valid  # Variable still created
        assert len(result.errors) > 0

    def test_enforce_requirement(self):
        """Test enforcing a requirement (making it mandatory)."""
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
        builder = RequirementConstraintBuilder(ctx)

        # Enforce the requirement
        req = RequirementCourse(course_id="6.100A")
        builder.enforce_requirement(req)

        # The requirement variable should be forced to 1
        # We can verify by checking that at least one semester must have the course
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        # At least one semester should take the course
        assert any(solver.Value(take_vars[(0, s)]) == 1 for s in range(1, 4))

    def test_get_summary(self):
        """Test getting a summary of issues encountered."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Build a requirement with warnings
        req = RequirementPlainString(description="Manual requirement")
        builder.build(req)

        # Build a requirement with errors
        req2 = RequirementCourse(course_id="MISSING")
        builder.build(req2)

        summary = builder.get_summary()

        assert summary["has_issues"]
        assert summary["warning_count"] > 0
        assert summary["error_count"] > 0
        assert len(summary["warnings"]) > 0
        assert len(summary["errors"]) > 0


class TestAddRequirementConstraints:
    """Tests for the top-level convenience function."""

    def test_add_requirement_constraints(self):
        """Test the add_requirement_constraints function."""
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

        # Simple requirement
        req = RequirementCourse(course_id="6.100A")

        aux_vars, var_name_map, course_to_requirements = add_requirement_constraints(
            model, take_vars, req, df, 2024, enforce=True
        )

        # Should return a dict of auxiliary variables and a var name map
        assert isinstance(aux_vars, dict)
        assert isinstance(var_name_map, dict)
        assert isinstance(course_to_requirements, dict)

    def test_add_requirement_without_enforce(self):
        """Test adding constraints without enforcing the requirement."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        req = RequirementCourse(course_id="6.100A")

        aux_vars, var_name_map, course_to_requirements = add_requirement_constraints(
            model, take_vars, req, df, 2024, enforce=False
        )

        assert isinstance(aux_vars, dict)
        assert isinstance(course_to_requirements, dict)
        assert isinstance(var_name_map, dict)
        # Requirement not enforced, so model could have solution without taking the course

    def test_pruned_course_skipped(self):
        """Test that pruned courses are skipped during constraint building."""
        df = pl.DataFrame({
            "subject_id": ["6.100A"],
            "gir_attribute": [None],
            "hass_attribute": [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Build a pruned requirement
        req = RequirementCourse(course_id="INVALID.COURSE", was_pruned=True)
        result = builder.build(req)

        # Should not create a constraint variable
        assert result.satisfied_var is None
        # Should generate a warning about skipping
        assert len(result.warnings) > 0
        assert "pruned" in result.warnings[0].lower()


    def test_pruned_group_skipped(self):
        """Test that pruned groups are skipped entirely."""
        df = pl.DataFrame({
            "subject_id": ["6.100A"],
            "gir_attribute": [None],
            "hass_attribute": [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Build a pruned group (entire group is infeasible)
        req = RequirementGroup(
            title="Infeasible Group",
            connection_type="all",
            items=(
                RequirementCourse(course_id="INVALID.1"),
                RequirementCourse(course_id="INVALID.2"),
            ),
            was_pruned=True
        )
        result = builder.build(req)

        # Should not create a constraint variable
        assert result.satisfied_var is None
        # Should generate a warning
        assert len(result.warnings) > 0
        assert "pruned" in result.warnings[0].lower()

    def test_mixed_pruned_and_valid_in_group(self):
        """Test a group with both pruned and valid children."""
        df = pl.DataFrame({
            "subject_id": ["6.100A", "6.100B"],
            "gir_attribute": [None, None],
            "hass_attribute": [None, None],
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
        builder = RequirementConstraintBuilder(ctx)

        # Group with mix of pruned and valid courses
        req = RequirementGroup(
            title="Mixed Group",
            connection_type="any",  # At least one required
            items=(
                RequirementCourse(course_id="6.100A"),  # Valid
                RequirementCourse(course_id="INVALID.COURSE", was_pruned=True),  # Pruned
                RequirementCourse(course_id="6.100B"),  # Valid
            )
        )
        result = builder.build(req)

        # Group itself should be built (not pruned)
        assert result.satisfied_var is not None
        # Should have warnings from the pruned child
        assert result.has_issues
        assert any("pruned" in w.lower() for w in result.warnings)

    def test_nested_pruned_groups(self):
        """Test nested groups where some are pruned."""
        df = pl.DataFrame({
            "subject_id": ["6.100A"],
            "gir_attribute": [None],
            "hass_attribute": [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Nested group with a pruned subgroup
        req = RequirementGroup(
            title="Outer Group",
            connection_type="any",
            items=(
                RequirementCourse(course_id="6.100A"),  # Valid
                RequirementGroup(  # Pruned subgroup
                    title="Pruned Subgroup",
                    connection_type="all",
                    items=(RequirementCourse(course_id="INVALID.1"),),
                    was_pruned=True
                ),
            )
        )
        result = builder.build(req)

        # Outer group should be built
        assert result.satisfied_var is not None
        # Should have warnings from pruned subgroup
        assert any("pruned" in w.lower() for w in result.warnings)

    def test_all_pruned_children_in_group(self):
        """Test a group where all children are pruned (but group itself is not marked pruned)."""
        df = pl.DataFrame({
            "subject_id": ["6.100A"],
            "gir_attribute": [None],
            "hass_attribute": [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Group with all pruned children (but group not marked pruned)
        req = RequirementGroup(
            title="All Children Pruned",
            connection_type="any",
            items=(
                RequirementCourse(course_id="INVALID.1", was_pruned=True),
                RequirementCourse(course_id="INVALID.2", was_pruned=True),
            ),
            was_pruned=False  # Group itself not marked as pruned
        )
        result = builder.build(req)

        # Group variable should be created
        assert result.satisfied_var is not None
        # Should have warnings for each pruned child
        assert len(result.warnings) >= 2
        # Should have errors since no valid children exist
        assert len(result.errors) > 0

    def test_pruned_plain_string(self):
        """Test that pruned plain-string requirements are skipped."""
        df = pl.DataFrame({
            "subject_id": ["6.100A"],
            "gir_attribute": [None],
            "hass_attribute": [None],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar("take_6.100A_s1")}

        schedule = CourseSchedule(df, 2024)
        ctx = ConstraintContext(model, take_vars, schedule)
        builder = RequirementConstraintBuilder(ctx)

        # Pruned plain-string requirement
        req = RequirementPlainString(
            description="Some manual requirement",
            was_pruned=True
        )
        result = builder.build(req)

        # Should not create a constraint variable
        assert result.satisfied_var is None
        # Should generate a warning
        assert len(result.warnings) > 0
        assert "pruned" in result.warnings[0].lower()
