"""
Schedule conflict constraint using Hydrant data.

Prevents taking courses with overlapping required time slots in the same semester.

A time slot is "required" if there's no alternative - i.e., only one section of that
type exists. Multiple sections = student picks one (optional).
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from .base import ConstraintContext


SLOTS_PER_DAY = 34
SLOT_START_HOUR = 6
SLOT_DURATION_MINUTES = 30


def slot_to_day_and_time(slot: int) -> tuple[int, int, int]:
    """Convert Hydrant slot to (day, start_minutes, end_minutes)."""
    day = slot // SLOTS_PER_DAY
    slot_in_day = slot % SLOTS_PER_DAY
    start_minutes = (SLOT_START_HOUR * 60) + (slot_in_day * SLOT_DURATION_MINUTES)
    end_minutes = start_minutes + SLOT_DURATION_MINUTES
    return day, start_minutes, end_minutes


def get_required_slots_from_course(course_data: dict[str, Any]) -> list[tuple[int, int, int]]:
    """
    Extract required time slots from Hydrant course data.
    A section type is required if there's only ONE section of that type.
    """
    required_slots: list[tuple[int, int, int]] = []

    section_keys = ["lectureSections", "recitationSections", "labSections", "designSections"]

    for key in section_keys:
        sections = course_data.get(key, [])
        if len(sections) == 1:
            section = sections[0]
            if section and len(section) >= 2:
                timeslots = section[0]
                for slot_pair in timeslots:
                    if len(slot_pair) >= 2:
                        start_slot, num_slots = slot_pair[0], slot_pair[1]
                        day, start_minutes, _ = slot_to_day_and_time(start_slot)
                        end_minutes = start_minutes + (num_slots * SLOT_DURATION_MINUTES)
                        required_slots.append((day, start_minutes, end_minutes))

    return required_slots


def find_conflicting_pairs(
    course_idx_to_slots: dict[int, list[tuple[int, int, int]]]
) -> set[tuple[int, int]]:
    """Find all pairs of courses with overlapping time slots using sweep line algorithm."""
    conflicting_pairs: set[tuple[int, int]] = set()

    # Group events by day
    events_by_day: dict[int, list[tuple[int, bool, int]]] = defaultdict(list)
    for course_idx, slots in course_idx_to_slots.items():
        for day, start_min, end_min in slots:
            events_by_day[day].append((start_min, True, course_idx))
            events_by_day[day].append((end_min, False, course_idx))

    # Sweep line per day
    for events in events_by_day.values():
        events.sort(key=lambda e: (e[0], e[1]))  # Sort by time, ends before starts
        active: set[int] = set()
        for _, is_start, course_idx in events:
            if is_start:
                for other_idx in active:
                    pair = (min(course_idx, other_idx), max(course_idx, other_idx))
                    conflicting_pairs.add(pair)
                active.add(course_idx)
            else:
                active.discard(course_idx)

    return conflicting_pairs


class NoScheduleConflicts:
    """
    Hard constraint: Prevent courses with overlapping required time slots.
    
    When extrapolate=True, applies to all semesters using best available schedule data.
    When extrapolate=False, only applies to semesters with real data available.
    
    Requires 'hydrant_schedule_data' in context.extra.
    """

    def __init__(self, extrapolate: bool = False):
        self.extrapolate: bool = extrapolate

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ConstraintContext
    ) -> None:
        start = time.time()

        if context.extra is None:
            return

        hydrant_data = context.extra.get('hydrant_schedule_data')
        if not hydrant_data:
            return

        semester_to_slots: dict[int, dict[str, list[tuple[int, int, int]]]] = hydrant_data.get('semester_to_slots', {})
        if not semester_to_slots:
            return

        # Group take_vars by semester
        courses_by_semester: dict[int, dict[int, cp_model.IntVar]] = defaultdict(dict)
        for (course_idx, semester), var in take_vars.items():
            courses_by_semester[semester][course_idx] = var

        total_intervals = 0
        total_nooverlap = 0

        for semester, course_vars in courses_by_semester.items():
            course_id_to_slots = semester_to_slots.get(semester)
            if not course_id_to_slots:
                continue

            # Group intervals by day for this semester
            # day -> list of interval variables
            day_intervals: dict[int, list[cp_model.IntervalVar]] = defaultdict(list)

            for course_idx, take_var in course_vars.items():
                subject_id = context.courses_df[course_idx, 'subject_id']
                slots = course_id_to_slots.get(subject_id)
                if not slots:
                    continue

                # Create an optional interval for each time block
                for i, (day, start_min, end_min) in enumerate(slots):
                    interval = model.NewOptionalFixedSizeIntervalVar(
                        start=start_min,
                        size=end_min - start_min,
                        is_present=take_var,
                        name=f"sched_s{semester}_c{course_idx}_{i}"
                    )
                    day_intervals[day].append(interval)
                    total_intervals += 1

            # Add NoOverlap constraint for each day
            for day, intervals in day_intervals.items():
                if len(intervals) >= 2:
                    model.AddNoOverlap(intervals)
                    total_nooverlap += 1

        print(f"[NoScheduleConflicts] Added {total_intervals} intervals, {total_nooverlap} NoOverlap constraints in {time.time() - start:.2f}s")

    def get_name(self) -> str:
        return "No Schedule Conflicts"

    def get_description(self) -> str:
        return "Prevents taking courses with overlapping required time slots."

    def get_category(self) -> str:
        return "scheduling"


async def fetch_hydrant_schedule_data(
    course_ids: list[str],
    fetch_semester: str,
) -> dict[str, list[tuple[int, int, int]]]:
    """Fetch Hydrant schedule data and return only required slots."""
    from shared.services.cache import get_hydrant_semester_data

    try:
        data = await get_hydrant_semester_data(fetch_semester)
    except ValueError:
        return {}

    if data is None:
        return {}

    classes = data.get("classes", {})
    result: dict[str, list[tuple[int, int, int]]] = {}

    for course_id in course_ids:
        course_data = classes.get(course_id)
        if course_data:
            required_slots = get_required_slots_from_course(course_data)
            if required_slots:
                result[course_id] = required_slots

    return result


async def fetch_hydrant_data_for_semesters(
    take_vars: dict[tuple[int, int], Any],
    courses_df: Any,
    planning_year_start: int,
    max_semesters: int,
    extrapolate: bool = False,
) -> dict[int, dict[str, list[tuple[int, int, int]]]]:
    """Fetch Hydrant schedule data for all relevant semesters."""
    from datetime import datetime

    from shared.services.hydrant import resolve_semester
    from shared.utils import semester_idx_to_hydrant_code

    now = datetime.now()

    # Pre-compute course_ids by semester
    semester_to_course_ids: dict[int, set[str]] = defaultdict(set)
    for (course_idx, semester) in take_vars.keys():
        if 1 <= semester <= max_semesters:
            semester_to_course_ids[semester].add(courses_df[course_idx, "subject_id"])

    # Group semesters by fetch source
    fetch_source_to_semesters: dict[tuple[str, str], list[int]] = {}

    for semester_idx in range(1, max_semesters + 1):
        if semester_idx not in semester_to_course_ids:
            continue

        target_code = semester_idx_to_hydrant_code(semester_idx, planning_year_start)
        fetch_semester, data_semester = resolve_semester(target_code, now.year, now.month)

        if not extrapolate and data_semester != target_code:
            continue

        key = (fetch_semester, data_semester)
        if key not in fetch_source_to_semesters:
            fetch_source_to_semesters[key] = []
        fetch_source_to_semesters[key].append(semester_idx)

    # Fetch data for each unique source
    result: dict[int, dict[str, list[tuple[int, int, int]]]] = {}

    for (fetch_semester, _), semester_indices in fetch_source_to_semesters.items():
        course_ids: set[str] = set()
        for semester_idx in semester_indices:
            course_ids.update(semester_to_course_ids[semester_idx])

        slots_data = await fetch_hydrant_schedule_data(list(course_ids), fetch_semester)

        for semester_idx in semester_indices:
            result[semester_idx] = slots_data

    return result
