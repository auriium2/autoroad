"""
Base classes for objective function components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import polars as pl
from ortools.sat.python import cp_model

# Global scaling factor for converting float weights to integers (DEPRECATED in tier-based system)
OBJECTIVE_SCALE = 10000

# Tier penalty multiplier
TIER_BASE = 5

def get_tier_penalty(tier: int, base_cost: int = 1) -> int:
    """
    Calculate penalty for a given tier.

    Args:
        tier: Tier level (1-4)
        base_cost: Base cost per violation (default 1 unit)

    Returns:
        Penalty = base_cost × (TIER_BASE^tier)
    """
    if tier < 1 or tier > 4:
        tier = 2  # Default to tier 2 if invalid
    return base_cost * (TIER_BASE ** tier)

def get_tier_penalty_hacked(tier: int, base_cost: int = 1) -> int:
    """
    Calculate penalty for a given tier. Hacked so that a certain equivalents constraint can use it

    Args:
        tier: Tier level (1-5)
        base_cost: Base cost per violation (default 1 unit)

    Returns:
        Penalty = base_cost × (TIER_BASE^tier)
    """
    if tier < 1 or tier > 5:
        tier = 2  # Default to tier 2 if invalid
    return base_cost * (TIER_BASE ** tier)


@dataclass
class ObjectiveContext:
    """
    Context information passed to objective components.

    Contains metadata and helper data structures needed by objectives.
    """
    planning_year_start: int
    courses_df: pl.DataFrame

    # Preprocessed schedule data (populated by preprocessing step)
    time_slots: dict[int, list[tuple[str, int]]] | None = None  # (days, start_time_minutes)

    # Tier data for soft constraints and category rewards
    objective_tiers: dict[str, int] | None = None  # Tier (1-4) for each objective key
    requirement_tiers: dict[str, int] | None = None  # Tier (0-3) for each requirement tree path

    # Marker data (set of course_ids that have user markers)
    marked_course_ids: set[str] | None = None

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
            Return LinearExpr.constant(0) if this objective doesn't apply.
        """
        ...

    def get_name(self) -> str:
        """Return a human-readable name for this objective."""
        ...

    def get_description(self) -> str:
        """Return a description of what this objective does."""
        ...

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        """
        Optional preprocessing step to extract/compute data from courses_df.

        This is called once before optimization. Use this to parse schedules,
        compute derived fields, etc.

        Returns:
            Dictionary of preprocessed data to be stored in ObjectiveContext
        """
        ...
