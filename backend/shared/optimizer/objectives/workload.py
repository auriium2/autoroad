"""
Workload-based objectives: minimize hours and finals.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext, get_tier_penalty


class LimitClassesPerSemester:
    def __init__(self, max_classes: int = 4):
        self.max_classes: int = max_classes

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
        # Get tier for this objective (default tier 2 if not set)
        tier = 2
        if context.objective_tiers and 'limit_classes_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_classes_per_semester']
        subject_ids = (context.extra.get('_subject_ids') if context.extra else None) or context.courses_df['subject_id'].to_list()

        penalty = get_tier_penalty(tier, base_cost=1)

        terms = []

        semesters = set(semester for _, semester in take_vars.keys() if semester >= 1)

        for sem in semesters:
            # Count classes in this semester
            classes_in_semester = []
            for (course_idx, semester), var in take_vars.items():
                subject_ids[course_idx]

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
    def __init__(self, max_units: int = 60):
        self.max_units: int = max_units

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


class LimitHoursPerSemester:
    def __init__(self, hours_threshold: float = 60.0, fallback_hours: float = 12.0, penalty_interval: int = 3):
        """
        Args:
            hours_threshold: Maximum acceptable weekly hours per semester before penalties apply
            fallback_hours: Assumed weekly hours for courses missing in_class/out_of_class data
            penalty_interval: Apply one tier penalty for every N hours over the threshold
        """
        self.hours_threshold: float = hours_threshold
        self.fallback_hours: float = fallback_hours
        self.penalty_interval: int = penalty_interval

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
        if context.objective_tiers and 'limit_hours_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_hours_per_semester']

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

                    # If no hours data available, use fallback
                    if not has_data or total_hours == 0:
                        total_hours = self.fallback_hours

                    hours_in_semester.append(var * int(total_hours))

            if not hours_in_semester:
                continue

            # Create variable for total hours in this semester
            # Use a reasonable upper bound (e.g., 20 courses × 20 hours each)
            max_possible_hours = 400

            total_hours_var = model.NewIntVar(0, max_possible_hours, f'total_hours_sem_{sem}')
            _ = model.Add(total_hours_var == sum(hours_in_semester))

            # Create variable for excess hours (above threshold)
            excess_var = model.NewIntVar(0, max_possible_hours, f'excess_hours_sem_{sem}')
            _ = model.AddMaxEquality(excess_var, [total_hours_var - int(self.hours_threshold), 0])

            # Divide by penalty_interval to get violations
            excess_classes_equiv_var = model.NewIntVar(0, max_possible_hours // self.penalty_interval + 1, f'excess_hours_equiv_sem_{sem}')
            _ = model.AddDivisionEquality(excess_classes_equiv_var, excess_var, self.penalty_interval)

            # Add tier-based penalty term
            terms.append(excess_classes_equiv_var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class LimitFinalsPerSemester:
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
        if context.objective_tiers and 'limit_finals_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_finals_per_semester']

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
