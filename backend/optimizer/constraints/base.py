"""
Base classes for hard constraint components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import polars as pl
from ortools.sat.python import cp_model


@dataclass
class ConstraintContext:
    """
    Context information passed to constraint components.

    Contains metadata and helper data structures needed by constraints.
    """
    planning_year_start: int
    courses_df: pl.DataFrame
    max_semesters: int

    # Marker data (for constraints that need to check user placements)
    markers: list[Any] | None = None

    # Any additional context data
    extra: dict[str, Any] | None = None


class HardConstraint(Protocol):
    """
    Protocol for hard constraint components.

    Each component represents a hard constraint that must be satisfied
    (e.g., ban IAP, lock past semesters). Unlike soft constraints (objectives),
    these are binary - they either pass or fail.
    """

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ConstraintContext
    ) -> None:
        """
        Add this hard constraint to the model.

        Args:
            model: The CP-SAT model
            take_vars: Dict mapping (course_idx, semester) -> decision variable
            context: Context with courses data and metadata
        """
        ...

    def get_name(self) -> str:
        """Return a human-readable name for this constraint."""
        ...

    def get_description(self) -> str:
        """Return a description of what this constraint does."""
        ...

    def get_category(self) -> str:
        """Return the category (e.g., 'scheduling', 'workload')."""
        ...
