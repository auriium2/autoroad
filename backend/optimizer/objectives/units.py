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
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Minimize sum of units for all courses taken.

        Cost = sum(total_units × take_var)

        This is the BASE optimization objective in the tier-based system.
        """
        terms = []

        for (course_idx, semester), var in take_vars.items():
            units = context.courses_df[course_idx, 'total_units']
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
        return {}

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

        terms = []

        for (course_idx, semester), var in take_vars.items():
            course_id = context.courses_df[course_idx, 'subject_id'] if 'subject_id' in context.courses_df.columns else None
            units = context.courses_df[course_idx, 'total_units'] if 'total_units' in context.courses_df.columns else 12

            # Skip courses with user markers - they explicitly want these
            if course_id and course_id in marked_course_ids:
                continue

            if units is not None and units < self.min_units:
                # Penalize taking this small class with tier-based penalty
                terms.append(var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.constant(0)
