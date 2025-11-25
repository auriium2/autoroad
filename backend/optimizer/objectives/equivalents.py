"""
Equivalent courses objective: discourage taking multiple equivalent courses.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from optimizer.semesters import VALID_SEMESTERS

from .base import ObjectiveContext, get_tier_penalty


class DiscourageEquivalentCourses:
    """
    Tier-based soft constraint to discourage taking multiple equivalent courses (e.g., 18.01 and ES.1801).

    Applies a tier-based penalty for each pair of equivalent courses taken. Taking both courses
    in an equivalency group is fundamentally redundant since they satisfy the same requirements.

    Formula: penalty = 2 × TIER_BASE^tier per pair
    """

    def __init__(self, custom_equivalencies: dict[str, list[str]] | None = None):
        """
        Args:
            custom_equivalencies: User-defined equivalency groups. Format: {"courseId": ["equiv1", "equiv2"]}
        """
        self.custom_equivalencies: dict[str, list[str]] | None = custom_equivalencies

    def get_name(self) -> str:
        return "Discourage Equivalent Courses"

    def get_description(self) -> str:
        return "Discourage taking multiple equivalent courses (e.g., 18.01 and ES.1801) using tier-based penalties"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        """
        Build equivalency groups for efficient lookup.

        Merges equivalencies from:
        1. Fireroad API (equivalent_subjects column)
        2. User custom equivalencies (from constructor)
        """
        custom_equivalencies = self.custom_equivalencies

        subject_ids = courses_df['subject_id'].to_list()
        equiv_subjects = courses_df['equivalent_subjects'].to_list() if 'equivalent_subjects' in courses_df.columns else None

        # Build merged equivalency map: courseId -> set of equivalent courseIds
        equiv_map: dict[str, set[str]] = {}

        # 1. Add equivalencies from Fireroad API
        if equiv_subjects is not None:
            for i, (course_id, equiv_data) in enumerate(zip(subject_ids, equiv_subjects)):
                if equiv_data is not None:
                    equiv_list = equiv_data.to_list() if hasattr(equiv_data, 'to_list') else list(equiv_data) if hasattr(equiv_data, '__iter__') else []
                    if equiv_list:
                        if course_id not in equiv_map:
                            equiv_map[course_id] = set()
                        equiv_map[course_id].update(equiv_list)

        # 2. Merge custom user equivalencies
        if custom_equivalencies:
            for course_id, equivalents in custom_equivalencies.items():
                if course_id not in equiv_map:
                    equiv_map[course_id] = set()
                equiv_map[course_id].update(equivalents)

        # Build equivalency groups from the merged map
        equiv_groups = []
        processed = set()
        course_id_to_idx = {cid: i for i, cid in enumerate(subject_ids)}

        for course_id, equivalents in equiv_map.items():
            if not equivalents:
                continue

            # Create sorted tuple of equivalency group
            equiv_group = tuple(sorted([course_id] + list(equivalents)))

            if equiv_group in processed:
                continue
            processed.add(equiv_group)

            # Find course indices that exist in catalog
            equiv_indices = []
            for equiv_course_id in equiv_group:
                if equiv_course_id in course_id_to_idx:
                    equiv_indices.append(course_id_to_idx[equiv_course_id])

            if len(equiv_indices) > 1:
                equiv_groups.append(equiv_indices)

        return {'equiv_groups': equiv_groups}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Penalize for each pair of equivalent courses taken using tier-based penalties.

        For each equivalency group, we count how many courses from that group are taken,
        then penalize for taking more than one.

        Formula: penalty = 2 × TIER_BASE^tier per pair
        """
        if context.extra is None or 'equiv_groups' not in context.extra:
            return cp_model.LinearExpr.constant(0)

        equiv_groups = context.extra['equiv_groups']
        if not equiv_groups:
            return cp_model.LinearExpr.constant(0)

        # Get tier for this objective (default tier 4 - should almost never violate)
        tier = 4
        if context.objective_tiers and 'discourage_equivalent_courses' in context.objective_tiers:
            tier = context.objective_tiers['discourage_equivalent_courses']

        penalty = get_tier_penalty(tier + 1, base_cost=1)

        terms = []
        pair_counter = 0

        for group_idx, equiv_indices in enumerate(equiv_groups):
            # For each equivalency group, we want to penalize taking multiple DIFFERENT courses
            # Not taking the same course in different semesters (that's already prevented)
            # So we create one indicator per COURSE (summing across all semesters)

            course_indicators = []

            for course_idx in equiv_indices:
                # Collect all take variables for this specific course across semesters
                course_takes = []
                for semester in VALID_SEMESTERS:
                    if (course_idx, semester) in take_vars:
                        course_takes.append(take_vars[(course_idx, semester)])

                if course_takes:
                    # Create indicator: is this course taken in ANY semester?
                    course_taken = model.NewBoolVar(f'equiv_course_g{group_idx}_c{course_idx}')
                    model.AddMaxEquality(course_taken, course_takes)
                    course_indicators.append(course_taken)

            if len(course_indicators) < 2:
                continue

            # Now penalize for each pair of COURSES taken (not semester pairs)
            for i in range(len(course_indicators)):
                for j in range(i + 1, len(course_indicators)):
                    # Create boolean variable: are both courses taken?
                    pair_taken = model.NewBoolVar(f'equiv_pair_g{group_idx}_{pair_counter}')
                    pair_counter += 1

                    # pair_taken = 1 if both courses are taken (in any semester)
                    model.AddMultiplicationEquality(pair_taken, [course_indicators[i], course_indicators[j]])

                    # Add tier-based penalty for this pair
                    terms.append(pair_taken * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])
