"""
Handlers for AnyGroup nodes.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from shared.courses.requirements.types import AnyGroup
from shared.optimizer.requirements import dispatch
from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.nodes.common import propagate_children_to_parent
from shared.optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


@dispatch.propagate.register
def _anygroup_propagate(node: AnyGroup, ctx: Ctx, path: str) -> None:
    child_paths = [f"{path}.{i}" for i, child in enumerate(node.children) if not child.was_pruned]
    propagate_children_to_parent(ctx, child_paths, path)


@dispatch.build.register
def _anygroup_build(node: AnyGroup, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    child_paths = [f"{path}.{i}" for i in range(len(node.children))]

    child_results = [
        dispatch.build(child, ctx, child_paths[i], need_contribution_vars)
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings = [w for r in child_results for w in r.warnings]
    errors = [e for r in child_results for e in r.errors]

    child_sats: list[cp_model.IntVar] = [r.sat_var for r in child_results if r.sat_var is not None]

    # Collect contribution_vars from children if needed
    contribution_vars: list[cp_model.IntVar] = []
    if need_contribution_vars:
        for r in child_results:
            contribution_vars.extend(r.contribution_vars)

    sat = ctx.model.NewBoolVar(ctx.fresh("any"))

    key = node.req_id or node.title or "AnyGroup"
    ctx.register_aux_var(key, sat)
    ctx.register_var_name(sat, key)

    if not child_sats:
        ctx.model.Add(sat == 0)
        errors.append("AnyGroup has no valid children")
    else:
        ctx.model.AddMaxEquality(sat, child_sats)

    # Propagate course-to-requirement mappings from children up to this node
    dispatch.propagate(node, ctx, path)

    return ContributionResult(sat_var=sat, contribution_vars=contribution_vars, warnings=warnings, errors=errors)


@dispatch.course_indices.register
def _anygroup_course_indices(node: AnyGroup, ctx: Ctx, path: str) -> CourseIndicesResult:
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
def _anygroup_units(node: AnyGroup, ctx: Ctx, path: str) -> UnitsResult:
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
