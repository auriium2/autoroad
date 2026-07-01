"""
Unit tests for nested group unique counting inside SubjectThresholdGroup.
"""

import polars as pl
from ortools.sat.python import cp_model

from shared.courses.requirements.types import AllGroup, Course, SubjectThresholdGroup
from shared.optimizer.requirements.builder import build_constraints


def test_subject_threshold_nested_all_group_strict():
    """
    Test that flat unique counting does not bypass nested group logic.
    Requirement: SubjectThresholdGroup(cutoff=2, children=(AllGroup(A, B), C))
    If we only take A and C:
    - AllGroup(A, B) is NOT satisfied.
    - C is satisfied.
    So only 1 requirement item is satisfied. It should be INFEASIBLE.
    """
    df = pl.DataFrame({
        'subject_id': ['A', 'B', 'C'],
        'total_units': [12, 12, 12]
    })

    model = cp_model.CpModel()
    take_vars = {
        (0, 1): model.NewBoolVar('take_A'),
        (1, 1): model.NewBoolVar('take_B'),
        (2, 1): model.NewBoolVar('take_C'),
    }

    # Structure: SubjectThreshold(cutoff=2, children=(AllGroup(A, B), C))
    node = SubjectThresholdGroup(
        cutoff=2,
        children=(
            AllGroup(children=(Course("A"), Course("B"))),
            Course("C")
        )
    )

    build_constraints(model, take_vars, node, df, "test_nested")

    # Only take A and C
    model.Add(take_vars[(0, 1)] == 1)  # A
    model.Add(take_vars[(1, 1)] == 0)  # B (so AllGroup is unsatisfied)
    model.Add(take_vars[(2, 1)] == 1)  # C

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # Without the fix, the buggy solver says OPTIMAL because it flat-counts {A, C} as 2 unique subjects.
    # With our fix, it correctly identifies it as INFEASIBLE because the AllGroup contributes 0.
    assert status == cp_model.INFEASIBLE
