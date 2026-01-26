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
        import time
        start = time.time()
        constraints_added = 0
        
        for (course_idx, semester), var in take_vars.items():
            subject_id = context.courses_df[course_idx, 'subject_id']
            if subject_id.startswith(self.prefix):
                model.Add(var == 0)
                constraints_added += 1
        
        print(f"[BanPrefix:{self.prefix}] Added {constraints_added} constraints in {time.time() - start:.3f}s")

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
        import time
        start = time.time()
        constraints_added = 0
        
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
                    constraints_added += 1
        
        print(f"[BanIAP] Added {constraints_added} constraints in {time.time() - start:.3f}s")

    def get_name(self) -> str:
        return "Ban IAP Classes"

    def get_description(self) -> str:
        return "Hard constraint: prevents optimizer from placing any classes in IAP. Your manual markers still work."

    def get_category(self) -> str:
        return "scheduling"


def _slots_overlap(slot1: tuple[int, int, int], slot2: tuple[int, int, int]) -> bool:
    """Check if two time slots overlap (same day and overlapping time)."""
    day1, start1, end1 = slot1
    day2, start2, end2 = slot2
    if day1 != day2:
        return False
    return start1 < end2 and start2 < end1


class ScheduleFreeTime:
    """
    Hard constraint: Block off time slots where you don't want classes.
    
    If a course has a required section (only one option for that section type)
    that falls entirely within blocked time, the course is banned.
    
    The blocked_slots parameter is a list of [day, start_hour, end_hour] where:
    - day is 0-4 (Mon-Fri)
    - start_hour and end_hour are in 24-hour format (e.g., 8 for 8am, 17 for 5pm)
    
    The extrapolate parameter controls whether to apply this constraint to future
    semesters using fallback schedule data.
    
    Requires 'hydrant_schedule_data' in context.extra.
    """

    def __init__(self, blocked_slots: list[list[int]] | None = None, extrapolate: bool = False):
        # blocked_slots format: [[day, start_hour, end_hour], ...]
        self.blocked_slots: list[list[int]] = blocked_slots or []
        self.extrapolate: bool = extrapolate

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ConstraintContext
    ) -> None:
        """Add free time constraint to model."""
        import time
        start = time.time()
        constraints_added = 0
        
        if not self.blocked_slots:
            return

        if context.extra is None:
            return

        hydrant_data = context.extra.get('hydrant_schedule_data')
        if not hydrant_data:
            return

        semester_to_slots: dict[int, dict[str, list[tuple[int, int, int]]]] = hydrant_data.get('semester_to_slots', {})
        if not semester_to_slots:
            return

        # Convert blocked_slots from hours to minutes
        blocked_time_slots: list[tuple[int, int, int]] = []
        for slot in self.blocked_slots:
            if len(slot) >= 3:
                day, start_hour, end_hour = slot[0], slot[1], slot[2]
                blocked_time_slots.append((day, start_hour * 60, end_hour * 60))

        if not blocked_time_slots:
            return

        # Build course_id -> course_idx mapping
        course_id_to_idx: dict[str, int] = {}
        for idx in range(len(context.courses_df)):
            subject_id = context.courses_df[idx, 'subject_id']
            course_id_to_idx[subject_id] = idx

        # For each course variable, check if its required slots conflict with blocked time
        for (course_idx, semester), var in take_vars.items():
            course_id_to_slots = semester_to_slots.get(semester, {})
            if not course_id_to_slots:
                continue

            course_id = context.courses_df[course_idx, 'subject_id']
            required_slots = course_id_to_slots.get(course_id, [])

            # Check if any required slot overlaps with any blocked slot
            for req_slot in required_slots:
                for blocked_slot in blocked_time_slots:
                    if _slots_overlap(req_slot, blocked_slot):
                        # This course has a required time that conflicts with blocked time
                        model.Add(var == 0)
                        constraints_added += 1
                        break
                else:
                    continue
                break
        
        print(f"[ScheduleFreeTime] Added {constraints_added} constraints in {time.time() - start:.3f}s")

    def get_name(self) -> str:
        return "Schedule Free Time"

    def get_description(self) -> str:
        return "Hard constraint: blocks off time slots where you don't want classes scheduled."

    def get_category(self) -> str:
        return "scheduling"
