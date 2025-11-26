"""
Handlers for Course nodes.
"""

from __future__ import annotations

from shared.courses.requirements.types import Course
from shared.optimizer.requirements import dispatch
from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


@dispatch.build.register
def _course_build(node: Course, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    idx = ctx.get_idx(node.subject_id)
    if idx is None:
        return ContributionResult(sat_var=None, errors=[f"Course '{node.subject_id}' not found"])

    ctx.record_course_requirement(idx, path)

    takes = ctx.get_takes(idx)
    sat = ctx.model.NewBoolVar(ctx.fresh("c"))

    if not takes:
        ctx.model.Add(sat == 0)
        contribution_vars = [sat] if need_contribution_vars else []
        return ContributionResult(sat_var=sat, contribution_vars=contribution_vars, warnings=[f"'{node.subject_id}' never offered"])

    ctx.model.Add(sum(takes) >= 1).OnlyEnforceIf(sat)
    ctx.model.Add(sum(takes) == 0).OnlyEnforceIf(sat.Not())

    contribution_vars = [sat] if need_contribution_vars else []
    return ContributionResult(sat_var=sat, contribution_vars=contribution_vars)


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
