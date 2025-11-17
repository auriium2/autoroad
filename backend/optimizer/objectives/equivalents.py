"""
Equivalent courses objective: discourage taking multiple equivalent courses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import OBJECTIVE_SCALE, ObjectiveContext


class DiscourageEquivalentCourses:
    """
    Soft constraint to discourage taking multiple equivalent courses (e.g., 18.01 and 18.01L).

    Applies a penalty for each pair of equivalent courses taken. Taking both courses in an
    equivalency group is fundamentally redundant since they satisfy the same requirements.

    Scale: Very high penalty (100M per pair by default) to strongly prevent redundancy.
           Constraints are not scaled by OBJECTIVE_SCALE, so penalties must be in the
           tens of millions to dominate typical objective values (which are scaled ~10000x).
    """

    def __init__(self, penalty_per_pair: int = 100000000):
        """
        Args:
            penalty_per_pair: Penalty for taking two equivalent courses. Default 100M.
        """
        self.penalty_per_pair: int = penalty_per_pair

    def get_name(self) -> str:
        return "Discourage Equivalent Courses"

    def get_description(self) -> str:
        return "Discourage taking multiple equivalent courses (e.g., 18.01 and 18.01L). Not recommended to disable."

    def preprocess(self, courses_df: pl.DataFrame, custom_equivalencies: dict[str, list[str]] | None = None) -> dict[str, Any]:
        """
        Build equivalency groups for efficient lookup.
        
        Merges equivalencies from:
        1. Fireroad API (equivalent_subjects column)
        2. Backend default overrides (data/equivalent_overrides.json)
        3. User custom equivalencies (passed as parameter)
        """
        # Load default equivalency overrides from JSON
        default_overrides = {}
        overrides_path = Path(__file__).parent.parent.parent / "data" / "equivalent_overrides.json"
        if overrides_path.exists():
            try:
                with open(overrides_path) as f:
                    default_overrides = json.load(f)
                print(f"[DEBUG] Loaded {len(default_overrides)} default equivalency overrides")
            except Exception as e:
                print(f"[WARNING] Failed to load equivalency overrides: {e}")
        
        # Build merged equivalency map: courseId -> set of equivalent courseIds
        equiv_map: dict[str, set[str]] = {}
        
        # 1. Add equivalencies from Fireroad API
        if 'equivalent_subjects' in courses_df.columns:
            for i in range(len(courses_df)):
                course_id = courses_df[i, 'subject_id']
                equiv_data = courses_df[i, 'equivalent_subjects']
                
                if equiv_data is not None:
                    equiv_list = equiv_data.to_list() if hasattr(equiv_data, 'to_list') else list(equiv_data) if hasattr(equiv_data, '__iter__') else []
                    if equiv_list:
                        if course_id not in equiv_map:
                            equiv_map[course_id] = set()
                        equiv_map[course_id].update(equiv_list)
        
        # 2. Merge default overrides
        for course_id, equivalents in default_overrides.items():
            if course_id not in equiv_map:
                equiv_map[course_id] = set()
            equiv_map[course_id].update(equivalents)
        
        # 3. Merge custom user equivalencies
        if custom_equivalencies:
            print(f"[DEBUG] Merging {len(custom_equivalencies)} custom equivalencies")
            for course_id, equivalents in custom_equivalencies.items():
                if course_id not in equiv_map:
                    equiv_map[course_id] = set()
                equiv_map[course_id].update(equivalents)
        
        # Build equivalency groups from the merged map
        equiv_groups = []
        processed = set()
        course_id_to_idx = {courses_df[i, 'subject_id']: i for i in range(len(courses_df))}
        
        # Debug: check if 6.100A and 6.100L are in the catalog
        print(f"[DEBUG EQUIV PREPROCESS] Checking for 6.100A in catalog: {'6.100A' in course_id_to_idx}")
        print(f"[DEBUG EQUIV PREPROCESS] Checking for 6.100L in catalog: {'6.100L' in course_id_to_idx}")
        if '6.100A' in equiv_map:
            print(f"[DEBUG EQUIV PREPROCESS] 6.100A equivalents: {equiv_map['6.100A']}")
        if '6.100L' in equiv_map:
            print(f"[DEBUG EQUIV PREPROCESS] 6.100L equivalents: {equiv_map['6.100L']}")

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
                # Debug: print equivalency groups
                course_names = [courses_df[idx, 'subject_id'] for idx in equiv_indices]
                if '18.01' in course_names or 'ES.1801' in course_names:
                    print(f"[DEBUG EQUIV PREPROCESS] *** 18.01 GROUP: {course_names}")

        print(f"[DEBUG] Total equivalency groups found: {len(equiv_groups)}")
        return {'equiv_groups': equiv_groups}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Penalize for each pair of equivalent courses taken.

        For each equivalency group, we count how many courses from that group are taken,
        then penalize for taking more than one.
        """
        if context.extra is None or 'equiv_groups' not in context.extra:
            return cp_model.LinearExpr.constant(0)

        equiv_groups = context.extra['equiv_groups']
        if not equiv_groups:
            return cp_model.LinearExpr.constant(0)

        terms = []
        pair_counter = 0

        for group_idx, equiv_indices in enumerate(equiv_groups):
            # For each equivalency group, we want to penalize taking multiple DIFFERENT courses
            # Not taking the same course in different semesters (that's already prevented)
            # So we create one indicator per COURSE (summing across all semesters)

            course_names = [context.courses_df[idx, 'subject_id'] for idx in equiv_indices]
            course_indicators = []

            for course_idx in equiv_indices:
                # Collect all take variables for this specific course across semesters
                course_takes = []
                course_id = context.courses_df[course_idx, 'subject_id']
                for semester in range(-1, 13):  # ASE (-1) through semester 12
                    if (course_idx, semester) in take_vars:
                        course_takes.append(take_vars[(course_idx, semester)])

                if course_takes:
                    # Create indicator: is this course taken in ANY semester?
                    course_taken = model.NewBoolVar(f'equiv_course_g{group_idx}_c{course_idx}')
                    # course_taken = 1 if any semester variable is 1
                    model.AddMaxEquality(course_taken, course_takes)
                    course_indicators.append(course_taken)
                    
                    if '18.01' in course_names or 'ES.1801' in course_names:
                        if course_id in ['18.01', 'ES.1801']:
                            print(f"[DEBUG EQUIV] *** {course_id}: found {len(course_takes)} take_vars across semesters")
                else:
                    print(f"[DEBUG EQUIV] Course {course_id} has NO take variables!")

            if '18.01' in course_names or 'ES.1801' in course_names:
                print(f"[DEBUG EQUIV] *** 18.01 GROUP: {len(course_indicators)} courses have variables")

            if len(course_indicators) < 2:
                continue

            # Now penalize for each pair of COURSES taken (not semester pairs)
            num_pairs = 0
            for i in range(len(course_indicators)):
                for j in range(i + 1, len(course_indicators)):
                    # Create boolean variable: are both courses taken?
                    pair_taken = model.NewBoolVar(f'equiv_pair_g{group_idx}_{pair_counter}')
                    pair_counter += 1
                    num_pairs += 1

                    # pair_taken = 1 if both courses are taken (in any semester)
                    model.AddMultiplicationEquality(pair_taken, [course_indicators[i], course_indicators[j]])

                    # Add penalty for this pair
                    terms.append(pair_taken * self.penalty_per_pair)

            if num_pairs > 0:
                if '18.01' in course_names or 'ES.1801' in course_names:
                    print(f"[DEBUG EQUIV] *** 18.01 GROUP: Created {num_pairs} penalty terms")
                    print(f"[DEBUG EQUIV] *** 18.01 GROUP: penalty_per_pair={self.penalty_per_pair}")
                    print(f"[DEBUG EQUIV] *** 18.01 GROUP: If all pairs violated, would add {num_pairs * self.penalty_per_pair} to objective BEFORE scaling")

        print(f"[DEBUG EQUIV] Total: Created {len(terms)} penalty terms for equivalent course pairs")
        print(f"[DEBUG EQUIV] If ALL {len(terms)} pairs violated: {len(terms) * self.penalty_per_pair} before scaling = {len(terms) * self.penalty_per_pair * 10000} after scaling")
        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.constant(0)
