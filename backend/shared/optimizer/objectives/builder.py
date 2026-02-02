"""
Objective builder for composing multiple objective components.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveComponent, ObjectiveContext


class ObjectiveBuilder:
    """
    Builder for composing multiple objective components with weights.

    Usage:
        builder = ObjectiveBuilder()
        builder.add(MinimizeUnits())
        builder.add(LimitClassesPerSemester(max_classes=4))

        objective = builder.build(model, take_vars, courses_df, planning_year_start)
        model.Minimize(objective)
    """

    def __init__(self):
        """Initialize the builder."""
        self.components: list[ObjectiveComponent] = []
        self.component_keys: list[str | None] = []  # Store keys for each component
        self.component_expressions: list[tuple[str, cp_model.LinearExpr]] = []  # Store (key, expr) for breakdown

    def add(self, component: ObjectiveComponent, key: str | None = None) -> ObjectiveBuilder:
        """
        Add an objective component.

        Args:
            component: Objective component to add
            key: Optional key for the objective (used for cost breakdown matching)

        Returns:
            Self for method chaining
        """
        self.components.append(component)
        self.component_keys.append(key)
        return self

    def build(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        courses_df: pl.DataFrame,
        planning_year_start: int,
        objective_tiers: dict[str, int] | None = None,
        requirement_tiers: dict[str, int] | None = None,
        marked_course_ids: set[str] | None = None,
        course_to_requirements: dict[int, set[str]] | None = None,
        lock_past_semesters: bool = False,
        current_semester: int = 0
    ) -> cp_model.LinearExpr:
        """
        Build the combined objective function.

        Args:
            model: CP-SAT model
            take_vars: Decision variables mapping (course_idx, semester) -> BoolVar
            courses_df: DataFrame with course data
            planning_year_start: Starting year for planning
            objective_tiers: Tier priorities for objectives (1-4)
            requirement_tiers: Tier priorities for requirement tree nodes (0-3)
            marked_course_ids: Set of course IDs that have markers
            course_to_requirements: Mapping from course indices to requirement paths they satisfy

        Returns:
            Linear expression to minimize
        """
        if not self.components:
            # No objectives specified, return empty sum
            return cp_model.LinearExpr.Sum([])

        # Preprocess: collect all preprocessing data
        extra_data: dict[str, Any] = {}
        for component in self.components:
            preprocessed = component.preprocess(courses_df)
            extra_data.update(preprocessed)

        # Add course_to_requirements mapping to extra data for category rewards
        if course_to_requirements is not None:
            extra_data['course_to_requirements'] = course_to_requirements

        # Create context
        context = ObjectiveContext(
            planning_year_start=planning_year_start,
            courses_df=courses_df,
            objective_tiers=objective_tiers,
            requirement_tiers=requirement_tiers,
            lock_past_semesters=lock_past_semesters,
            current_semester=current_semester,
            marked_course_ids=marked_course_ids,
            extra=extra_data
        )

        # Build objective terms
        terms = []
        self.component_expressions = []  # Clear previous expressions

        for i, component in enumerate(self.components):
            # Get the linear expression from this component
            expr = component.add_to_model(model, take_vars, context)

            # Skip zero expressions
            if isinstance(expr, int) and expr == 0:
                continue

            # Use key (should always be provided)
            identifier = self.component_keys[i] or f"objective_{i}"

            # Check if this is CategoryRewards with per-category breakdowns
            from .categories import CategoryRewards
            if isinstance(component, CategoryRewards) and component.category_terms:
                # Store per-category expressions for detailed breakdown
                for req_path, category_terms in component.category_terms.items():
                    category_expr = cp_model.LinearExpr.Sum(category_terms)
                    self.component_expressions.append((f"category:{req_path}", category_expr))
            else:
                # Store the expression for later breakdown calculation
                self.component_expressions.append((identifier, expr))

            terms.append(expr)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])

    def clear(self) -> ObjectiveBuilder:
        """Clear all components."""
        self.components.clear()
        return self

    def remove_by_type(self, component_type: type) -> ObjectiveBuilder:
        """Remove all components of a specific type."""
        self.components = [
            c for c in self.components
            if not isinstance(c, component_type)
        ]
        return self

    def calculate_cost_breakdown(
        self,
        solver: cp_model.CpSolver
    ) -> dict[str, int]:
        """
        Calculate the cost breakdown for the current solution.

        Uses the expressions stored during build() to evaluate costs.

        Args:
            solver: Solved CP-SAT solver with solution

        Returns:
            Dictionary mapping objective name to cost contribution
        """
        breakdown = {}

        for name, expr in self.component_expressions:
            # Evaluate the expression with the current solution
            if isinstance(expr, int):
                cost = expr
            else:
                # Use solver.Value() to evaluate the linear expression
                try:
                    cost = solver.Value(expr)
                except Exception as e:
                    print(f"[WARNING] Failed to evaluate cost for {name}: {e}")
                    cost = 0

            breakdown[name] = cost

        return breakdown
