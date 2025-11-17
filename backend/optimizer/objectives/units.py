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
                # Scale by 10 to normalize (12 units → 120)
                scaled_units = int(units) * 10
                terms.append(var * scaled_units)

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.Sum([])


class AvoidSmallClasses:
    """
    Soft constraint to avoid taking small unit classes (e.g., seminars, 1-unit courses).

    Penalizes courses below a minimum unit threshold. This prevents padding schedules
    with low-value classes that don't contribute much to degree progress.

    Scale: Soft constraint with high penalty (1000 per small class by default).
           Designed to dominate when violated, but negligible when satisfied.
    """

    def __init__(self, min_units: int = 3, penalty: int = 1000):
        """
        Args:
            min_units: Minimum acceptable units for a class (default 3)
            penalty: Penalty cost for each class below min_units (default 1000)
        """
        self.min_units: int = min_units
        self.penalty: int = penalty

    def get_name(self) -> str:
        return "Avoid Small Classes"

    def get_description(self) -> str:
        return f"Penalize classes with fewer than {self.min_units} units"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add penalty for taking small unit classes.

        For each course with units < min_units, add penalty when taken.
        """
        terms = []

        for (course_idx, semester), var in take_vars.items():
            units = context.courses_df[course_idx, 'total_units'] if 'total_units' in context.courses_df.columns else 12

            if units is not None and units < self.min_units:
                # Penalize taking this small class
                terms.append(var * self.penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.constant(0)
