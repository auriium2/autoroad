"""
Workload-based objectives: minimize hours and finals.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from ortools.sat.python import cp_model

from .base import ObjectiveContext


class MinimizeTotalHours:
    """
    Objective to minimize total hours across all semesters.

    Linear objective - continuously prefers fewer total hours.
    Note: This can lead to unbalanced semesters. Consider MinimizeMaxSemesterHours
    for more even distribution.

    Scale: Normalized to ~100 per course (12 hours × 10 = 120).
    """

    def __init__(self, default_hours: float = 12.0):
        """
        Args:
            default_hours: Default weekly hours for courses with missing data
                          (12 hours = 4 hours in class + 8 hours out of class, typical for 12-unit course)
        """
        self.default_hours = default_hours

    def get_name(self) -> str:
        return "Minimize Total Hours"

    def get_description(self) -> str:
        return f"Minimize total weekly hours (default {self.default_hours}h for courses with missing data)"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Minimize sum of total hours for all courses taken.

        Cost = sum((in_class_hours + out_of_class_hours) * take_var)

        For courses with missing hours data, uses default_hours.
        """
        terms = []

        for (course_idx, semester), var in take_vars.items():
            in_class = context.courses_df.at[course_idx, 'in_class_hours'] if 'in_class_hours' in context.courses_df.columns else None
            out_of_class = context.courses_df.at[course_idx, 'out_of_class_hours'] if 'out_of_class_hours' in context.courses_df.columns else None

            total_hours = 0
            has_data = False

            if in_class is not None and pd.notna(in_class):
                total_hours += float(in_class)  # type: ignore[arg-type]
                has_data = True
            if out_of_class is not None and pd.notna(out_of_class):
                total_hours += float(out_of_class)  # type: ignore[arg-type]
                has_data = True

            # If no hours data available, use default
            if not has_data or total_hours == 0:
                total_hours = self.default_hours

            # Scale hours to integers (multiply by 10 to preserve 1 decimal place)
            scaled_hours = int(total_hours * 10)
            terms.append(var * scaled_hours)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class LimitClassesPerSemester:
    """
    Soft constraint to limit the number of classes per semester.

    Penalizes semesters that exceed max_classes threshold. This prevents
    taking too many classes in one semester even if the units and hours are manageable.

    Scale: Soft constraint with high penalty (1000 per excess class by default).
           Designed to dominate when violated, but negligible when satisfied.
    """

    def __init__(self, max_classes: int = 4, penalty: int = 1000):
        """
        Args:
            max_classes: Maximum comfortable number of classes per semester
            penalty: Penalty cost for each class beyond max_classes (default 1000)
        """
        self.max_classes = max_classes
        self.penalty = penalty

    def get_name(self) -> str:
        return "Limit Classes Per Semester"

    def get_description(self) -> str:
        return f"Penalize semesters with more than {self.max_classes} classes"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add penalty for semesters exceeding max_classes.

        For each semester:
        1. Count total classes: sum(take_var)
        2. Create excess_var = max(0, class_count - max_classes)
        3. Add excess_var * penalty to objective
        """
        terms = []

        # Group take_vars by semester (only regular semesters 1-12)
        semesters = set(semester for _, semester in take_vars.keys() if semester >= 1)

        for sem in semesters:
            # Count classes in this semester
            classes_in_semester = []
            for (course_idx, semester), var in take_vars.items():
                if semester == sem:
                    classes_in_semester.append(var)

            if not classes_in_semester:
                continue

            # Create a variable for number of classes in this semester
            class_count_var = model.NewIntVar(0, len(classes_in_semester), f'classes_sem_{sem}')
            model.Add(class_count_var == sum(classes_in_semester))

            # Create a variable for excess classes (above threshold)
            excess_var = model.NewIntVar(0, len(classes_in_semester), f'excess_classes_sem_{sem}')
            model.AddMaxEquality(excess_var, [class_count_var - self.max_classes, 0])

            # Add penalty term
            terms.append(excess_var * self.penalty)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class MinimizeMaxSemesterHours:
    """
    Soft constraint to limit hours per semester.

    Penalizes semesters that exceed max_hours threshold. This prevents
    one brutal semester even if total hours is reasonable.

    Scale: Soft constraint with high penalty (100 per excess hour by default).
           Designed to dominate when violated, but negligible when satisfied.
    """

    def __init__(self, max_hours: float = 60.0, penalty: int = 100, default_hours: float = 12.0):
        """
        Args:
            max_hours: Maximum acceptable weekly hours per semester
            penalty: Penalty per hour over the limit
            default_hours: Default weekly hours for courses with missing data
        """
        self.max_hours = max_hours
        self.penalty = penalty
        self.default_hours = default_hours

    def get_name(self) -> str:
        return "Limit Semester Hours"

    def get_description(self) -> str:
        return f"Penalize semesters with more than {self.max_hours} hours/week (default {self.default_hours}h for courses with missing data)"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add penalty for semesters exceeding max_hours.

        For each semester:
        1. Calculate total hours: sum((in_class + out_of_class) * take_var)
        2. Create excess_var = max(0, total_hours - max_hours)
        3. Add excess_var * penalty to objective
        """
        terms = []

        # Group take_vars by semester
        semesters = set(semester for _, semester in take_vars.keys())

        for sem in semesters:
            # Calculate total hours for this semester
            hours_in_semester = []
            for (course_idx, semester), var in take_vars.items():
                if semester == sem:
                    in_class = context.courses_df.at[course_idx, 'in_class_hours'] if 'in_class_hours' in context.courses_df.columns else None
                    out_of_class = context.courses_df.at[course_idx, 'out_of_class_hours'] if 'out_of_class_hours' in context.courses_df.columns else None

                    total_hours = 0
                    has_data = False

                    if in_class is not None and pd.notna(in_class):
                        total_hours += float(in_class)  # type: ignore[arg-type]
                        has_data = True
                    if out_of_class is not None and pd.notna(out_of_class):
                        total_hours += float(out_of_class)  # type: ignore[arg-type]
                        has_data = True

                    # If no hours data available, use default
                    if not has_data or total_hours == 0:
                        total_hours = self.default_hours

                    # Scale by 10 to preserve 1 decimal place
                    scaled_hours = int(total_hours * 10)
                    hours_in_semester.append(var * scaled_hours)

            if not hours_in_semester:
                continue

            # Create variable for total hours in this semester
            # Calculate max possible hours (handle NaN values)
            max_possible = 0
            if 'in_class_hours' in context.courses_df.columns:
                for c in context.courses_df.index:
                    in_h = context.courses_df.at[c, 'in_class_hours']
                    out_h = context.courses_df.at[c, 'out_of_class_hours'] if 'out_of_class_hours' in context.courses_df.columns else 0
                    total = 0
                    if pd.notna(in_h):
                        total += float(in_h)
                    if pd.notna(out_h):
                        total += float(out_h)
                    max_possible += int(total * 10)
            max_possible_hours = max(max_possible, 1000)

            total_hours_var = model.NewIntVar(0, max_possible_hours, f'total_hours_sem_{sem}')
            model.Add(total_hours_var == sum(hours_in_semester))

            # Create variable for excess hours (above threshold)
            # max_hours is in actual hours, but we scaled by 10
            scaled_max_hours = int(self.max_hours * 10)
            excess_var = model.NewIntVar(0, max_possible_hours, f'excess_hours_sem_{sem}')
            model.AddMaxEquality(excess_var, [total_hours_var - scaled_max_hours, 0])

            # Add penalty term
            terms.append(excess_var * self.penalty)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class MinimizeFinalsLoad:
    """
    Objective to minimize the maximum number of finals in any semester.

    This is a soft constraint: we add penalty variables for semesters
    exceeding a threshold number of finals.

    Scale: Soft constraint with high penalty (1000 per excess final by default).
           Designed to dominate when violated, but negligible when satisfied.
    """

    def __init__(self, max_finals: int = 4, penalty: int = 1000):
        """
        Args:
            max_finals: Maximum comfortable number of finals per semester
            penalty: Penalty cost for each final beyond max_finals (default 1000)
        """
        self.max_finals = max_finals
        self.penalty = penalty

    def get_name(self) -> str:
        return "Minimize Finals Load"

    def get_description(self) -> str:
        return f"Penalize semesters with more than {self.max_finals} finals"

    def preprocess(self, courses_df: pd.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add penalty for semesters exceeding max_finals.

        For each semester:
        1. Count total finals: sum(has_final * take_var)
        2. Create excess_var = max(0, finals_count - max_finals)
        3. Add excess_var * penalty to objective
        """
        terms = []

        # Group take_vars by semester
        semesters = set(semester for _, semester in take_vars.keys())

        for sem in semesters:
            # Count finals in this semester
            finals_in_semester = []
            for (course_idx, semester), var in take_vars.items():
                if semester == sem:
                    has_final = context.courses_df.at[course_idx, 'has_final'] if 'has_final' in context.courses_df.columns else False
                    if has_final:
                        finals_in_semester.append(var)

            if not finals_in_semester:
                continue

            # Create a variable for number of finals in this semester
            finals_count_var = model.NewIntVar(0, len(finals_in_semester), f'finals_sem_{sem}')
            model.Add(finals_count_var == sum(finals_in_semester))

            # Create a variable for excess finals (above threshold)
            excess_var = model.NewIntVar(0, len(finals_in_semester), f'excess_finals_sem_{sem}')
            model.AddMaxEquality(excess_var, [finals_count_var - self.max_finals, 0])

            # Add penalty term
            terms.append(excess_var * self.penalty)

        if terms:
            return sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])
