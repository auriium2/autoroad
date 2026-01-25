"""
Schedule conflict hard constraint using Hydrant data.

Prevents taking courses with overlapping required time slots in the same semester.
Only applies to the current/latest semester where schedule data is accurate.

A time slot is "required" if there's no alternative - i.e., only one unique time
for that course+type on a given day. Multiple times on the same day = options (pick one).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from .base import ConstraintContext


# Hydrant slot system constants
SLOTS_PER_DAY = 34
SLOT_START_HOUR = 6
SLOT_DURATION_MINUTES = 30


def slot_to_day_and_time(slot: int) -> tuple[int, int, int]:
    """
    Convert Hydrant slot to (day, start_minutes, end_minutes).
    
    Args:
        slot: Hydrant slot number (0-based)
        
    Returns:
        (day, start_minutes, end_minutes) where day is 0-4 (Mon-Fri)
    """
    day = slot // SLOTS_PER_DAY
    slot_in_day = slot % SLOTS_PER_DAY
    start_minutes = (SLOT_START_HOUR * 60) + (slot_in_day * SLOT_DURATION_MINUTES)
    end_minutes = start_minutes + SLOT_DURATION_MINUTES
    return day, start_minutes, end_minutes


def get_required_slots_from_course(
    course_data: dict[str, Any]
) -> list[tuple[int, int, int]]:
    """
    Extract required (non-optional) time slots from Hydrant course data.
    
    A section type is required if there's only ONE section of that type.
    Multiple sections of the same type = options (student picks one section).
    Within a required section, ALL time slots must be attended.
    
    Args:
        course_data: Hydrant course object
        
    Returns:
        List of (day, start_minutes, end_minutes) for required slots only
    """
    required_slots: list[tuple[int, int, int]] = []
    
    section_types = [
        ("Lecture", "lectureSections"),
        ("Recitation", "recitationSections"),
        ("Lab", "labSections"),
        ("Design", "designSections"),
    ]
    
    for _, key in section_types:
        sections = course_data.get(key, [])
        
        # If there's exactly ONE section of this type, all its slots are required
        # If there are multiple sections, student picks one (optional)
        if len(sections) == 1:
            section = sections[0]
            # section format: [[[startSlot, numSlots], ...], room]
            if section and len(section) >= 2:
                timeslots = section[0]
                for slot_pair in timeslots:
                    if len(slot_pair) >= 2:
                        start_slot, num_slots = slot_pair[0], slot_pair[1]
                        day, start_minutes, _ = slot_to_day_and_time(start_slot)
                        end_minutes = start_minutes + (num_slots * SLOT_DURATION_MINUTES)
                        required_slots.append((day, start_minutes, end_minutes))
    
    return required_slots


def slots_overlap(slot1: tuple[int, int, int], slot2: tuple[int, int, int]) -> bool:
    """Check if two time slots overlap (same day and overlapping time)."""
    day1, start1, end1 = slot1
    day2, start2, end2 = slot2
    
    if day1 != day2:
        return False
    
    return start1 < end2 and start2 < end1


class NoScheduleConflicts:
    """
    Hard constraint: Prevent courses with overlapping required time slots.
    
    This uses Hydrant schedule data for accurate time slot detection.
    
    When extrapolate=True (default), applies to all semesters using the best available
    schedule data for each (extrapolates current semester data to future semesters
    of the same term type).
    
    When extrapolate=False, only applies to semesters that have real schedule data
    available (typically just the current/upcoming semester).
    
    A time slot is "required" if there's no alternative on that day for that section type.
    Multiple times on the same day = options (student picks one), so no conflict.
    
    Requires 'hydrant_schedule_data' in context.extra with format:
    {
        'semester_to_slots': dict[int, dict[str, list[tuple[int, int, int]]]]
            # semester_idx -> (course_id -> required slots)
    }
    """

    def __init__(self, extrapolate: bool = False):
        self.extrapolate: bool = extrapolate
    
    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ConstraintContext
    ) -> None:
        """Add schedule conflict constraints to model."""
        if context.extra is None:
            return
        
        hydrant_data = context.extra.get('hydrant_schedule_data')
        if not hydrant_data:
            return
        
        semester_to_slots: dict[int, dict[str, list[tuple[int, int, int]]]] = hydrant_data.get('semester_to_slots', {})
        
        if not semester_to_slots:
            return
        
        # Build course_id -> course_idx mapping
        course_id_to_idx: dict[str, int] = {}
        for idx in range(len(context.courses_df)):
            subject_id = context.courses_df[idx, 'subject_id']
            course_id_to_idx[subject_id] = idx
        
        # Group take_vars by semester
        courses_by_semester: dict[int, list[tuple[int, cp_model.IntVar]]] = {}
        for (course_idx, semester), var in take_vars.items():
            if semester not in courses_by_semester:
                courses_by_semester[semester] = []
            courses_by_semester[semester].append((course_idx, var))
        
        # For each semester, add constraints for conflicting course pairs
        conflicts_added: set[tuple[int, int, int]] = set()
        
        for semester, courses in courses_by_semester.items():
            # Get the schedule data for this semester
            course_id_to_slots = semester_to_slots.get(semester, {})
            if not course_id_to_slots:
                continue
            
            # Build course_idx -> slots mapping for this semester
            course_idx_to_slots: dict[int, list[tuple[int, int, int]]] = {}
            for course_id, slots in course_id_to_slots.items():
                if course_id in course_id_to_idx:
                    course_idx_to_slots[course_id_to_idx[course_id]] = slots
            
            for i, (course_idx1, var1) in enumerate(courses):
                slots1 = course_idx_to_slots.get(course_idx1, [])
                if not slots1:
                    continue
                
                for course_idx2, var2 in courses[i + 1:]:
                    # Avoid duplicate constraints
                    conflict_key = (semester, min(course_idx1, course_idx2), max(course_idx1, course_idx2))
                    if conflict_key in conflicts_added:
                        continue
                    
                    slots2 = course_idx_to_slots.get(course_idx2, [])
                    if not slots2:
                        continue
                    
                    # Check if any required slots overlap
                    has_conflict = any(
                        slots_overlap(s1, s2)
                        for s1 in slots1
                        for s2 in slots2
                    )
                    
                    if has_conflict:
                        # Hard constraint: cannot take both courses
                        # var1 + var2 <= 1
                        model.Add(var1 + var2 <= 1)
                        conflicts_added.add(conflict_key)
    
    def get_name(self) -> str:
        return "No Schedule Conflicts"
    
    def get_description(self) -> str:
        return "Hard constraint: prevents taking courses with overlapping required time slots."
    
    def get_category(self) -> str:
        return "scheduling"


async def fetch_hydrant_schedule_data(
    course_ids: list[str],
    semester_code: str,
) -> dict[str, list[tuple[int, int, int]]]:
    """
    Fetch Hydrant schedule data for courses and return only required slots.
    
    A section type is required if there's only ONE section of that type.
    Multiple sections = options (student picks one).
    
    Args:
        course_ids: List of course IDs to fetch
        semester_code: Hydrant semester code (e.g., "s26", "f25", "latest")
        
    Returns:
        Dict mapping course_id -> list of required slots (day, start_minutes, end_minutes)
    """
    from shared.services.cache import get_hydrant_semester_data
    
    try:
        data = await get_hydrant_semester_data(semester_code)
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
    """
    Fetch Hydrant schedule data for all semesters, using fallback logic.
    
    Args:
        take_vars: Course take decision variables
        courses_df: Polars DataFrame with course data
        planning_year_start: Start year of planning (e.g., 2025 for class of 2029)
        max_semesters: Maximum number of semesters
        extrapolate: If True, use fallback data for future semesters. If False, only
                     use semesters with real data available.
    
    Returns:
        Dict mapping semester_idx -> (course_id -> required slots)
    """
    from datetime import datetime
    from shared.services.hydrant import resolve_semester
    from shared.utils import semester_idx_to_hydrant_code
    
    now = datetime.now()
    
    # Group semesters by their data source to avoid redundant fetches
    data_source_to_semesters: dict[str, list[int]] = {}
    
    for semester_idx in range(1, max_semesters + 1):
        # Check if any courses have variables for this semester
        has_courses = any(sem == semester_idx for (_, sem) in take_vars.keys())
        if not has_courses:
            continue
        
        target_code = semester_idx_to_hydrant_code(semester_idx, planning_year_start)
        _, data_semester = resolve_semester(target_code, now.year, now.month)
        
        # When not extrapolating, skip semesters that would use fallback data
        if not extrapolate and data_semester != target_code:
            continue
        
        if data_semester not in data_source_to_semesters:
            data_source_to_semesters[data_semester] = []
        data_source_to_semesters[data_semester].append(semester_idx)
    
    # Fetch data for each unique data source
    result: dict[int, dict[str, list[tuple[int, int, int]]]] = {}
    
    for data_semester, semester_indices in data_source_to_semesters.items():
        # Get all course IDs that have variables in any of these semesters
        course_ids_for_source: set[str] = set()
        for semester_idx in semester_indices:
            for (course_idx, sem) in take_vars.keys():
                if sem == semester_idx:
                    course_ids_for_source.add(courses_df[course_idx, "subject_id"])
        
        # Fetch the schedule data once for this data source
        slots_data = await fetch_hydrant_schedule_data(list(course_ids_for_source), data_semester)
        
        # Apply to all semesters that use this data source
        for semester_idx in semester_indices:
            result[semester_idx] = slots_data
    
    return result
