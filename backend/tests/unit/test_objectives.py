"""
Tests for optimizer objective functions.

These tests verify that objective functions correctly compute costs
and handle edge cases like missing data.
"""

import polars as pl
from ortools.sat.python import cp_model

from shared.optimizer.objectives.base import ObjectiveContext
from shared.optimizer.objectives.units import MinimizeUnits


class TestMinimizeUnits:
    """Test the MinimizeUnits objective."""

    def test_minimizes_total_units(self):
        """Should prefer schedules with fewer total units."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.100A', '6.9020'],
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
        # Total units: 12 + 6 = 18 (no scaling in tier-based system)
        assert solver.ObjectiveValue() == 18

    def test_handles_nan_units(self):
        """Courses with None units should default to 12 units."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.100A', '6.9020'],
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
        # Both courses counted: 12 + 12 (None defaults to 12)
        assert solver.ObjectiveValue() == 24



