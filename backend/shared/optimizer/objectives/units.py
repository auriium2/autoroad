"""
Unit-based objective: minimize total units taken.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext


class MinimizeUnits:
    """
    Objective to minimize the total number of units taken.

    This encourages taking the minimum required courses to satisfy requirements.

    Scale: Normalized to ~100 per course (typical course is 12 units, scaled by 10).
    """

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        units_list = courses_df['total_units'].fill_null(0).to_list()
        return {'_units_list': units_list}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Minimize sum of units for all courses taken.

        Cost = sum(total_units × take_var)

        """
        units_list = (context.extra.get('_units_list') if context.extra else None) or context.courses_df['total_units'].to_list()
        terms = []

        for (course_idx, semester), var in take_vars.items():
            units = units_list[course_idx]
            if units is None or units == 0: # 0 unit classes are never free lol
                units = 12
            terms.append(var * int(units))

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.Sum([])



