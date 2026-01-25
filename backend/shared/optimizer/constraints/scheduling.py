"""
Scheduling-related hard constraints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from .base import ConstraintContext


class BanPrefix:
    """
    Hard constraint: Ban all classes with a specific prefix.

    Prevents the optimizer from scheduling any course whose subject_id
    starts with the specified prefix (e.g., "21M" to ban music classes).
    """

    def __init__(self, prefix: str):
        self.prefix: str = prefix

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ConstraintContext
    ) -> None:
        """Add prefix ban constraint to model."""
        for (course_idx, semester), var in take_vars.items():
            subject_id = context.courses_df[course_idx, 'subject_id']
            if subject_id.startswith(self.prefix):
                model.Add(var == 0)

    def get_name(self) -> str:
        return f"Ban {self.prefix} Classes"

    def get_description(self) -> str:
        return f"Hard constraint: prevents taking any classes with prefix '{self.prefix}'."

    def get_category(self) -> str:
        return "scheduling"


class BanIAP:
    """
    Hard constraint: Prevent optimizer from placing any classes in IAP.

    User markers are still allowed - this only prevents the optimizer
    from automatically scheduling classes during IAP semesters.
    """

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ConstraintContext
    ) -> None:
        """Add IAP ban constraint to model."""
        # Get course IDs that have user markers in IAP semesters
        marked_iap_course_ids = set()
        if context.markers:
            for marker in context.markers:
                # IAP semesters: 2, 5, 8, 11 (after converting from 0-indexed section to 1-indexed semester)
                # Section 1, 4, 7, 10 -> Semester 2, 5, 8, 11
                if marker.section >= 0 and (marker.section + 1) % 3 == 2:
                    marked_iap_course_ids.add(marker.courseId)

        # Build course_id -> course_idx mapping
        course_id_to_idx = {}
        for idx in range(len(context.courses_df)):
            subject_id = context.courses_df[idx, 'subject_id']
            course_id_to_idx[subject_id] = idx

        # Ban all non-marked courses from IAP semesters
        for (course_idx, semester), var in take_vars.items():
            # Check if this is an IAP semester (2, 5, 8, 11)
            # Must exclude ASE (semester -1) which also has -1 % 3 == 2 in Python
            if semester >= 1 and semester % 3 == 2:
                # Check if this course has a user marker in IAP
                course_id = context.courses_df[course_idx, 'subject_id']
                if course_id not in marked_iap_course_ids:
                    # Hard constraint: cannot take this course in IAP
                    model.Add(var == 0)

    def get_name(self) -> str:
        return "Ban IAP Classes"

    def get_description(self) -> str:
        return "Hard constraint: prevents optimizer from placing any classes in IAP. Your manual markers still work."

    def get_category(self) -> str:
        return "scheduling"
