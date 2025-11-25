"""
Handlers for UnitThresholdGroup nodes.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from courses.requirements.types import UnitThresholdGroup
from optimizer.requirements import dispatch
from optimizer.requirements.context import Ctx
from optimizer.requirements.nodes.common import propagate_courses_to_parent
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    SatisfactionResult,
    UnitsResult,
)


@dispatch.satisfaction.register
def _unitthreshold_satisfaction(node: UnitThresholdGroup, ctx: Ctx, path: str) -> SatisfactionResult:
    contrib_result = dispatch.contribution(node, ctx, path)
    return SatisfactionResult(
        sat_var=contrib_result.sat_var,
        warnings=contrib_result.warnings,
        errors=contrib_result.errors
    )


@dispatch.contribution.register
def _unitthreshold_contribution(node: UnitThresholdGroup, ctx: Ctx, path: str) -> ContributionResult:
    child_paths = [f"{path}.{i}" for i in range(len(node.children))]
    
    child_results = [
        dispatch.contribution(child, ctx, child_paths[i])
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings: list[str] = [w for r in child_results for w in r.warnings]
    errors: list[str] = [e for r in child_results for e in r.errors]

    propagate_courses_to_parent(ctx, child_paths, path)

    if node.threshold_type == "LTE":
        warnings.append(f"Group '{node.title}' uses LTE threshold which may need manual review")

    contribution_vars: list[cp_model.IntVar] = []
    for r in child_results:
        contribution_vars.extend(r.contribution_vars)

    # Collect course indices using units query
    units_result = dispatch.units(node, ctx, path)
    idx2units = units_result.idx2units
    warnings.extend(units_result.warnings)
    errors.extend(units_result.errors)

    sat = ctx.model.NewBoolVar(ctx.fresh("unit_thresh"))

    key = node.req_id or node.title or "UnitThresholdGroup"
    ctx.register_aux_var(key, sat)
    ctx.register_var_name(sat, key)

    total_available = sum(idx2units.values())

    # Open-ended fallback
    if not idx2units or total_available < node.cutoff:
        ctx.model.Add(sat == 1)
        warnings.append(
            f"Unit requirement '{node.title}' requires {node.cutoff} units but only "
            f"{total_available} available. Assuming satisfiable with unlisted courses."
        )
        return ContributionResult(
            sat_var=sat,
            contribution_vars=contribution_vars,
            has_nontrivial_threshold=node.cutoff > 0,
            warnings=warnings,
            errors=errors
        )

    # Build unit contributions
    unit_vars: list[cp_model.IntVar] = []
    for course_idx, units in idx2units.items():
        takes = ctx.get_takes(course_idx)
        if not takes:
            continue

        taken = ctx.model.NewBoolVar(ctx.fresh("taken"))
        ctx.model.AddMaxEquality(taken, takes)

        contrib = ctx.model.NewIntVar(0, units, ctx.fresh("u"))
        ctx.model.Add(contrib == units).OnlyEnforceIf(taken)
        ctx.model.Add(contrib == 0).OnlyEnforceIf(taken.Not())
        unit_vars.append(contrib)

    if not unit_vars:
        ctx.model.Add(sat == 0)
        errors.append("UnitThresholdGroup has no valid courses")
    else:
        total = sum(unit_vars)
        if node.threshold_type == "GTE":
            ctx.model.Add(total >= node.cutoff).OnlyEnforceIf(sat)
            ctx.model.Add(total < node.cutoff).OnlyEnforceIf(sat.Not())
        else:
            ctx.model.Add(total <= node.cutoff).OnlyEnforceIf(sat)
            ctx.model.Add(total > node.cutoff).OnlyEnforceIf(sat.Not())

    return ContributionResult(
        sat_var=sat,
        contribution_vars=contribution_vars,
        has_nontrivial_threshold=node.cutoff > 0,
        warnings=warnings,
        errors=errors
    )


@dispatch.course_indices.register
def _unitthreshold_course_indices(node: UnitThresholdGroup, ctx: Ctx, path: str) -> CourseIndicesResult:
    all_indices: list[int] = []
    warnings: list[str] = []
    errors: list[str] = []

    for i, child in enumerate(node.children):
        if child.was_pruned:
            continue
        result = dispatch.course_indices(child, ctx, f"{path}.{i}")
        all_indices.extend(result.indices)
        warnings.extend(result.warnings)
        errors.extend(result.errors)

    return CourseIndicesResult(indices=all_indices, warnings=warnings, errors=errors)


@dispatch.units.register
def _unitthreshold_units(node: UnitThresholdGroup, ctx: Ctx, path: str) -> UnitsResult:
    idx2units: dict[int, int] = {}
    warnings: list[str] = []
    errors: list[str] = []

    for i, child in enumerate(node.children):
        if child.was_pruned:
            continue
        result = dispatch.units(child, ctx, f"{path}.{i}")
        idx2units.update(result.idx2units)
        warnings.extend(result.warnings)
        errors.extend(result.errors)

    return UnitsResult(idx2units=idx2units, warnings=warnings, errors=errors)
