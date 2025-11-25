"""
Handlers for Course nodes.
"""

from __future__ import annotations

from courses.requirements.types import Course
from optimizer.requirements import dispatch
from optimizer.requirements.context import Ctx
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    SatisfactionResult,
    UnitsResult,
)


@dispatch.satisfaction.register
def _course_satisfaction(node: Course, ctx: Ctx, path: str) -> SatisfactionResult:
    idx = ctx.get_idx(node.subject_id)
    if idx is None:
        return SatisfactionResult(sat_var=None, errors=[f"Course '{node.subject_id}' not found"])

    ctx.record_course_requirement(idx, path)

    takes = ctx.get_takes(idx)
    sat = ctx.model.NewBoolVar(ctx.fresh("c"))

    if not takes:
        ctx.model.Add(sat == 0)
        return SatisfactionResult(sat_var=sat, warnings=[f"'{node.subject_id}' never offered"])

    ctx.model.Add(sum(takes) >= 1).OnlyEnforceIf(sat)
    ctx.model.Add(sum(takes) == 0).OnlyEnforceIf(sat.Not())
    return SatisfactionResult(sat_var=sat)


@dispatch.contribution.register
def _course_contribution(node: Course, ctx: Ctx, path: str) -> ContributionResult:
    sat_result = dispatch.satisfaction(node, ctx, path)
    contribution_vars = [sat_result.sat_var] if sat_result.sat_var is not None else []
    return ContributionResult(
        sat_var=sat_result.sat_var,
        contribution_vars=contribution_vars,
        warnings=sat_result.warnings,
        errors=sat_result.errors
    )


@dispatch.course_indices.register
def _course_indices(node: Course, ctx: Ctx, path: str) -> CourseIndicesResult:
    idx = ctx.get_idx(node.subject_id)
    if idx is None:
        return CourseIndicesResult(errors=[f"Course '{node.subject_id}' not found"])
    return CourseIndicesResult(indices=[idx])


@dispatch.units.register
def _course_units(node: Course, ctx: Ctx, path: str) -> UnitsResult:
    idx = ctx.get_idx(node.subject_id)
    if idx is None:
        return UnitsResult(errors=[f"Course '{node.subject_id}' not found"])
    return UnitsResult(idx2units={idx: ctx.get_units(idx)})
