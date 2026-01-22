"""
Unit-based objective: minimize total units taken.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext, get_tier_penalty


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
            if units is not None:
                # Direct unit cost (no scaling in tier-based system)
                terms.append(var * int(units))

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.Sum([])


class AvoidSmallClasses:
    """
    Tier-based soft constraint to avoid taking small unit classes (e.g., seminars, 1-unit courses).

    Penalizes courses below a minimum unit threshold using tier-based penalties.
    This prevents padding schedules with low-value classes.
    """

    def __init__(self, min_units: int = 3):
        """
        Args:
            min_units: Minimum acceptable units for a class (default 3)
        """
        self.min_units: int = min_units

    def get_name(self) -> str:
        return "Avoid Small Classes"

    def get_description(self) -> str:
        return f"Penalize classes with fewer than {self.min_units} units (tier-based)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        if 'total_units' not in courses_df.columns:
            units_list = [12] * len(courses_df)
        else:
            units_list = courses_df['total_units'].fill_null(12).to_list()
        return {
            '_units_list': units_list,
            '_subject_ids': courses_df['subject_id'].to_list()
        }

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add tier-based penalty for taking small unit classes.

        Formula: penalty = violations × TIER_BASE^tier × 1

        Note: Courses with user markers are excluded from this penalty,
        allowing users to explicitly choose small classes they want.
        """
        # Get tier for this objective (default tier 2 if not set)
        tier = 2
        if context.objective_tiers and 'avoid_small_classes' in context.objective_tiers:
            tier = context.objective_tiers['avoid_small_classes']

        penalty = get_tier_penalty(tier, base_cost=1)

        # Get marked course IDs (courses user explicitly placed)
        marked_course_ids = context.marked_course_ids or set()

        # Pre-fetch lists for O(1) access
        units_list = (context.extra.get('_units_list') if context.extra else None) or context.courses_df['total_units'].to_list()
        subject_ids = (context.extra.get('_subject_ids') if context.extra else None) or context.courses_df['subject_id'].to_list()

        terms = []

        for (course_idx, semester), var in take_vars.items():
            course_id = subject_ids[course_idx]
            units = units_list[course_idx]

            if units is not None and units < self.min_units:
                # Penalize taking this small class with tier-based penalty
                terms.append(var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.constant(0)
