"""
Base classes for objective function components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd
from ortools.sat.python import cp_model

# Global scaling factor for converting float weights to integers
OBJECTIVE_SCALE = 10000


@dataclass
class ObjectiveContext:
    """
    Context information passed to objective components.

    Contains metadata and helper data structures needed by objectives.
    """
    planning_year_start: int
    courses_df: pd.DataFrame

    # Preprocessed schedule data (populated by preprocessing step)
    has_friday: dict[int, bool] | None = None
    time_slots: dict[int, list[tuple[str, int]]] | None = None  # (days, start_time_minutes)

    # Any additional context data
    extra: dict[str, Any] | None = None


class ObjectiveComponent(Protocol):
    """
    Protocol for objective function components.

    Each component represents a single optimization goal (e.g., minimize units,
    maximize ratings). Components can be combined with weights using ObjectiveBuilder.
    """

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add this objective component to the model.

        Args:
            model: The CP-SAT model
            take_vars: Dict mapping (course_idx, semester) -> decision variable
            context: Context with courses data and metadata

        Returns:
            A linear expression representing the cost to MINIMIZE.
            For maximization objectives, return negative values.
        """
        ...

    def get_name(self) -> str:
        """Return a human-readable name for this objective."""
        ...

    def get_description(self) -> str:
        """Return a description of what this objective does."""
        ...

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        """
        Optional preprocessing step to extract/compute data from courses_df.

        This is called once before optimization. Use this to parse schedules,
        compute derived fields, etc.

        Returns:
            Dictionary of preprocessed data to be stored in ObjectiveContext
        """
        ...


