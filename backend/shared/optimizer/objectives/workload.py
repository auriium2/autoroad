"""
Workload-based objectives: minimize hours and finals.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext, get_tier_penalty


class LimitClassesPerSemester:
    """
    Tier-based soft constraint to limit the number of classes per semester.

    Penalizes semesters that exceed max_classes threshold using tier-based penalties.

    Tier meanings:
        Tier 1 (3 units/violation): "Ideal preferences"
        Tier 2 (9 units/violation): "Important preferences"
        Tier 3 (27 units/violation): "Rarely violate"
        Tier 4 (81 units/violation): "Never violate"
    """

    def __init__(self, max_classes: int = 4):
        """
        Args:
            max_classes: Maximum comfortable number of classes per semester
        """
        self.max_classes: int = max_classes

    def get_name(self) -> str:
        return "Limit Classes Per Semester"

    def get_description(self) -> str:
        return f"Penalize semesters with more than {self.max_classes} classes (tier-based)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {
            '_subject_ids': courses_df['subject_id'].to_list()
        }


    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:

        """
        Add tier-based penalty for semesters exceeding max_classes.

        Formula: penalty = violations × TIER_BASE^tier × 1
        """
        # Get tier for this objective (default tier 2 if not set)
        tier = 2
        if context.objective_tiers and 'limit_classes_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_classes_per_semester']
        marked_course_ids = context.marked_course_ids or set()
        subject_ids = (context.extra.get('_subject_ids') if context.extra else None) or context.courses_df['subject_id'].to_list()

        penalty = get_tier_penalty(tier, base_cost=1)

        terms = []

        semesters = set(semester for _, semester in take_vars.keys() if semester >= 1)

        for sem in semesters:
            # Count classes in this semester
            classes_in_semester = []
            for (course_idx, semester), var in take_vars.items():
                course_id = subject_ids[course_idx]

                if semester == sem:
                    classes_in_semester.append(var)

            if not classes_in_semester:
                continue

            class_count_var = model.NewIntVar(0, len(classes_in_semester), f'classes_sem_{sem}')
            _ = model.Add(class_count_var == sum(classes_in_semester))

            excess_var = model.NewIntVar(0, len(classes_in_semester), f'excess_classes_sem_{sem}')
            _ = model.AddMaxEquality(excess_var, [class_count_var - self.max_classes, 0])

            terms.append(excess_var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class LimitUnitsPerSemester:
    """
    Tier-based soft constraint to limit the number of units per semester.

    Penalizes semesters that exceed max_units threshold using tier-based penalties.
    Note: Penalty is per 3 units over the limit (roughly 1 class equivalent).
    """

    def __init__(self, max_units: int = 60):
        """
        Args:
            max_units: Maximum comfortable number of units per semester
        """
        self.max_units: int = max_units

    def get_name(self) -> str:
        return "Limit Units Per Semester"

    def get_description(self) -> str:
        return f"Penalize semesters with more than {self.max_units} units (tier-based, per 3 units)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add tier-based penalty for semesters exceeding max_units.

        Formula: penalty = (excess_units / 3) × TIER_BASE^tier × 1
        Dividing by 3 makes penalty comparable to class-based constraints.
        """
        # Get tier for this objective (default tier 2 if not set)
        tier = 2
        if context.objective_tiers and 'limit_units_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_units_per_semester']

        penalty = get_tier_penalty(tier, base_cost=1)

        terms = []

        # Group take_vars by semester (only regular semesters 1-12)
        semesters = set(semester for _, semester in take_vars.keys() if semester >= 1)

        for sem in semesters:
            # Count units in this semester
            units_in_semester = []
            for (course_idx, semester), var in take_vars.items():
                if semester == sem:
                    units = context.courses_df[course_idx, 'total_units'] if 'total_units' in context.courses_df.columns else 0
                    if units is not None and units > 0:
                        units_in_semester.append(var * int(units))

            if not units_in_semester:
                continue

            # Create a variable for number of units in this semester
            max_possible_units = sum(
                int(context.courses_df[course_idx, 'total_units'])
                for course_idx, _ in take_vars.keys()
                if 'total_units' in context.courses_df.columns
                and context.courses_df[course_idx, 'total_units'] is not None
                and context.courses_df[course_idx, 'total_units'] > 0
            )
            max_possible_units = max(max_possible_units, 1000)

            units_count_var = model.NewIntVar(0, max_possible_units, f'units_sem_{sem}')
            _ = model.Add(units_count_var == sum(units_in_semester))

            # Create a variable for excess units (above threshold)
            excess_var = model.NewIntVar(0, max_possible_units, f'excess_units_sem_{sem}')
            _ = model.AddMaxEquality(excess_var, [units_count_var - self.max_units, 0])

            # Divide by 3 to get class-equivalent violations, then apply tier penalty
            # This makes 12 excess units ≈ 4 violations ≈ similar to 4 excess classes
            excess_classes_equiv_var = model.NewIntVar(0, max_possible_units // 3 + 1, f'excess_units_equiv_sem_{sem}')
            _ = model.AddDivisionEquality(excess_classes_equiv_var, excess_var, 3)

            # Add tier-based penalty term
            terms.append(excess_classes_equiv_var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class MinimizeMaxSemesterHours:
    """
    Tier-based soft constraint to limit hours per semester.

    Penalizes semesters that exceed max_hours threshold using tier-based penalties.
    Note: Penalty is per 3 hours over the limit (roughly 1 class equivalent).
    """

    def __init__(self, max_hours: float = 60.0, default_hours: float = 12.0):
        """
        Args:
            max_hours: Maximum acceptable weekly hours per semester
            default_hours: Default weekly hours for courses with missing data
        """
        self.max_hours: float = max_hours
        self.default_hours: float = default_hours

    def get_name(self) -> str:
        return "Limit Semester Hours"

    def get_description(self) -> str:
        return f"Penalize semesters with more than {self.max_hours} hours/week (tier-based, per 3 hours)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add tier-based penalty for semesters exceeding max_hours.

        Formula: penalty = (excess_hours / 3) × TIER_BASE^tier × 1
        Dividing by 3 makes penalty comparable to class-based constraints.
        """
        # Get tier for this objective (default tier 2 if not set)
        tier = 2
        if context.objective_tiers and 'minimize_max_semester_hours' in context.objective_tiers:
            tier = context.objective_tiers['minimize_max_semester_hours']

        penalty = get_tier_penalty(tier, base_cost=1)

        terms = []

        # Group take_vars by semester (exclude ASE semester -1)
        semesters = set(semester for _, semester in take_vars.keys() if semester >= 1)

        for sem in semesters:
            # Calculate total hours for this semester
            hours_in_semester = []
            for (course_idx, semester), var in take_vars.items():
                if semester == sem:
                    in_class = context.courses_df[course_idx, 'in_class_hours'] if 'in_class_hours' in context.courses_df.columns else None
                    out_of_class = context.courses_df[course_idx, 'out_of_class_hours'] if 'out_of_class_hours' in context.courses_df.columns else None

                    total_hours = 0
                    has_data = False

                    if in_class is not None:
                        total_hours += float(in_class)  # type: ignore[arg-type]
                        has_data = True
                    if out_of_class is not None:
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
                for c in range(len(context.courses_df)):
                    in_h = context.courses_df[c, 'in_class_hours']
                    out_h = context.courses_df[c, 'out_of_class_hours'] if 'out_of_class_hours' in context.courses_df.columns else 0
                    total = 0
                    if in_h is not None:
                        total += float(in_h)
                    if out_h is not None:
                        total += float(out_h)
                    max_possible += int(total * 10)
            max_possible_hours = max(max_possible, 1000)

            total_hours_var = model.NewIntVar(0, max_possible_hours, f'total_hours_sem_{sem}')
            _ = model.Add(total_hours_var == sum(hours_in_semester))

            # Create variable for excess hours (above threshold)
            # max_hours is in actual hours, but we scaled by 10
            scaled_max_hours = int(self.max_hours * 10)
            excess_var = model.NewIntVar(0, max_possible_hours, f'excess_hours_sem_{sem}')
            _ = model.AddMaxEquality(excess_var, [total_hours_var - scaled_max_hours, 0])

            # Divide by 30 to get class-equivalent violations (3 hours × 10 scaling = 30)
            # This makes 12 excess hours ≈ 4 violations ≈ similar to 4 excess classes
            excess_classes_equiv_var = model.NewIntVar(0, max_possible_hours // 30 + 1, f'excess_hours_equiv_sem_{sem}')
            _ = model.AddDivisionEquality(excess_classes_equiv_var, excess_var, 30)

            # Add tier-based penalty term
            terms.append(excess_classes_equiv_var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class MinimizeFinalsLoad:
    """
    Tier-based soft constraint to limit the number of finals in any semester.

    Penalizes semesters that exceed max_finals threshold using tier-based penalties.
    """

    def __init__(self, max_finals: int = 4):
        """
        Args:
            max_finals: Maximum comfortable number of finals per semester
        """
        self.max_finals: int = max_finals

    def get_name(self) -> str:
        return "Minimize Finals Load"

    def get_description(self) -> str:
        return f"Penalize semesters with more than {self.max_finals} finals (tier-based)"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add tier-based penalty for semesters exceeding max_finals.

        Formula: penalty = violations × TIER_BASE^tier × 1
        """
        # Get tier for this objective (default tier 2 if not set)
        tier = 2
        if context.objective_tiers and 'minimize_finals_load' in context.objective_tiers:
            tier = context.objective_tiers['minimize_finals_load']

        penalty = get_tier_penalty(tier, base_cost=1)

        terms = []

        # Group take_vars by semester (exclude ASE semester -1)
        semesters = set(semester for _, semester in take_vars.keys() if semester >= 1)

        for sem in semesters:
            # Count finals in this semester
            finals_in_semester = []
            for (course_idx, semester), var in take_vars.items():
                if semester == sem:
                    has_final = context.courses_df[course_idx, 'has_final'] if 'has_final' in context.courses_df.columns else False
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

            # Add tier-based penalty term
            terms.append(excess_var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])
