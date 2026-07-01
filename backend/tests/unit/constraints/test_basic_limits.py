"""
Unit tests for basic limit constraints (freshman fall and IAP) with fallback units.
"""

import polars as pl
from ortools.sat.python import cp_model

from shared.optimizer.constraints.basic import add_freshman_fall_limit, add_iap_limits


def test_freshman_fall_limit_fallback_units():
    """Test that courses with missing or None total_units default to 12 units in freshman fall constraint."""
    df = pl.DataFrame({
        'subject_id': ['6.100A', '18.01', '8.01'],
        'total_units': [None, 3, 12]  # None and 3 should both fallback to 12 units
    })

    model = cp_model.CpModel()
    take_vars = {
        (0, 1): model.NewBoolVar('take_0_s1'),
        (1, 1): model.NewBoolVar('take_1_s1'),
        (2, 1): model.NewBoolVar('take_2_s1'),
    }

    # Add the constraint
    add_freshman_fall_limit(model, take_vars, df)

    # Force all three courses to be taken
    model.Add(take_vars[(0, 1)] == 1)
    model.Add(take_vars[(1, 1)] == 1)
    model.Add(take_vars[(2, 1)] == 1)

    # With fallback: total units = 12 + 12 + 12 = 36 <= 54 (feasible)
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status == cp_model.OPTIMAL


def test_iap_limit_fallback_units():
    """Test that courses with missing or None total_units default to 12 units in IAP constraint."""
    df = pl.DataFrame({
        'subject_id': ['6.100A', '18.01'],
        'total_units': [None, 12]
    })

    model = cp_model.CpModel()
    # Semester 2 is an IAP semester
    take_vars = {
        (0, 2): model.NewBoolVar('take_0_s2'),
        (1, 2): model.NewBoolVar('take_1_s2'),
    }

    add_iap_limits(model, take_vars, df, max_semesters=2)

    # Try to take both courses in IAP (total units: 12 + 12 = 24, which exceeds 12 units limit)
    model.Add(take_vars[(0, 2)] == 1)
    model.Add(take_vars[(1, 2)] == 1)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status == cp_model.INFEASIBLE
