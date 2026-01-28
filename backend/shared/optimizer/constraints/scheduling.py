"""
Scheduling-related hard constraints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from .base import ConstraintContext


def _slots_overlap(slot1: tuple[int, int, int], slot2: tuple[int, int, int]) -> bool:
    """Check if two time slots overlap (same day and overlapping time)."""
    day1, start1, end1 = slot1
    day2, start2, end2 = slot2
    if day1 != day2:
        return False
    return start1 < end2 and start2 < end1


def _option_conflicts_with_blocked(
    option_slots: list[tuple[int, int, int]],
    blocked_slots: list[tuple[int, int, int]]
) -> bool:
    """Check if any slot in an option conflicts with any blocked slot."""
    for slot in option_slots:
        for blocked in blocked_slots:
            if _slots_overlap(slot, blocked):
                return True
    return False


def _course_has_unavoidable_conflict(
    section_types: list[list[list[tuple[int, int, int]]]],
    blocked_slots: list[tuple[int, int, int]]
) -> bool:
    """
    Check if a course has at least one section type where ALL options conflict.
    
    A course should be banned if there's a section type (lecture, recitation, etc.)
    where every available option conflicts with blocked time - meaning there's no
    way to take the course without hitting blocked time.
    """
    for section_type_options in section_types:
        # Check if ALL options for this section type conflict
        all_options_conflict = True
        for option_slots in section_type_options:
            if not _option_conflicts_with_blocked(option_slots, blocked_slots):
                all_options_conflict = False
                break

        if all_options_conflict:
            return True

    return False


class ScheduleFreeTime:
    """
    Hard constraint: Block off time slots where you don't want classes.
    
    A course is banned if it has ANY section type (lecture, recitation, lab, etc.)
    where ALL available options conflict with blocked time. This means even if
    there are multiple recitation options, if they ALL conflict, the course is banned.
    
    The blocked_slots parameter is a list of [day, start_hour, end_hour] where:
    - day is 0-4 (Mon-Fri)
    - start_hour and end_hour are in 24-hour format (e.g., 8 for 8am, 17 for 5pm)
    
    The extrapolate parameter controls whether to apply this constraint to future
    semesters using fallback schedule data.
    
    Requires 'hydrant_schedule_data' in context.extra.
    """

    def __init__(self, blocked_slots: list[list[int]] | None = None, extrapolate: bool = False):
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

        semester_to_section_options = hydrant_data.get('semester_to_section_options', {})
        if not semester_to_section_options:
            return

        blocked_time_slots: list[tuple[int, int, int]] = []
        for slot in self.blocked_slots:
            if len(slot) >= 3:
                day, start_hour, end_hour = slot[0], slot[1], slot[2]
                blocked_time_slots.append((day, start_hour * 60, end_hour * 60))

        if not blocked_time_slots:
            return

        for (course_idx, semester), var in take_vars.items():
            course_section_options = semester_to_section_options.get(semester, {})
            if not course_section_options:
                continue

            course_id = context.courses_df[course_idx, 'subject_id']
            section_types = course_section_options.get(course_id, [])

            if not section_types:
                continue

            if _course_has_unavoidable_conflict(section_types, blocked_time_slots):
                model.Add(var == 0)
                constraints_added += 1

        print(f"[ScheduleFreeTime] Added {constraints_added} constraints in {time.time() - start:.3f}s")

    def get_name(self) -> str:
        return "Schedule Free Time"

    def get_description(self) -> str:
        return "Hard constraint: blocks off time slots where you don't want classes scheduled."

    def get_category(self) -> str:
        return "scheduling"
