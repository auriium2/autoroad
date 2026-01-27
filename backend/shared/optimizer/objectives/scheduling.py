"""
Schedule-based objectives: avoid IAP, avoid special classes.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext, get_tier_penalty

class AvoidIAP:
    def __init__(self):
        pass

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
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


class AvoidSpecialClasses:
    SPECIAL_PREFIXES: tuple[str, ...] = ("ES.", "CC.", "STS.")

    def __init__(self):
        pass

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        subject_ids = courses_df['subject_id'].to_list()
        is_special = [
            any(str(sid).startswith(prefix) for prefix in self.SPECIAL_PREFIXES)
            for sid in subject_ids
        ]
        return {'_is_special_class': is_special, '_subject_ids': subject_ids}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        tier = 2
        if context.objective_tiers and 'avoid_special_classes' in context.objective_tiers:
            tier = context.objective_tiers['avoid_special_classes']

        penalty = get_tier_penalty(tier, base_cost=1)

        if context.extra is None or '_is_special_class' not in context.extra:
            return cp_model.LinearExpr.constant(0)

        is_special = context.extra['_is_special_class']
        terms = []

        for (course_idx, semester), var in take_vars.items():
            if is_special[course_idx]:
                terms.append(var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.constant(0)


class MinimumClassesPerSemester:
    def __init__(self, min_classes: int = 2):
        self.min_classes: int = min_classes

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
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
