"""
Scheduling-related hard constraints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from .base import ConstraintContext


IAP_SEMESTERS: set[int] = {2, 5, 8, 11}


class BanIAPClasses:
    """
    Hard constraint: prevent the optimizer from placing any courses in IAP semesters.

    Courses that the user has explicitly pinned/overridden to IAP are exempt to
    prevent infeasibility. Courses only offered during IAP that have no marker
    are also exempt (banning them would silently make them unschedulable).
    """

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ConstraintContext
    ) -> None:
        import time
        start = time.time()

        from shared.optimizer.marker_constraint_builder import VIRTUAL_MARKER_ATTRS, is_virtual_marker

        # Build set of (course_idx, semester) that the user explicitly placed in IAP
        marked_iap: set[tuple[int, int]] = set()
        course_id_to_idx: dict[str, int] = {}
        for idx in range(len(context.courses_df)):
            course_id_to_idx[context.courses_df[idx, 'subject_id']] = idx

        if context.markers:
            for marker in context.markers:
                semester = marker.section + 1  # 0-indexed -> 1-indexed
                if semester not in IAP_SEMESTERS:
                    continue
                if marker.status not in ("pin", "override"):
                    continue

                if is_virtual_marker(marker.courseId):
                    # Virtual markers (HASS-A, GIR:PHY1, etc.) match by attribute
                    attr = VIRTUAL_MARKER_ATTRS.get(marker.courseId)
                    if attr is not None:
                        col, val = attr
                        if col in context.courses_df.columns:
                            for idx in range(len(context.courses_df)):
                                if context.courses_df[idx, col] == val:
                                    marked_iap.add((idx, semester))
                else:
                    course_idx = course_id_to_idx.get(marker.courseId)
                    if course_idx is not None:
                        marked_iap.add((course_idx, semester))

        # Find courses that are ONLY offered in IAP (no regular semester vars exist)
        iap_only_courses: set[int] = set()
        courses_with_regular: set[int] = set()
        for (course_idx, semester) in take_vars:
            if semester >= 1 and semester not in IAP_SEMESTERS:
                courses_with_regular.add(course_idx)
        for (course_idx, semester) in take_vars:
            if semester in IAP_SEMESTERS and course_idx not in courses_with_regular:
                iap_only_courses.add(course_idx)

        constraints_added = 0
        for (course_idx, semester), var in take_vars.items():
            if semester not in IAP_SEMESTERS:
                continue
            if (course_idx, semester) in marked_iap:
                continue
            if course_idx in iap_only_courses:
                continue
            model.Add(var == 0)
            constraints_added += 1

        print(f"[BanIAPClasses] Banned {constraints_added} IAP placements in {time.time() - start:.3f}s")

    def get_name(self) -> str:
        return "Ban IAP Classes"

    def get_description(self) -> str:
        return "Prevents the optimizer from placing courses in IAP semesters."

    def get_category(self) -> str:
        return "scheduling"


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
