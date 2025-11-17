"""
Objective builder for composing multiple objective components.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import OBJECTIVE_SCALE, ObjectiveComponent, ObjectiveContext


class ObjectiveBuilder:
    """
    Builder for composing multiple objective components with weights.

    Usage:
        builder = ObjectiveBuilder()
        builder.add(MinimizeUnits(), weight=0.3)
        builder.add(MaximizeRating(), weight=0.5)
        builder.add(FrontloadCourses(), weight=0.2)

        objective = builder.build(model, take_vars, courses_df, planning_year_start)
        model.Minimize(objective)
    """

    def __init__(self, normalize_weights: bool = True):
        """
        Args:
            normalize_weights: If True, normalize weights to sum to 1.0.
                             If False, use weights as-is.
        """
        self.components: list[tuple[ObjectiveComponent, float]] = []
        self.normalize_weights = normalize_weights

    def add(self, component: ObjectiveComponent, weight: float = 1.0) -> ObjectiveBuilder:
        """
        Add an objective component with a weight.

        Args:
            component: Objective component to add
            weight: Weight for this component (will be normalized if normalize_weights=True)

        Returns:
            Self for method chaining
        """
        if weight < 0:
            raise ValueError(f"Weight must be non-negative, got {weight}")

        self.components.append((component, weight))
        return self

    def build(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        courses_df: pl.DataFrame,
        planning_year_start: int
    ) -> cp_model.LinearExpr:
        """
        Build the combined objective function.

        Args:
            model: CP-SAT model
            take_vars: Decision variables mapping (course_idx, semester) -> BoolVar
            courses_df: DataFrame with course data
            planning_year_start: Starting year for planning

        Returns:
            Linear expression to minimize
        """
        if not self.components:
            # No objectives specified, return 0
            from ortools.sat.python.cp_model import LinearExpr
            return LinearExpr.Sum([])

        # Normalize weights if requested
        if self.normalize_weights:
            total_weight = sum(w for _, w in self.components)
            if total_weight == 0:
                raise ValueError("Total weight is 0, cannot normalize")
            weights = [(c, w / total_weight) for c, w in self.components]
        else:
            weights = self.components

        # Preprocess: collect all preprocessing data
        extra_data: dict[str, Any] = {}
        for component, _ in self.components:
            preprocessed = component.preprocess(courses_df)
            extra_data.update(preprocessed)

        # Create context
        context = ObjectiveContext(
            planning_year_start=planning_year_start,
            courses_df=courses_df,
            extra=extra_data
        )

        # Build objective terms
        terms = []
        for component, weight in weights:
            # Get the linear expression from this component
            expr = component.add_to_model(model, take_vars, context)

            # Scale weight to integer
            scaled_weight = int(weight * OBJECTIVE_SCALE)

            # Add weighted term
            # Note: expr might be 0 (int) or LinearExpr, check weight only
            if scaled_weight != 0:
                if isinstance(expr, int) and expr == 0:
                    # Skip zero expressions
                    continue
                terms.append(expr * scaled_weight)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        from ortools.sat.python.cp_model import LinearExpr
        return LinearExpr.Sum([])

    def get_summary(self) -> str:
        """
        Get a human-readable summary of the objectives.

        Returns:
            Multi-line string describing the objectives and their weights
        """
        if not self.components:
            return "No objectives defined"

        # Compute normalized weights
        if self.normalize_weights:
            total_weight = sum(w for _, w in self.components)
            weights = [(c, w / total_weight) for c, w in self.components]
        else:
            weights = self.components

        lines = ["Objective Function:"]
        for component, weight in weights:
            percentage = weight * 100
            name = component.get_name()
            desc = component.get_description()
            lines.append(f"  {percentage:5.1f}% - {name}")
            if desc:
                lines.append(f"         {desc}")

        return "\n".join(lines)

    def clear(self) -> ObjectiveBuilder:
        """Clear all components."""
        self.components.clear()
        return self

    def remove_by_type(self, component_type: type) -> ObjectiveBuilder:
        """Remove all components of a specific type."""
        self.components = [
            (c, w) for c, w in self.components
            if not isinstance(c, component_type)
        ]
        return self
