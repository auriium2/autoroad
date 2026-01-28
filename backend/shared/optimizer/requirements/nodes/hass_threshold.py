"""
Handlers for HASSThreshold nodes.

Generic HASS (category=None or "HASS") uses pairing logic:
- Courses >= 9 units count as 1 full credit
- Courses < 9 units count as 0.5 credit (two = 1 full credit)

Category-specific HASS (HASS-A, HASS-H, HASS-S) counts each course as 1.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from shared.courses.requirements.types import HASSThreshold
from shared.optimizer.requirements import dispatch
from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)

HASS_FULL_CREDIT_UNITS = 9


def _get_hass_indices(node: HASSThreshold, ctx: Ctx) -> list[int]:
    if node.category is None or node.category == "HASS":
        return ctx.get_any_hass()
    return ctx.get_by_attr("hass_attribute", node.category)


def _uses_pairing(node: HASSThreshold) -> bool:
    """Generic HASS uses pairing; category-specific does not."""
    return node.category is None or node.category == "HASS"


@dispatch.build.register
def _hassthreshold_build(node: HASSThreshold, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    warnings: list[str] = []
    errors: list[str] = []

    indices = _get_hass_indices(node, ctx)

    if not indices:
        sat = ctx.model.NewBoolVar(ctx.fresh("hass_thresh"))
        ctx.model.Add(sat == 0)
        errors.append(f"No HASS courses available for {node.category or 'HASS'}")
        return ContributionResult(sat_var=sat, errors=errors)

    for idx in indices:
        ctx.record_course_requirement(idx, path)

    sat = ctx.model.NewBoolVar(ctx.fresh("hass_thresh"))
    key = node.req_id or node.title or "HASSThreshold"
    ctx.register_aux_var(key, sat)
    ctx.register_var_name(sat, key)

    if _uses_pairing(node):
        # HASS pairing logic: full-credit vs half-credit
        full_indices: list[int] = []
        half_indices: list[int] = []
        for idx in indices:
            units = ctx.get_units(idx)
            if units >= HASS_FULL_CREDIT_UNITS:
                full_indices.append(idx)
            else:
                half_indices.append(idx)

        full_taken_vars: list[cp_model.IntVar] = []
        for idx in full_indices:
            taken = ctx.get_or_create_taken_var(idx)
            if taken is not None:
                full_taken_vars.append(taken)

        half_taken_vars: list[cp_model.IntVar] = []
        for idx in half_indices:
            taken = ctx.get_or_create_taken_var(idx)
            if taken is not None:
                half_taken_vars.append(taken)

        if not full_taken_vars and not half_taken_vars:
            ctx.model.Add(sat == 0)
            errors.append("No HASS courses available")
            return ContributionResult(sat_var=sat, errors=errors)

        full_count = sum(full_taken_vars) if full_taken_vars else 0

        if half_taken_vars:
            half_count = sum(half_taken_vars)
            max_pairs = len(half_taken_vars) // 2
            paired_count = ctx.model.NewIntVar(0, max_pairs, ctx.fresh("hass_pairs"))
            ctx.model.Add(paired_count * 2 <= half_count)
            ctx.model.Add(half_count <= paired_count * 2 + 1)
            total_credits = full_count + paired_count
        else:
            total_credits = full_count

        if node.threshold_type == "GTE":
            ctx.model.Add(total_credits >= node.cutoff).OnlyEnforceIf(sat)
            ctx.model.Add(total_credits < node.cutoff).OnlyEnforceIf(sat.Not())
        else:
            ctx.model.Add(total_credits <= node.cutoff).OnlyEnforceIf(sat)
            ctx.model.Add(total_credits > node.cutoff).OnlyEnforceIf(sat.Not())

        all_taken_vars = full_taken_vars + half_taken_vars
    else:
        # Category-specific: simple count
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

        all_taken_vars = taken_vars

    contribution_vars = all_taken_vars if need_contribution_vars else []
    return ContributionResult(
        sat_var=sat,
        contribution_vars=contribution_vars,
        has_nontrivial_threshold=node.cutoff > 0,
        warnings=warnings,
        errors=errors,
    )


@dispatch.course_indices.register
def _hassthreshold_course_indices(node: HASSThreshold, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult(indices=_get_hass_indices(node, ctx))


@dispatch.units.register
def _hassthreshold_units(node: HASSThreshold, ctx: Ctx, path: str) -> UnitsResult:
    indices = _get_hass_indices(node, ctx)
    return UnitsResult(idx2units={idx: ctx.get_units(idx) for idx in indices})
