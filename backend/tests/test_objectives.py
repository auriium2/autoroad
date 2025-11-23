"""
Tests for optimizer objective functions.

These tests verify that objective functions correctly compute costs
and handle edge cases like missing data.
"""

import polars as pl
from ortools.sat.python import cp_model

from optimizer.objectives.base import ObjectiveContext
from optimizer.objectives.units import AvoidSmallClasses, MinimizeUnits


class TestAvoidSmallClasses:
    """Test the AvoidSmallClasses objective."""

    def test_penalizes_small_unit_courses(self):
        """Regression test: ensure we read 'total_units' column correctly."""
        # Create sample courses with different unit values
        courses_df = pl.DataFrame({
            'course_id': ['6.100A', '6.9020', '21M.401', '6.1010'],
            'total_units': [12, 6, 3, 1],  # Note: total_units, not 'units'
        })

        model = cp_model.CpModel()

        # Create take variables for semester 1
        take_vars = {}
        for idx in range(len(courses_df)):
            var = model.NewBoolVar(f'take_{idx}_1')
            take_vars[(idx, 1)] = var

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={}
        )

        # Test with default threshold (min_units=3)
        objective = AvoidSmallClasses(min_units=3, penalty=1000)
        expr = objective.add_to_model(model, take_vars, context)

        # Force all courses to be taken
        for var in take_vars.values():
            model.Add(var == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL

        # Expected: Only 21M.401 (3 units) and 6.1010 (1 unit) should be penalized
        # 21M.401 is NOT penalized because it equals min_units (3 >= 3 is False)
        # 6.1010 IS penalized because 1 < 3
        # Total penalty: 1000 (for the 1-unit course)
        assert solver.ObjectiveValue() == 1000

    def test_no_penalty_for_courses_at_or_above_threshold(self):
        """Courses with units >= min_units should not be penalized."""
        courses_df = pl.DataFrame({
            'course_id': ['6.100A', '6.9020'],
            'total_units': [12, 6],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_0_1'),
            (1, 1): model.NewBoolVar('take_1_1'),
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={}
        )

        objective = AvoidSmallClasses(min_units=6, penalty=1000)
        expr = objective.add_to_model(model, take_vars, context)

        # Force both courses to be taken
        model.Add(take_vars[(0, 1)] == 1)
        model.Add(take_vars[(1, 1)] == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        # Both courses are >= 6 units, so no penalty
        assert solver.ObjectiveValue() == 0

    def test_handles_missing_total_units_column(self):
        """When total_units column is missing, should default to 12."""
        courses_df = pl.DataFrame({
            'course_id': ['6.100A', '6.9020'],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_0_1'),
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={}
        )

        objective = AvoidSmallClasses(min_units=15, penalty=1000)
        expr = objective.add_to_model(model, take_vars, context)

        # Force course to be taken
        model.Add(take_vars[(0, 1)] == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        # Default is 12 units, which is < 15, so penalty applies
        assert solver.ObjectiveValue() == 1000

    def test_different_penalty_values(self):
        """Test that penalty parameter is correctly applied."""
        courses_df = pl.DataFrame({
            'course_id': ['6.1010'],
            'total_units': [1],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar('take_0_1')}

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={}
        )

        # Test with custom penalty
        objective = AvoidSmallClasses(min_units=3, penalty=5000)
        expr = objective.add_to_model(model, take_vars, context)

        model.Add(take_vars[(0, 1)] == 1)
        model.Minimize(expr)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        assert solver.ObjectiveValue() == 5000


class TestMinimizeUnits:
    """Test the MinimizeUnits objective."""

    def test_minimizes_total_units(self):
        """Should prefer schedules with fewer total units."""
        courses_df = pl.DataFrame({
            'course_id': ['6.100A', '6.9020'],
            'total_units': [12, 6],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_0_1'),
            (1, 1): model.NewBoolVar('take_1_1'),
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={}
        )

        objective = MinimizeUnits()
        expr = objective.add_to_model(model, take_vars, context)

        # Force both courses to be taken
        model.Add(take_vars[(0, 1)] == 1)
        model.Add(take_vars[(1, 1)] == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        # Total units: (12 + 6) * 10 = 180
        assert solver.ObjectiveValue() == 180

    def test_handles_nan_units(self):
        """Should skip courses with NaN units."""
        courses_df = pl.DataFrame({
            'course_id': ['6.100A', '6.9020'],
            'total_units': [12, None],  # Polars uses None instead of NaN
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_0_1'),
            (1, 1): model.NewBoolVar('take_1_1'),
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={}
        )

        objective = MinimizeUnits()
        expr = objective.add_to_model(model, take_vars, context)

        model.Add(take_vars[(0, 1)] == 1)
        model.Add(take_vars[(1, 1)] == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        # Only first course counted: 12 * 10 = 120
        assert solver.ObjectiveValue() == 120



