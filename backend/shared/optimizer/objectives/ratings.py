"""
Rating-based objectives.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext, get_tier_penalty


class PenalizeLowRatings:
    def __init__(self, threshold: float = 5.5, use_imdb: bool = False):
        self.threshold: float = threshold
        self.use_imdb: bool = use_imdb

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add penalty for courses with ratings below threshold.

        For each course with rating < threshold:
            penalty = ticks_below * (tier_penalty // 10)
        where ticks_below = int((threshold - rating) * 10)

        Example at tier 2 (base penalty 25, scaled to 2):
            - Rating 5.3 with threshold 5.5: 2 ticks * 2 = 4 cost
            - Rating 4.0 with threshold 5.5: 15 ticks * 2 = 30 cost
        """
        tier = 2
        if context.objective_tiers and 'penalize_low_ratings' in context.objective_tiers:
            tier = context.objective_tiers['penalize_low_ratings']

        base_penalty = get_tier_penalty(tier, base_cost=1)
        # Scale down to avoid dominating other objectives
        per_tick_penalty = max(1, base_penalty // 10)

        terms: list[cp_model.LinearExpr] = []

        # Determine which rating column to use
        rating_column = 'imdb_rating' if self.use_imdb else 'rating'

        if rating_column not in context.courses_df.columns:
            return cp_model.LinearExpr.Sum([])

        # Track which courses we've already penalized (avoid double-counting across semesters)
        course_penalties: dict[int, int] = {}

        for course_idx in range(len(context.courses_df)):
            rating = context.courses_df[course_idx, rating_column]

            # Skip courses without rating data
            if rating is None:
                continue

            rating_float = float(rating)
            if rating_float >= self.threshold:
                continue

            # Calculate ticks below threshold (each tick = 0.1 rating points)
            ticks_below = int((self.threshold - rating_float) * 10)
            if ticks_below <= 0:
                continue

            course_penalties[course_idx] = ticks_below * per_tick_penalty

        # Apply penalty when course is taken (in any semester)
        # Create indicator for "course is taken at all"
        for course_idx, penalty in course_penalties.items():
            # Get all semester vars for this course
            course_vars = [
                var for (cidx, sem), var in take_vars.items()
                if cidx == course_idx
            ]

            if not course_vars:
                continue

            # Course is taken if any semester var is 1
            course_taken = model.NewBoolVar(f'course_taken_rating_{course_idx}')
            model.AddMaxEquality(course_taken, course_vars)

            terms.append(course_taken * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.Sum([])
