"""
Handlers for CIThreshold nodes.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from shared.courses.requirements.types import CIThreshold
from shared.optimizer.requirements import dispatch
from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


def _get_ci_indices(node: CIThreshold, ctx: Ctx) -> list[int]:
    return ctx.get_by_attr("communication_requirement", node.ci_type)


@dispatch.build.register
def _cithreshold_build(node: CIThreshold, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    warnings: list[str] = []
    errors: list[str] = []

    indices = _get_ci_indices(node, ctx)

    if not indices:
        sat = ctx.model.NewBoolVar(ctx.fresh("ci_thresh"))
        ctx.model.Add(sat == 0)
        errors.append(f"No courses available for {node.ci_type}")
        return ContributionResult(sat_var=sat, errors=errors)

    for idx in indices:
        ctx.record_course_requirement(idx, path)

    sat = ctx.model.NewBoolVar(ctx.fresh("ci_thresh"))
    key = node.req_id or node.title or "CIThreshold"
    ctx.register_aux_var(key, sat)
    ctx.register_var_name(sat, key)

    taken_vars: list[cp_model.IntVar] = []
    for idx in indices:
        taken = ctx.get_or_create_taken_var(idx)
        if taken is not None:
            taken_vars.append(taken)

    if taken_vars:
        total = sum(taken_vars)
        if node.threshold_type == "GTE":
            ctx.model.Add(total >= node.cutoff).OnlyEnforceIf(sat)
            ctx.model.Add(total < node.cutoff).OnlyEnforceIf(sat.Not())
        else:
            ctx.model.Add(total <= node.cutoff).OnlyEnforceIf(sat)
            ctx.model.Add(total > node.cutoff).OnlyEnforceIf(sat.Not())
    else:
        ctx.model.Add(sat == 0)

    contribution_vars = taken_vars if need_contribution_vars else []
    return ContributionResult(
        sat_var=sat,
        contribution_vars=contribution_vars,
        has_nontrivial_threshold=node.cutoff > 0,
        warnings=warnings,
        errors=errors,
    )


@dispatch.course_indices.register
def _cithreshold_course_indices(node: CIThreshold, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult(indices=_get_ci_indices(node, ctx))


@dispatch.units.register
def _cithreshold_units(node: CIThreshold, ctx: Ctx, path: str) -> UnitsResult:
    indices = _get_ci_indices(node, ctx)
    return UnitsResult(idx2units={idx: ctx.get_units(idx) for idx in indices})
