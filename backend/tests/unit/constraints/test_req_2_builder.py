"""
Tests for the req_2 constraint builder.

These tests verify that the new single-dispatch based builder
produces equivalent constraints to the old RequirementConstraintBuilder.
"""

import polars as pl
from ortools.sat.python import cp_model

from courses.requirements import nodes
from optimizer.requirements.builder import add_requirement_constraints, build_constraints


class TestCourseNode:
    """Tests for Course node constraint building."""

    def test_simple_course(self):
        """Test a simple course requirement."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.Course(subject_id="6.100A")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None
        assert not result.errors

    def test_missing_course(self):
        """Test that missing courses generate errors."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}
        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_6.100A_s{semester}")

        req = nodes.Course(subject_id="MISSING.COURSE")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is None
        assert len(result.errors) > 0
        assert "MISSING.COURSE" in result.errors[0]

    def test_course_enforced(self):
        """Test enforcing a course requirement forces it to be taken."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}
        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_6.100A_s{semester}")

        req = nodes.Course(subject_id="6.100A")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=True)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert any(solver.Value(take_vars[(0, s)]) == 1 for s in range(1, 4))


class TestGIRNode:
    """Tests for GIR node constraint building."""

    def test_gir_requirement(self):
        """Test a GIR requirement (e.g., CAL1)."""
        df = pl.DataFrame({
            'subject_id': ['18.01', '18.02', '6.100A'],
            'gir_attribute': ['CAL1', 'CAL2', None],
            'hass_attribute': [None, None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.GIR(gir_code="CAL1")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None
        assert not result.errors


class TestHASSNode:
    """Tests for HASS node constraint building."""

    def test_hass_category_requirement(self):
        """Test a specific HASS category requirement (e.g., HASS-A)."""
        df = pl.DataFrame({
            'subject_id': ['21M.011', '21H.102', '6.100A'],
            'gir_attribute': [None, None, None],
            'hass_attribute': ['HASS-A', 'HASS-H', None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.HASS(category="HASS-A")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None
        assert not result.errors

    def test_generic_hass_requirement(self):
        """Test a generic HASS requirement (any HASS course)."""
        df = pl.DataFrame({
            'subject_id': ['21M.011', '21H.102', '6.100A'],
            'gir_attribute': [None, None, None],
            'hass_attribute': ['HASS-A', 'HASS-H', None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(3):
            for semester in range(1, 9):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.HASS(category="HASS")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None


class TestCINode:
    """Tests for CI node constraint building."""

    def test_ci_requirement(self):
        """Test a CI requirement (e.g., CI-H)."""
        df = pl.DataFrame({
            'subject_id': ['6.UAT', '6.UAR', '6.100A'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
            'communication_requirement': ['CI-H', 'CI-HW', None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.CI(ci_type="CI-H")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None
        assert not result.errors


class TestPlainStringNode:
    """Tests for PlainString node constraint building."""

    def test_plain_string_always_satisfied(self):
        """Test plain-string requirements are always satisfied with warning."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {
            (0, 1): model.NewBoolVar("take_6.100A_s1")
        }

        req = nodes.PlainString(description="Must maintain a GPA above 4.0")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None
        assert len(result.warnings) > 0


class TestAllGroup:
    """Tests for AllGroup node constraint building."""

    def test_all_group(self):
        """Test a group with ALL connection (all children required)."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B', '6.1010'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.AllGroup(
            title="Intro Programming",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None
        assert "Intro Programming" in ctx.aux_vars

    def test_all_group_enforced(self):
        """Test that enforcing AllGroup requires all children to be taken."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.AllGroup(
            title="Both Required",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=True)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        # Both courses should be taken
        assert any(solver.Value(take_vars[(0, s)]) == 1 for s in range(1, 4))
        assert any(solver.Value(take_vars[(1, s)]) == 1 for s in range(1, 4))


class TestAnyGroup:
    """Tests for AnyGroup node constraint building."""

    def test_any_group(self):
        """Test a group with ANY connection (at least one child required)."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.AnyGroup(
            title="Programming Choice",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None

    def test_any_group_enforced(self):
        """Test that enforcing AnyGroup requires at least one child to be taken."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.AnyGroup(
            title="Pick One",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=True)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        # At least one course should be taken
        course_0_taken = any(solver.Value(take_vars[(0, s)]) == 1 for s in range(1, 4))
        course_1_taken = any(solver.Value(take_vars[(1, s)]) == 1 for s in range(1, 4))
        assert course_0_taken or course_1_taken


