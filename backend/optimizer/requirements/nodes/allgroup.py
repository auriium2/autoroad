"""
Handlers for AllGroup nodes.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from courses.requirements.types import AllGroup
from optimizer.requirements import dispatch
from optimizer.requirements.context import Ctx
from optimizer.requirements.nodes.common import propagate_children_to_parent
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


@dispatch.propagate.register
def _allgroup_propagate(node: AllGroup, ctx: Ctx, path: str) -> None:
    child_paths = [f"{path}.{i}" for i, child in enumerate(node.children) if not child.was_pruned]
    propagate_children_to_parent(ctx, child_paths, path)


@dispatch.build.register
def _allgroup_build(node: AllGroup, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    child_paths = [f"{path}.{i}" for i in range(len(node.children))]
    
    child_results = [
        dispatch.build(child, ctx, child_paths[i], need_contribution_vars)
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings = [w for r in child_results for w in r.warnings]
    errors = [e for r in child_results for e in r.errors]

    child_sats: list[cp_model.IntVar] = [r.sat_var for r in child_results if r.sat_var is not None]
    sat = ctx.model.NewBoolVar(ctx.fresh("all"))

    key = node.req_id or node.title or "AllGroup"
    ctx.register_aux_var(key, sat)
    ctx.register_var_name(sat, key)

    if not child_sats:
        ctx.model.Add(sat == 0)
        errors.append("AllGroup has no valid children")
        contribution_vars = [sat] if need_contribution_vars else []
        return ContributionResult(sat_var=sat, contribution_vars=contribution_vars, warnings=warnings, errors=errors)

    ctx.model.AddMinEquality(sat, child_sats)
    contribution_vars = [sat] if need_contribution_vars else []
    return ContributionResult(sat_var=sat, contribution_vars=contribution_vars, warnings=warnings, errors=errors)


@dispatch.course_indices.register
def _allgroup_course_indices(node: AllGroup, ctx: Ctx, path: str) -> CourseIndicesResult:
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
def _allgroup_units(node: AllGroup, ctx: Ctx, path: str) -> UnitsResult:
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
