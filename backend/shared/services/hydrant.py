"""
Hydrant schedule data parsing and utilities.
"""

from typing import Any

from pydantic import BaseModel

from shared.services.cache import get_hydrant_semester_data


# Hydrant slot system:
# - 34 slots per day (6am-11pm, 30 min each)
# - Slot 0-33 = Monday, 34-67 = Tuesday, etc.
SLOTS_PER_DAY = 34
SLOT_START_HOUR = 6  # 6am
SLOT_DURATION_HOURS = 0.5  # 30 minutes


class TimeBlock(BaseModel):
    course_id: str
    type: str  # "Lecture", "Recitation", "Lab"
    room: str
    day: int  # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
    start_hour: float  # 24-hour format decimal (e.g., 15.5 for 3:30pm)
    end_hour: float


class ScheduleResponse(BaseModel):
    target_semester: str  # What was requested
    data_semester: str  # What we actually have data from
    blocks: list[TimeBlock]
    missing_courses: list[str]
    has_conflicts: bool


def slot_to_time(slot: int) -> tuple[int, float]:
    """Convert Hydrant slot to (day, hour)."""
    day = slot // SLOTS_PER_DAY
    slot_in_day = slot % SLOTS_PER_DAY
    hour = SLOT_START_HOUR + slot_in_day * SLOT_DURATION_HOURS
    return day, hour


def parse_hydrant_course(course_id: str, course: dict[str, Any]) -> list[TimeBlock]:
    """Parse a Hydrant course into time blocks."""
    blocks: list[TimeBlock] = []

    section_types = [
        ("Lecture", course.get("lectureSections")),
        ("Recitation", course.get("recitationSections")),
        ("Lab", course.get("labSections")),
    ]

    for kind, sections in section_types:
        if not sections:
            continue

        for section in sections:
            # section format: [[[startSlot, numSlots], ...], room]
            timeslots, room = section

            for slot_pair in timeslots:
                start_slot, num_slots = slot_pair
                day, start_hour = slot_to_time(start_slot)
                end_hour = start_hour + num_slots * SLOT_DURATION_HOURS

                blocks.append(TimeBlock(
                    course_id=course_id,
                    type=kind,
                    room=room,
                    day=day,
                    start_hour=start_hour,
                    end_hour=end_hour,
                ))

    return blocks


def detect_conflicts(blocks: list[TimeBlock]) -> bool:
    """
    Check if any required time blocks overlap.
    
    A block is "required" (not optional) if there's only one unique time-of-day
    for that course+type on any given day. Multiple times on the SAME day = options.
    Same time on different days = required (you attend all).
    """
    from collections import defaultdict
    
    # Group blocks by (course_id, type, day) to find options per day
    day_times: dict[tuple[str, str, int], set[tuple[float, float]]] = defaultdict(set)
    for b in blocks:
        key = (b.course_id, b.type, b.day)
        time_key = (b.start_hour, b.end_hour)
        day_times[key].add(time_key)
    
    # A block is "required" if on its day, there's only one unique time for that course+type
    required_blocks: list[TimeBlock] = []
    for b in blocks:
        key = (b.course_id, b.type, b.day)
        if len(day_times[key]) == 1:
            required_blocks.append(b)
    
    # Deduplicate required blocks (same course+type+day+time)
    seen: set[tuple[str, str, int, float, float]] = set()
    deduped_required: list[TimeBlock] = []
    for b in required_blocks:
        key = (b.course_id, b.type, b.day, b.start_hour, b.end_hour)
        if key not in seen:
            seen.add(key)
            deduped_required.append(b)
    
    # Check for overlaps among required blocks only
    for i, a in enumerate(deduped_required):
        for b in deduped_required[i + 1:]:
            if a.day != b.day:
                continue
            if a.start_hour < b.end_hour and b.start_hour < a.end_hour:
                return True
    return False


def resolve_semester(
    target_semester: str,
    current_year: int,
    current_month: int,
) -> tuple[str, str]:
    """
    Resolve which semester to fetch given a target and current date.
    
    Returns (fetch_semester, data_semester) where:
    - fetch_semester: "latest" or an archived semester code to fetch
    - data_semester: the actual semester code the data represents
    
    Logic:
    - Jan-May: latest contains spring of current year
    - Jun-Dec: latest contains fall of current year
    - If target matches latest, use "latest"
    - If target is future of same term type, use latest
    - If target is different term type, use most recent archived of that term
    - If target is past, fetch it directly
    """
    # Calculate what "latest" contains based on current month
    if current_month <= 5:
        latest_semester = f"s{current_year % 100}"
    else:
        latest_semester = f"f{current_year % 100}"
    
    target_year = int(target_semester[1:]) + 2000
    target_term = target_semester[0]
    latest_term = latest_semester[0]
    latest_year = int(latest_semester[1:]) + 2000
    
    if target_semester == latest_semester:
        # Target is current semester
        return "latest", latest_semester
    elif target_term == latest_term and target_year >= latest_year:
        # Future semester of same term type as latest - use latest
        return "latest", latest_semester
    elif target_term != latest_term:
        # Different term type - check if it's past or future
        # Determine the most recent semester of this term type that has already occurred
        if target_term == "f":
            # Fall X occurs Jun-Dec of year X
            # If we're in Jan-May, most recent fall is previous year
            # If we're in Jun-Dec, most recent fall is current year (but that's in latest, not here)
            most_recent_year = current_year - 1
        elif target_term == "i":
            # IAP X occurs in January of year X
            # If we're past January, IAP of current year has occurred
            most_recent_year = current_year if current_month > 1 else current_year - 1
        else:  # spring
            # Spring X occurs Jan-May of year X
            # If we're past May, spring of current year has occurred
            most_recent_year = current_year if current_month > 5 else current_year - 1
        
        if target_year <= most_recent_year:
            # Past semester - fetch directly
            return target_semester, target_semester
        else:
            # Future semester - use most recent as fallback
            most_recent = f"{target_term}{most_recent_year % 100}"
            return most_recent, most_recent
    else:
        # Past semester of same term type - fetch directly
        return target_semester, target_semester


async def get_schedule_blocks(
    target_semester: str,
    course_ids: list[str]
) -> ScheduleResponse:
    """
    Get parsed schedule blocks for courses in a semester.
    
    Tries: 1) target directly, 2) fallback by term type
    """
    from datetime import datetime
    
    now = datetime.now()
    fetch_semester, data_semester = resolve_semester(
        target_semester, now.year, now.month
    )
    
    data = await get_hydrant_semester_data(fetch_semester)
    
    if data is None:
        return ScheduleResponse(
            target_semester=target_semester,
            data_semester="",
            blocks=[],
            missing_courses=course_ids,
            has_conflicts=False,
        )
    
    classes = data.get("classes", {})
    all_blocks: list[TimeBlock] = []
    missing_courses: list[str] = []

    for course_id in course_ids:
        course = classes.get(course_id)
        if course:
            blocks = parse_hydrant_course(course_id, course)
            all_blocks.extend(blocks)
        else:
            missing_courses.append(course_id)

    has_conflicts = detect_conflicts(all_blocks)

    return ScheduleResponse(
        target_semester=target_semester,
        data_semester=data_semester,
        blocks=all_blocks,
        missing_courses=missing_courses,
        has_conflicts=has_conflicts,
    )
