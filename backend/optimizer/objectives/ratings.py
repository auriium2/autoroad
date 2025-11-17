"""
Rating-based objectives: maximize course ratings.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext
from .utils import compute_bayesian_rating


class MaximizeRating:
    """
    Objective to prefer highly-rated courses.

    Uses a penalty-based approach: penalizes courses based on how far below
    a target rating they are. This way, taking more courses doesn't
    automatically improve the objective.

    Scale: Normalized to ~100 per course. Deficit of 1.0 rating point × 100 = 100.
           Typical course (rating 5.0 vs target 6.0) → penalty = 100.
    """

    def __init__(self, target_rating: float = 6.0):
        """
        Args:
            target_rating: Target rating threshold. Courses below this get penalized.
                          Default 6.0 is reasonable for MIT (most courses are 4-7).
                          Courses at or above target have no penalty.
        """
        self.target_rating = target_rating

    def get_name(self) -> str:
        return "Maximize Rating"

    def get_description(self) -> str:
        return "Prefer courses with higher ratings (penalize low-rated courses)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Penalize courses based on rating deficit from target.

        Cost = sum(max(0, target - actual_rating) * 100 * take_var)

        This encourages taking high-rated courses without rewarding
        taking more courses total.

        Example (target=6.0):
        - Course with rating 6.5: penalty = 0 (at or above target)
        - Course with rating 6.0: penalty = 0 (at target)
        - Course with rating 5.2: penalty = 80
        - Course with rating 4.8: penalty = 120
        """
        terms = []

        for (course_idx, semester), var in take_vars.items():
            rating = context.courses_df[course_idx, 'rating'] if 'rating' in context.courses_df.columns else None

            if rating is not None and rating > 0:
                # Penalty is how far below target this course is
                # Scale by 100 to preserve decimal precision (e.g., 5.2 vs 4.8)
                deficit = max(0, self.target_rating - rating)
                penalty = int(deficit * 100)
                if penalty > 0:
                    terms.append(var * penalty)
            else:
                # No rating data - assume worst case
                # Assume rating of 4.0 (typical minimum for MIT courses)
                deficit = max(0, self.target_rating - 4.0)
                penalty = int(deficit * 100)
                terms.append(var * penalty)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])  # type: ignore[return-value]


class MaximizeWeightedRating:
    """
    Objective to prefer courses with high Bayesian-weighted ratings.

    Uses penalty-based approach with Bayesian averaging to reduce bias
    from courses with few reviews.

    Scale: Normalized to ~100 per course. Deficit of 1.0 rating point × 100 = 100.
           Similar to MaximizeRating but uses Bayesian weighting.
    """

    def __init__(self, min_votes: int = 10, global_mean: float | None = None, target_rating: float = 6.0):
        """
        Args:
            min_votes: Minimum number of students for a rating to be fully trusted
            global_mean: Global average rating. If None, computed from courses_df
            target_rating: Target rating threshold (default 6.0)
        """
        self.min_votes = min_votes
        self.global_mean = global_mean
        self.target_rating = target_rating
        self._computed_mean: float | None = None

    def get_name(self) -> str:
        return "Maximize Weighted Rating"

    def get_description(self) -> str:
        return (
            f"Prefer courses with high Bayesian-weighted ratings (reduces bias from courses with <{self.min_votes} students)"
        )

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        """Compute global mean rating if not provided."""
        if self.global_mean is None and 'rating' in courses_df.columns:
            # Compute global mean from courses with ratings
            mean_val = courses_df['rating'].drop_nulls().mean()
            self._computed_mean = float(mean_val) if mean_val is not None else 5.0
        else:
            self._computed_mean = self.global_mean or 5.0

        return {'global_mean': self._computed_mean}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Penalize courses based on deficit from target weighted rating.

        Cost = sum(max(0, target - weighted_rating) * 100 * take_var)
        """
        terms = []
        global_mean = self._computed_mean or 5.0

        for (course_idx, semester), var in take_vars.items():
            rating = context.courses_df[course_idx, 'rating'] if 'rating' in context.courses_df.columns else None
            enrollment = context.courses_df[course_idx, 'enrollment_number'] if 'enrollment_number' in context.courses_df.columns else None

            if rating is not None and rating > 0:
                weighted_rating = compute_bayesian_rating(
                    float(rating), enrollment or 0, self.min_votes, global_mean
                )
                # Penalty is deficit from target rating
                deficit = max(0, self.target_rating - weighted_rating)
                penalty = int(deficit * 100)
                if penalty > 0:
                    terms.append(var * penalty)
            else:
                # No rating - assume 4.0
                deficit = max(0, self.target_rating - 4.0)
                penalty = int(deficit * 100)
                terms.append(var * penalty)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])  # type: ignore[return-value]
