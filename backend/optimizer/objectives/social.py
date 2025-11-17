"""
Social objectives: maximize cohort overlap.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from ortools.sat.python import cp_model

from .base import ObjectiveContext


class MaximizeCohortOverlap:
    """
    Objective to prefer courses with higher enrollment (more classmates).

    Uses a penalty approach based on enrollment deficit from a target size.
    This avoids rewarding taking more courses just to maximize total enrollment.

    Scale: Normalized to ~100 per course. With target=50 and typical deficit ~25,
           scaled by 4 → 100.
    """

    def __init__(self, target_enrollment: int = 50):
        """
        Args:
            target_enrollment: Target class size. Courses below this get penalized.
                             Default 50 students (scaled by 4 to get ~100 cost per course).
        """
        self.target_enrollment = target_enrollment

    def get_name(self) -> str:
        return "Maximize Cohort Overlap"

    def get_description(self) -> str:
        return f"Prefer courses with higher enrollment (target: {self.target_enrollment} students)"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Penalize courses based on enrollment deficit from target.

        Cost = sum(max(0, target - enrollment) * 4 * take_var)

        Courses at or above target enrollment have 0 penalty.
        Courses below target are penalized proportionally.
        Scaled by 4 to normalize to ~100 per course.
        """
        terms = []

        for (course_idx, semester), var in take_vars.items():
            enrollment = context.courses_df.at[course_idx, 'enrollment_number'] if 'enrollment_number' in context.courses_df.columns else None

            if enrollment is not None and pd.notna(enrollment) and enrollment > 0:
                # Penalty for being below target enrollment, scaled by 4
                deficit = max(0, self.target_enrollment - int(enrollment))  # type: ignore[arg-type]
                if deficit > 0:
                    terms.append(var * deficit * 4)
            else:
                # No enrollment data - maximum penalty
                terms.append(var * self.target_enrollment * 4)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])  # type: ignore[return-value]
