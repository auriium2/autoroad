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
    - X.UAR (Undergraduate Advanced Research)
    - X.URG (Graduate Research)
    - X.THU (Undergraduate Thesis)
    - X.THG (Graduate Thesis)
    """
    SPECIAL_PREFIXES: tuple[str, ...] = ("ES.", "CC.", "STS.")
    # Patterns that can appear after the department number (e.g., 6.UR, 18.THU)
    SPECIAL_SUFFIXES: tuple[str, ...] = (".UR", ".UAR", ".URG", ".THU", ".THG")

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

        # Collect one take-var per HASS course (deduplicate across semesters)
        course2var: dict[int, cp_model.IntVar] = {}
        for (course_idx, semester), var in take_vars.items():
            if is_hass[course_idx] and course_idx not in course2var:
                course_vars = [v for (ci, s), v in take_vars.items() if ci == course_idx]
                taken = model.NewBoolVar(f'hass_taken_{course_idx}')
                model.AddMaxEquality(taken, course_vars)
                course2var[course_idx] = taken

        if not course2var:
            return cp_model.LinearExpr.constant(0)

        hass_count = model.NewIntVar(0, len(course2var), 'hass_count')
        model.Add(hass_count == sum(course2var.values()))

        excess = model.NewIntVar(0, len(course2var), 'excess_hass')
        model.AddMaxEquality(excess, [hass_count - 8, 0])

        return excess * penalty


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

        For each non-frozen, non-IAP semester, penalize if class count < min_classes.
        This includes completely empty semesters (0 classes gets full penalty).
        Frozen past semesters (when lock_past_semesters is enabled) are skipped.
        """
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
            # Skip ASE
            if semester < 1:
                continue
            # Skip IAP semesters (2, 5, 8, 11)
            if semester >= 1 and semester % 3 == 2:
                continue
            # Skip frozen past semesters
            if context.lock_past_semesters and semester <= context.current_semester:
                continue

            class_count = model.NewIntVar(0, len(vars_in_semester), f'class_count_s{semester}')
            model.Add(class_count == cp_model.LinearExpr.Sum(vars_in_semester))

            # Penalize each count from 0 to min_classes-1
            for target_count in range(0, self.min_classes):
                has_target_count = model.NewBoolVar(f'semester_s{semester}_has_{target_count}')
                model.Add(class_count == target_count).OnlyEnforceIf(has_target_count)
                model.Add(class_count != target_count).OnlyEnforceIf(has_target_count.Not())

                shortage = self.min_classes - target_count
                terms.append(has_target_count * shortage * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.constant(0)
