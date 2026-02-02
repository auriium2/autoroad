"""
Workload-based objectives: minimize hours, finals, and overload.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext, get_tier_penalty

def _semester_to_year(semester: int) -> int:
    if semester < 1:
        return 0
    return (semester - 1) // 3 + 1


class LimitClassesPerSemester:
    def __init__(self, max_classes: int = 4):
        self.max_classes: int = max_classes

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        tier = 2
        if context.objective_tiers and 'limit_classes_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_classes_per_semester']

        penalty = get_tier_penalty(tier, base_cost=1)
        terms = []

        semester2vars: dict[int, list[cp_model.IntVar]] = {}
        for (course_idx, semester), var in take_vars.items():
            if semester >= 1:
                semester2vars.setdefault(semester, []).append(var)

        for sem, vars_in_sem in semester2vars.items():
            n = len(vars_in_sem)
            class_count_var = model.NewIntVar(0, n, f'classes_sem_{sem}')
            model.Add(class_count_var == sum(vars_in_sem))

            excess_var = model.NewIntVar(0, n, f'excess_classes_sem_{sem}')
            model.AddMaxEquality(excess_var, [class_count_var - self.max_classes, 0])

            terms.append(excess_var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])



class PreferEarlierSemesters:
    """
    Tiny per-class cost based on year of placement.

    Each class placed in year Y costs tier * Y. This is intentionally weak —
    it serves as a tiebreaker that gently biases toward earlier placement
    without overriding other objectives. In isolation it front-loads too
    aggressively, but combined with prerequisite constraints and overload
    penalties it produces natural ramp-up/taper-off schedules.
    """

    def __init__(self):
        pass

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        tier: int = 1
        if context.objective_tiers and 'prefer_earlier_semesters' in context.objective_tiers:
            tier = context.objective_tiers['prefer_earlier_semesters']

        terms: list[cp_model.LinearExpr] = []

        for (course_idx, semester), var in take_vars.items():
            if semester < 1:
                continue
            year: int = _semester_to_year(semester)
            cost: int = tier * year
            if cost > 0:
                terms.append(var * cost)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.constant(0)


class LimitUnitsPerSemester:
    UNIT_DIVISOR: int = 3  # 3 excess units ≈ 1 excess class for penalty scaling

    def __init__(self, max_units: int = 60):
        self.max_units: int = max_units

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        units_col = courses_df['total_units'].to_list() if 'total_units' in courses_df.columns else []
        return {'_units': units_col}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        tier = 2
        if context.objective_tiers and 'limit_units_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_units_per_semester']

        # Apply penalty per excess unit, scaled down by UNIT_DIVISOR so that
        # 3 excess units costs roughly the same as 1 excess class.
        penalty_per_unit = max(1, round(get_tier_penalty(tier, base_cost=1) / self.UNIT_DIVISOR))
        terms = []

        units_list: list = (context.extra or {}).get('_units', [])

        semester2vars: dict[int, list[tuple[int, cp_model.IntVar]]] = {}
        for (course_idx, semester), var in take_vars.items():
            if semester < 1:
                continue
            units = int(units_list[course_idx]) if course_idx < len(units_list) and units_list[course_idx] is not None else 0
            if units > 0:
                semester2vars.setdefault(semester, []).append((units, var))

        for sem, unit_var_pairs in semester2vars.items():
            max_sem_units = sum(u for u, _ in unit_var_pairs)

            units_count_var = model.NewIntVar(0, max_sem_units, f'units_sem_{sem}')
            model.Add(units_count_var == sum(var * u for u, var in unit_var_pairs))

            excess_var = model.NewIntVar(0, max_sem_units, f'excess_units_sem_{sem}')
            model.AddMaxEquality(excess_var, [units_count_var - self.max_units, 0])

            terms.append(excess_var * penalty_per_unit)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class LimitHoursPerSemester:
    def __init__(self, hours_threshold: float = 60.0, fallback_hours: float = 12.0, penalty_interval: int = 3):
        """
        Args:
            hours_threshold: Maximum acceptable weekly hours per semester before penalties apply
            fallback_hours: Assumed weekly hours for courses missing in_class/out_of_class data
            penalty_interval: Penalty is scaled down by this factor so N excess hours ≈ 1 excess class
        """
        self.hours_threshold: float = hours_threshold
        self.fallback_hours: float = fallback_hours
        self.penalty_interval: int = penalty_interval

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        in_class = courses_df['in_class_hours'].to_list() if 'in_class_hours' in courses_df.columns else []
        out_of_class = courses_df['out_of_class_hours'].to_list() if 'out_of_class_hours' in courses_df.columns else []
        return {'_in_class_hours': in_class, '_out_of_class_hours': out_of_class}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        tier = 2
        if context.objective_tiers and 'limit_hours_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_hours_per_semester']

        penalty_per_hour = max(1, round(get_tier_penalty(tier, base_cost=1) / self.penalty_interval))
        terms = []

        extra = context.extra or {}
        in_class_list: list = extra.get('_in_class_hours', [])
        out_of_class_list: list = extra.get('_out_of_class_hours', [])
        fallback = int(self.fallback_hours)

        # Precompute per-course hours and group by semester in a single pass
        semester2vars: dict[int, list[tuple[int, cp_model.IntVar]]] = {}
        for (course_idx, semester), var in take_vars.items():
            if semester < 1:
                continue
            ic = in_class_list[course_idx] if course_idx < len(in_class_list) else None
            oc = out_of_class_list[course_idx] if course_idx < len(out_of_class_list) else None

            total_hours = 0
            has_data = False
            if ic is not None:
                total_hours += int(ic)
                has_data = True
            if oc is not None:
                total_hours += int(oc)
                has_data = True
            if not has_data or total_hours == 0:
                total_hours = fallback

            semester2vars.setdefault(semester, []).append((total_hours, var))

        threshold = int(self.hours_threshold)

        for sem, hour_var_pairs in semester2vars.items():
            max_sem_hours = sum(h for h, _ in hour_var_pairs)

            total_hours_var = model.NewIntVar(0, max_sem_hours, f'total_hours_sem_{sem}')
            model.Add(total_hours_var == sum(var * h for h, var in hour_var_pairs))

            excess_var = model.NewIntVar(0, max_sem_hours, f'excess_hours_sem_{sem}')
            model.AddMaxEquality(excess_var, [total_hours_var - threshold, 0])

            terms.append(excess_var * penalty_per_hour)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])


class LimitFinalsPerSemester:
    def __init__(self, max_finals: int = 4):
        self.max_finals: int = max_finals

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        has_final = courses_df['has_final'].to_list() if 'has_final' in courses_df.columns else []
        return {'_has_final': has_final}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        tier = 2
        if context.objective_tiers and 'limit_finals_per_semester' in context.objective_tiers:
            tier = context.objective_tiers['limit_finals_per_semester']

        penalty = get_tier_penalty(tier, base_cost=1)
        terms = []

        has_final_list: list = (context.extra or {}).get('_has_final', [])

        semester2vars: dict[int, list[cp_model.IntVar]] = {}
        for (course_idx, semester), var in take_vars.items():
            if semester < 1:
                continue
            has_final = has_final_list[course_idx] if course_idx < len(has_final_list) else False
            if has_final:
                semester2vars.setdefault(semester, []).append(var)

        for sem, vars_in_sem in semester2vars.items():
            n = len(vars_in_sem)
            finals_count_var = model.NewIntVar(0, n, f'finals_sem_{sem}')
            model.Add(finals_count_var == sum(vars_in_sem))

            excess_var = model.NewIntVar(0, n, f'excess_finals_sem_{sem}')
            model.AddMaxEquality(excess_var, [finals_count_var - self.max_finals, 0])

            terms.append(excess_var * penalty)

        if terms:
            return cp_model.LinearExpr.Sum(terms)  # type: ignore[return-value]
        return cp_model.LinearExpr.Sum([])
