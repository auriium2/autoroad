"""
Schedule-based objectives: frontload, backload, minimize Fridays, clustering.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from ortools.sat.python import cp_model

from .base import ObjectiveContext
from .utils import preprocess_schedule_data


class FrontloadCourses:
    """
    Objective to frontload courses (prefer earlier semesters).

    This encourages taking courses earlier in the academic career,
    which can be useful for unlocking prerequisites or graduating early.

    Scale: Normalized to ~100 per course (semester 6 × 20 = 120).
    """

    def get_name(self) -> str:
        return "Frontload Courses"

    def get_description(self) -> str:
        return "Prefer taking courses in earlier semesters"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Minimize sum of (semester_number * 20 * take_var).

        Later semesters have higher numbers, so this penalizes taking courses late.
        Scaled by 20 to normalize to ~100 per course.
        """
        terms = []

        for (course_idx, semester), var in take_vars.items():
            # Semester 1 costs 20, semester 2 costs 40, etc.
            # Average semester ~6 → 120
            terms.append(var * semester * 20)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class BackloadCourses:
    """
    Objective to backload courses (prefer later semesters).

    This encourages taking courses later in the academic career,
    which can be useful for maintaining enrollment status or
    spreading out difficult courses.

    Scale: Normalized to ~100 per course (semester 6 → (13-6) × 20 = 140).
    """

    def get_name(self) -> str:
        return "Backload Courses"

    def get_description(self) -> str:
        return "Prefer taking courses in later semesters"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Minimize sum of ((13 - semester_number) * 20 * take_var).

        Earlier semesters have higher costs, so this penalizes taking courses early.
        Assumes 12 semesters max. Scaled by 20 to normalize to ~100 per course.
        """
        terms = []

        for (course_idx, semester), var in take_vars.items():
            # Semester 1 costs 240, semester 2 costs 220, ..., semester 12 costs 20
            # Average semester ~6 → (13-6) × 20 = 140
            terms.append(var * (13 - semester) * 20)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class MinimizeFridayClasses:
    """
    Objective to minimize classes that meet on Friday.

    This maximizes long weekends for students who want to minimize Friday schedules.

    Scale: Normalized to ~100 per Friday course (penalty=100).
    """

    def __init__(self, penalty: int = 100):
        """
        Args:
            penalty: Cost penalty for each course that meets on Friday (default 100)
        """
        self.penalty = penalty

    def get_name(self) -> str:
        return "Minimize Friday Classes"

    def get_description(self) -> str:
        return "Avoid courses that meet on Fridays"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        """Preprocess schedule data to identify Friday classes."""
        return preprocess_schedule_data(courses_df)

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add penalty for each course taken that meets on Friday.

        Cost = sum(penalty * take_var) for courses with Friday classes
        """
        if context.extra is None or 'has_friday' not in context.extra:
            return cp_model.LinearExpr.Sum([])

        has_friday = context.extra['has_friday']
        terms = []

        for (course_idx, semester), var in take_vars.items():
            if has_friday.get(course_idx, False):
                terms.append(var * self.penalty)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class ClusterCourses:
    """
    Objective to cluster courses together in the day (minimize time gaps).

    This encourages schedules where classes are back-to-back rather than
    spread throughout the day with long gaps.

    Uses actual time slot parsing to calculate gaps in minutes.

    Scale: Normalized to ~100 per course assuming ~1 hour average gap × 50 penalty = 50.
    """

    def __init__(self, gap_penalty_per_hour: int = 50):
        """
        Args:
            gap_penalty_per_hour: Penalty for each hour of gap between classes
                                 (default 50, so 2-hour gap costs 100)
        """
        self.gap_penalty_per_hour = gap_penalty_per_hour

    def get_name(self) -> str:
        return "Cluster Courses"

    def get_description(self) -> str:
        return f"Minimize time gaps between classes (penalty: {self.gap_penalty_per_hour} per hour)"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        """Preprocess schedule data to extract time slots."""
        return preprocess_schedule_data(courses_df)

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add penalty for time gaps between classes.

        For each semester and each day:
        1. Identify which courses are taken on that day
        2. For each pair of courses, calculate the time gap
        3. Penalize the gap proportionally

        Note: This is an approximation since we can't know exact end times.
        We use start time differences as a proxy.
        """
        if context.extra is None or 'time_slots' not in context.extra:
            return cp_model.LinearExpr.Sum([])

        time_slots_map = context.extra['time_slots']
        terms = []

        # Group by semester
        semesters = set(semester for _, semester in take_vars.keys())

        for sem in semesters:
            # For each day, collect courses with their time slots
            day_courses: dict[str, list[tuple[int, int, cp_model.IntVar]]] = {
                'M': [], 'T': [], 'W': [], 'R': [], 'F': []
            }

            for (course_idx, semester), var in take_vars.items():
                if semester != sem:
                    continue

                slots = time_slots_map.get(course_idx, [])
                for days, start_time_minutes in slots:
                    # Days is like "MWF" or "TR"
                    for day_char in days:
                        if day_char in day_courses:
                            day_courses[day_char].append((course_idx, start_time_minutes, var))

            # For each day, calculate gaps between consecutive classes
            for day, courses_on_day in day_courses.items():
                if len(courses_on_day) < 2:
                    continue

                # Sort by time
                courses_on_day.sort(key=lambda x: x[1])

                # For each consecutive pair, add gap penalty if both are taken
                for i in range(len(courses_on_day) - 1):
                    course1_idx, time1, var1 = courses_on_day[i]
                    course2_idx, time2, var2 = courses_on_day[i + 1]

                    # Calculate gap in minutes
                    # Assume 1-hour class duration, so gap = (time2 - time1 - 60)
                    gap_minutes = max(0, time2 - time1 - 60)
                    gap_hours = gap_minutes / 60.0

                    if gap_hours > 0:
                        # Penalty applies only if BOTH courses are taken
                        # Create a variable for "both taken"
                        both_taken = model.NewBoolVar(f'both_taken_{sem}_{day}_{i}')
                        model.AddMultiplicationEquality(both_taken, [var1, var2])

                        # Add gap penalty (scaled to integer)
                        penalty = int(gap_hours * self.gap_penalty_per_hour)
                        terms.append(both_taken * penalty)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])
