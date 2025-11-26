"""
Utility functions for objective components.
"""

from __future__ import annotations

import polars as pl


def parse_schedule_has_friday(schedule: str | None) -> bool:
    """
    Check if a course schedule includes Friday classes.

    Args:
        schedule: Schedule string from Fireroad API

    Returns:
        True if the course has classes on Friday
    """
    if schedule is None or not schedule:
        return False

    # Schedule format: "Lecture,4-237/MWF/0/1;Recitation,34-101/TR/0/1"
    # Each section separated by semicolon, meetings separated by comma
    # Days are in format like "MWF", "TR", etc.

    sections = schedule.split(';')
    for section in sections:
        meetings = section.split(',')[1:]  # Skip first entry (section type)
        for meeting in meetings:
            if meeting == 'TBA':
                continue
            parts = meeting.split('/')
            if len(parts) >= 2:
                days = parts[1]  # e.g., "MWF", "TR"
                if 'F' in days:
                    return True

    return False


def parse_time_to_minutes(time_str: str, is_evening: str) -> int | None:
    """
    Convert time string to minutes since midnight.

    Args:
        time_str: Time string like "9", "1-2.30", "5.30 PM"
        is_evening: "0" for daytime, "1" for evening

    Returns:
        Minutes since midnight, or None if unparseable
    """
    if not time_str:
        return None

    try:
        # Handle ranges like "1-2.30" - use start time
        if '-' in time_str:
            time_str = time_str.split('-')[0].strip()

        # Handle evening times like "5.30 PM"
        if 'PM' in time_str or 'AM' in time_str:
            time_str = time_str.replace('PM', '').replace('AM', '').strip()
            is_pm = 'PM' in time_str
        else:
            is_pm = is_evening == "1"

        # Parse hours and minutes
        if '.' in time_str:
            hour, minute = time_str.split('.')
            hour = int(hour)
            minute = int(minute)
        else:
            hour = int(time_str)
            minute = 0

        # Convert to 24-hour format
        if is_pm and hour < 12:
            hour += 12

        return hour * 60 + minute
    except (ValueError, IndexError):
        return None


def parse_schedule_time_slots(schedule: str | None) -> list[tuple[str, int]]:
    """
    Parse schedule into list of (days, start_time_minutes) tuples for clustering analysis.

    Args:
        schedule: Schedule string from Fireroad API

    Returns:
        List of (days, start_time_minutes) tuples, e.g., [("MWF", 540), ("TR", 810)]
        where 540 = 9:00 AM, 810 = 1:30 PM
    """
    if schedule is None or not schedule:
        return []

    time_slots = []
    sections = schedule.split(';')

    for section in sections:
        meetings = section.split(',')[1:]  # Skip first entry (section type)
        for meeting in meetings:
            if meeting == 'TBA':
                continue
            parts = meeting.split('/')
            if len(parts) >= 4:
                # parts[0] = room, parts[1] = days, parts[2] = is_evening, parts[3] = time
                days = parts[1]
                is_evening = parts[2]
                time_str = parts[3]

                minutes = parse_time_to_minutes(time_str, is_evening)
                if minutes is not None:
                    time_slots.append((days, minutes))

    return time_slots


def preprocess_schedule_data(courses_df: pl.DataFrame) -> dict[str, object]:
    """
    Preprocess all schedule data for efficient lookup during optimization.

    Args:
        courses_df: DataFrame with course data including 'schedule' column

    Returns:
        Dictionary with preprocessed data:
        - 'has_friday': dict mapping course_idx -> bool
        - 'time_slots': dict mapping course_idx -> list of (days, time) tuples
    """
    has_friday = {}
    time_slots = {}

    for idx in range(len(courses_df)):
        schedule = courses_df[idx, 'schedule'] if 'schedule' in courses_df.columns else None
        has_friday[idx] = parse_schedule_has_friday(schedule)
        time_slots[idx] = parse_schedule_time_slots(schedule)

    return {
        'has_friday': has_friday,
        'time_slots': time_slots,
    }


def compute_bayesian_rating(rating: float, enrollment: float, min_votes: int = 10, global_mean: float = 5.0) -> float:
    """
    Compute Bayesian/IMDB-style weighted rating.

    This reduces bias from courses with very few reviews by blending
    the course rating with the global mean, weighted by number of reviews.

    Formula: weighted_rating = (v / (v + m)) * R + (m / (v + m)) * C
    where:
        v = number of reviews (enrollment)
        m = minimum votes threshold
        R = course rating
        C = global mean rating

    Args:
        rating: Course rating (0-7)
        enrollment: Number of students (proxy for number of reviews)
        min_votes: Minimum number of votes to trust the rating
        global_mean: Global average rating across all courses

    Returns:
        Weighted rating
    """
    if rating is None or enrollment is None:
        return global_mean

    v = enrollment
    m = min_votes
    R = rating
    C = global_mean

    weighted_rating = (v / (v + m)) * R + (m / (v + m)) * C
    return weighted_rating
