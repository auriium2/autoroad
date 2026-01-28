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
    """
    Penalize special classes that most students don't take.
    
    Includes:
    - ES. (Experimental Study Group)
    - CC. (Concourse)
    - STS. (Science, Technology, and Society)
    - X.UR (Undergraduate Research)
    - X.URG (Graduate Research)
    - X.THU (Undergraduate Thesis)
    - X.THG (Graduate Thesis)
    """
    SPECIAL_PREFIXES: tuple[str, ...] = ("ES.", "CC.", "STS.")
    # Patterns that can appear after the department number (e.g., 6.UR, 18.THU)
    SPECIAL_SUFFIXES: tuple[str, ...] = (".UR", ".URG", ".THU", ".THG")

    def __init__(self):
        pass

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        subject_ids = courses_df['subject_id'].to_list()
        is_special = []
        for sid in subject_ids:
            sid_str = str(sid).upper()
            is_prefix_match = any(sid_str.startswith(prefix.upper()) for prefix in self.SPECIAL_PREFIXES)
            is_suffix_match = any(suffix.upper() in sid_str for suffix in self.SPECIAL_SUFFIXES)
            is_special.append(is_prefix_match or is_suffix_match)
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


class AvoidClassesWithPrefix:
    def __init__(self, prefixes: list[str] | None = None):
        self.prefixes: list[str] = prefixes or []

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        subject_ids = courses_df['subject_id'].to_list()
        return {'_subject_ids': subject_ids}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        if not self.prefixes:
            return cp_model.LinearExpr.constant(0)

        tier = 2
        if context.objective_tiers and 'avoid_classes_with_prefix' in context.objective_tiers:
            tier = context.objective_tiers['avoid_classes_with_prefix']

        penalty = get_tier_penalty(tier, base_cost=1)

        subject_ids = (context.extra.get('_subject_ids') if context.extra else None) or context.courses_df['subject_id'].to_list()
        
        # Normalize prefixes to uppercase for case-insensitive matching
        prefixes_upper = [p.upper() for p in self.prefixes]
        
        terms = []
        for (course_idx, semester), var in take_vars.items():
            sid = str(subject_ids[course_idx]).upper()
            if any(sid.startswith(prefix) for prefix in prefixes_upper):
                terms.append(var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.constant(0)


class AvoidHASSClasses:
    """
    Penalize HASS classes to prefer technical courses when possible.
    
    Useful for students who want to minimize humanities/arts/social science
    courses and focus on technical requirements.
    """

    def __init__(self):
        pass

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        hass_attr = courses_df['hass_attribute'].to_list() if 'hass_attribute' in courses_df.columns else [None] * len(courses_df)
        is_hass = [
            bool(attr) and attr in ('HASS-A', 'HASS-H', 'HASS-S', 'HASS-E')
            for attr in hass_attr
        ]
        return {'_is_hass': is_hass}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        tier = 2
        if context.objective_tiers and 'avoid_hass_classes' in context.objective_tiers:
            tier = context.objective_tiers['avoid_hass_classes']

        penalty = get_tier_penalty(tier, base_cost=1)

        if context.extra is None or '_is_hass' not in context.extra:
            return cp_model.LinearExpr.constant(0)

        is_hass = context.extra['_is_hass']
        terms = []

        for (course_idx, semester), var in take_vars.items():
            if is_hass[course_idx]:
                terms.append(var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)
        return cp_model.LinearExpr.constant(0)


class AvoidSpecialTopics:
    """
    Penalize special topics courses (X.SYYY pattern like 6.S040, 18.S097).
    
    These are typically one-off experimental courses that may not be offered
    regularly. Not enabled by default since some students specifically want
    to take these courses.
    """

    def __init__(self):
        pass

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        import re
        subject_ids = courses_df['subject_id'].to_list()
        # Pattern: department number, dot, S, then digits (e.g., 6.S040, 18.S097)
        special_topics_pattern = re.compile(r'^\d+\.S\d+', re.IGNORECASE)
        is_special_topics = [
            bool(special_topics_pattern.match(str(sid)))
            for sid in subject_ids
        ]
        return {'_is_special_topics': is_special_topics}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        tier = 2
        if context.objective_tiers and 'avoid_special_topics' in context.objective_tiers:
            tier = context.objective_tiers['avoid_special_topics']

        penalty = get_tier_penalty(tier, base_cost=1)

        if context.extra is None or '_is_special_topics' not in context.extra:
            return cp_model.LinearExpr.constant(0)

        is_special_topics = context.extra['_is_special_topics']
        terms = []

        for (course_idx, semester), var in take_vars.items():
            if is_special_topics[course_idx]:
                terms.append(var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)
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
