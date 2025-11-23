"""
Schedule-based objectives: minimize Fridays, avoid IAP.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext, get_tier_penalty
from .utils import preprocess_schedule_data


class MinimizeFridayClasses:
    """
    Tier-based soft constraint to avoid classes that meet on Friday.

    This maximizes long weekends for students who want to minimize Friday schedules.
    """

    def __init__(self):
        """Initialize MinimizeFridayClasses."""
        pass

    def get_name(self) -> str:
        return "Minimize Friday Classes"

    def get_description(self) -> str:
        return "Avoid courses that meet on Fridays (tier-based)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        """Preprocess schedule data to identify Friday classes."""
        return preprocess_schedule_data(courses_df)

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add tier-based penalty for courses that meet on Friday.

        Formula: penalty = violations × TIER_BASE^tier × 1
        """
        # Get tier for this objective (default tier 2 if not set)
        tier = 2
        if context.objective_tiers and 'minimize_friday_classes' in context.objective_tiers:
            tier = context.objective_tiers['minimize_friday_classes']

        penalty = get_tier_penalty(tier, base_cost=1)

        if context.extra is None or 'has_friday' not in context.extra:
            return cp_model.LinearExpr.constant(0)

        has_friday = context.extra['has_friday']
        terms = []

        for (course_idx, semester), var in take_vars.items():
            if has_friday.get(course_idx, False):
                terms.append(var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.constant(0)


class AvoidIAP:
    """
    Tier-based soft constraint to avoid placing classes during IAP (January term).
    
    IAP is semester index % 3 == 2 (Freshman IAP = 2, Sophomore IAP = 5, Junior IAP = 8, Senior IAP = 11)
    """

    def __init__(self):
        """Initialize AvoidIAP."""
        pass

    def get_name(self) -> str:
        return "Avoid IAP Classes"

    def get_description(self) -> str:
        return "Penalize placing classes during IAP (tier-based)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        """No preprocessing needed for IAP constraint."""
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add tier-based penalty for courses taken during IAP.

        Formula: penalty = violations × TIER_BASE^tier × 1
        """
        # Get tier for this objective (default tier 2 if not set)
        tier = 2
        if context.objective_tiers and 'avoid_iap' in context.objective_tiers:
            tier = context.objective_tiers['avoid_iap']

        penalty = get_tier_penalty(tier, base_cost=1)

        terms = []

        for (course_idx, semester), var in take_vars.items():
            # IAP semesters: 2, 5, 8, 11 (semester % 3 == 2 and semester >= 1)
            # Must exclude ASE (semester -1) which also has -1 % 3 == 2 in Python
            if semester >= 1 and semester % 3 == 2:
                terms.append(var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.constant(0)


class MinimumClassesPerSemester:
    """
    Tier-based soft constraint to penalize semesters with too few classes.
    
    This prevents the optimizer from creating unrealistic schedules with single-class semesters.
    """

    def __init__(self, min_classes: int = 2):
        """
        Initialize MinimumClassesPerSemester.
        
        Args:
            min_classes: Minimum number of classes per semester (default 2)
        """
        self.min_classes: int = min_classes

    def get_name(self) -> str:
        return f"Min {self.min_classes} Classes Per Semester"

    def get_description(self) -> str:
        return f"Penalize semesters with fewer than {self.min_classes} classes (tier-based)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        """No preprocessing needed."""
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add tier-based penalty for semesters with too few classes.

        For each semester with at least 1 class, penalize if class count < min_classes.
        """
        # Get tier for this objective (default tier 3 if not set)
        tier = 3
        if context.objective_tiers and 'minimum_classes_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['minimum_classes_per_semester']

        penalty = get_tier_penalty(tier, base_cost=1)

        # Group take_vars by semester
        semesters_with_vars: dict[int, list[cp_model.IntVar]] = {}
        for (course_idx, semester), var in take_vars.items():
            if semester not in semesters_with_vars:
                semesters_with_vars[semester] = []
            semesters_with_vars[semester].append(var)

        terms = []

        for semester, vars_in_semester in semesters_with_vars.items():
            # Skip IAP semesters (2, 5, 8, 11) - it's normal to have 0-1 classes during IAP
            # Also skip ASE (semester -1) which also has -1 % 3 == 2 in Python
            if semester >= 1 and semester % 3 == 2:
                continue
            # Skip ASE explicitly
            if semester < 1:
                continue

            # Count how many classes are taken in this semester
            class_count = model.NewIntVar(0, len(vars_in_semester), f'class_count_s{semester}')
            model.Add(class_count == cp_model.LinearExpr.Sum(vars_in_semester))

            # Check if semester is active (has at least 1 class)
            semester_active = model.NewBoolVar(f'semester_active_s{semester}')
            model.Add(class_count >= 1).OnlyEnforceIf(semester_active)
            model.Add(class_count == 0).OnlyEnforceIf(semester_active.Not())

            # If semester is active and has fewer than min_classes, incur penalty
            # Penalty = (min_classes - class_count) for active semesters with < min_classes
            for target_count in range(1, self.min_classes):
                # If semester has exactly target_count classes (which is < min_classes)
                has_target_count = model.NewBoolVar(f'semester_s{semester}_has_{target_count}')
                model.Add(class_count == target_count).OnlyEnforceIf(has_target_count)
                model.Add(class_count != target_count).OnlyEnforceIf(has_target_count.Not())

                # Penalty = (min_classes - target_count) * penalty
                shortage = self.min_classes - target_count
                terms.append(has_target_count * shortage * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.constant(0)
