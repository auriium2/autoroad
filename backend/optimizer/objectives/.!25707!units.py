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

    def get_name(self) -> str:
        return "Minimize Units"

    def get_description(self) -> str:
        return "Minimize the total number of units taken across all semesters"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Minimize sum of units for all courses taken.

        Cost = sum(total_units * 10 * take_var)

        Scaling: Multiply by 10 to normalize to ~100 per course (12 units × 10 = 120).
        """
        terms = []

        for (course_idx, semester), var in take_vars.items():
            units = context.courses_df[course_idx, 'total_units']
            if units is not None:
