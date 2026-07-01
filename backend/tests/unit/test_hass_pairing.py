"""
Unit tests for HASS pairing logic with fallback is_half_class units detection.
"""

import polars as pl
from ortools.sat.python import cp_model

from shared.courses.requirements.types import HASSThreshold
from shared.optimizer.requirements.builder import build_constraints


def test_hass_pairing_with_units_fallback():
    """Test that two 6-unit HASS classes are paired together to satisfy 1 credit."""
    df = pl.DataFrame({
        'subject_id': ['21M.011', '21L.011', '21A.011'],
        'hass_attribute': ['HASS-A', 'HASS-H', 'HASS-S'],
        'total_units': [6, 6, 12]  # First two are 6 units (half classes), third is 12 units (full class)
    })

    model = cp_model.CpModel()
    take_vars = {
        (0, 1): model.NewBoolVar('take_0_s1'),  # 21M.011
        (1, 1): model.NewBoolVar('take_1_s1'),  # 21L.011
        (2, 1): model.NewBoolVar('take_2_s1'),  # 21A.011
    }

    # HASS Threshold GTE 2 credits
    node = HASSThreshold(cutoff=2, category=None)

    # Build the constraints with enforce=True
    build_constraints(model, take_vars, node, df, "hass_thresh_test")

    # If we only take 21M.011 (6) and 21L.011 (6), total credits = 0.5 + 0.5 = 1 < 2, so it should be INFEASIBLE
    model.Add(take_vars[(0, 1)] == 1)
    model.Add(take_vars[(1, 1)] == 1)
    model.Add(take_vars[(2, 1)] == 0)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status == cp_model.INFEASIBLE

    # If we take all three, total credits = 0.5 + 0.5 + 1 = 2 >= 2, so it should be FEASIBLE
    model2 = cp_model.CpModel()
    take_vars2 = {
        (0, 1): model2.NewBoolVar('take_0_s1_2'),
        (1, 1): model2.NewBoolVar('take_1_s1_2'),
        (2, 1): model2.NewBoolVar('take_2_s1_2'),
    }
    build_constraints(model2, take_vars2, node, df, "hass_thresh_test")
    model2.Add(take_vars2[(0, 1)] == 1)
    model2.Add(take_vars2[(1, 1)] == 1)
    model2.Add(take_vars2[(2, 1)] == 1)

    solver2 = cp_model.CpSolver()
    status2 = solver2.Solve(model2)
    assert status2 == cp_model.OPTIMAL