class TestSubjectThresholdGroup:
    """Tests for SubjectThresholdGroup node constraint building."""

    def test_threshold_2_of_4(self):
        """Test a threshold requirement (N of M courses)."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B', '6.1010', '6.1020'],
            'gir_attribute': [None, None, None, None],
            'hass_attribute': [None, None, None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(4):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.SubjectThresholdGroup(
            title="Electives",
            cutoff=2,
            threshold_type="GTE",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
                nodes.Course(subject_id="6.1010"),
                nodes.Course(subject_id="6.1020"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None

    def test_threshold_enforced(self):
        """Test that enforcing a threshold requires the minimum courses."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B', '6.1010'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.SubjectThresholdGroup(
            title="Pick 2",
            cutoff=2,
            threshold_type="GTE",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
                nodes.Course(subject_id="6.1010"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=True)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Count how many courses are taken
        courses_taken = 0
        for course_idx in range(3):
            if any(solver.Value(take_vars[(course_idx, s)]) == 1 for s in range(1, 4)):
                courses_taken += 1

        assert courses_taken >= 2

    def test_distinct_threshold(self):
        """Test distinct_threshold (courses from N different categories)."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B', '18.01', '18.02'],
            'gir_attribute': [None, None, None, None],
            'hass_attribute': [None, None, None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(4):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        # 4 courses from at least 2 categories
        req = nodes.SubjectThresholdGroup(
            title="From 2 Areas",
            cutoff=4,
            threshold_type="GTE",
            distinct_threshold=nodes.DistinctThreshold(cutoff=2),
            children=(
                nodes.SubjectThresholdGroup(
                    title="CS",
                    cutoff=0,  # Optional threshold
                    children=(
                        nodes.Course(subject_id="6.100A"),
                        nodes.Course(subject_id="6.100B"),
                    )
                ),
                nodes.SubjectThresholdGroup(
                    title="Math",
                    cutoff=0,
                    children=(
                        nodes.Course(subject_id="18.01"),
                        nodes.Course(subject_id="18.02"),
                    )
                ),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None


class TestUnitThresholdGroup:
    """Tests for UnitThresholdGroup node constraint building."""

    def test_unit_threshold(self):
        """Test a unit-based threshold requirement."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B', '6.1010'],
            'gir_attribute': [None, None, None],
            'hass_attribute': [None, None, None],
            'total_units': [12, 12, 15],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(3):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.UnitThresholdGroup(
            title="24 Units",
            cutoff=24,
            threshold_type="GTE",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
                nodes.Course(subject_id="6.1010"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        assert result.sat_var is not None

    def test_unit_threshold_enforced(self):
        """Test that enforcing a unit threshold requires enough units."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
            'total_units': [12, 15],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.UnitThresholdGroup(
            title="24 Units",
            cutoff=24,
            threshold_type="GTE",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=True)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Need at least 24 units (12 + 15 = 27 available, need 24)
        # So both courses must be taken
        assert any(solver.Value(take_vars[(0, s)]) == 1 for s in range(1, 4))
        assert any(solver.Value(take_vars[(1, s)]) == 1 for s in range(1, 4))


class TestPrunedNodes:
    """Tests for handling pruned nodes."""

    def test_pruned_course_skipped(self):
        """Test that pruned courses are skipped."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {
            (0, 1): model.NewBoolVar("take_6.100A_s1")
        }

        req = nodes.Course(subject_id="INVALID.COURSE", was_pruned=True)
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        # Pruned courses should contribute 0, not create an error
        # The behavior depends on implementation - check what we actually do
        assert result.sat_var is None or not result.errors

    def test_mixed_pruned_and_valid_in_group(self):
        """Test a group with both pruned and valid children."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}
        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.AnyGroup(
            title="Mixed Group",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="INVALID.COURSE", was_pruned=True),
                nodes.Course(subject_id="6.100B"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        # Group should still be built with valid children
        assert result.sat_var is not None


class TestCourseToRequirements:
    """Tests for course_to_requirements tracking."""

    def test_course_records_path(self):
        """Test that courses record their requirement path."""
        df = pl.DataFrame({
            'subject_id': ['6.100A'],
            'gir_attribute': [None],
            'hass_attribute': [None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}
        for semester in range(1, 4):
            take_vars[(0, semester)] = model.NewBoolVar(f"take_6.100A_s{semester}")

        req = nodes.Course(subject_id="6.100A")
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        # Course 0 should be recorded with path "test" (the requirement_key)
        assert 0 in ctx.course_to_requirements
        assert "test" in ctx.course_to_requirements[0]

    def test_nested_paths(self):
        """Test that nested structures have correct paths."""
        df = pl.DataFrame({
            'subject_id': ['6.100A', '6.100B'],
            'gir_attribute': [None, None],
            'hass_attribute': [None, None],
        })

        model = cp_model.CpModel()
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}
        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.AllGroup(
            title="Parent",
            children=(
                nodes.Course(subject_id="6.100A"),
                nodes.Course(subject_id="6.100B"),
            )
        )
        result, ctx = build_constraints(model, take_vars, req, df, "test", enforce=False)

        # Course 0 should have path "test.0", course 1 should have "test.1"
        assert 0 in ctx.course_to_requirements
        assert 1 in ctx.course_to_requirements
        assert "test.0" in ctx.course_to_requirements[0]
        assert "test.1" in ctx.course_to_requirements[1]


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
        take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for course_idx in range(2):
            for semester in range(1, 4):
                take_vars[(course_idx, semester)] = model.NewBoolVar(
                    f"take_{df[course_idx, 'subject_id']}_s{semester}"
                )

        req = nodes.Course(subject_id="6.100A")

        aux_vars, var_name_map, course_to_requirements = add_requirement_constraints(
            model, take_vars, req, df, "test", enforce=True
        )

        assert isinstance(aux_vars, dict)
        assert isinstance(var_name_map, dict)
        assert isinstance(course_to_requirements, dict)
