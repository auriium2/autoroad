"""
Handlers for SubjectThresholdGroup nodes.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from courses.requirements.types import SubjectThresholdGroup
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
def _subjectthreshold_satisfaction(node: SubjectThresholdGroup, ctx: Ctx, path: str) -> SatisfactionResult:
    contrib_result = dispatch.contribution(node, ctx, path)
    return SatisfactionResult(
        sat_var=contrib_result.sat_var,
        warnings=contrib_result.warnings,
        errors=contrib_result.errors
    )


@dispatch.contribution.register
def _subjectthreshold_contribution(node: SubjectThresholdGroup, ctx: Ctx, path: str) -> ContributionResult:
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

    child_sats: list[cp_model.IntVar] = [r.sat_var for r in child_results if r.sat_var is not None]
    contribution_vars: list[cp_model.IntVar] = []
    for r in child_results:
        contribution_vars.extend(r.contribution_vars)

    sat = ctx.model.NewBoolVar(ctx.fresh("subj_thresh"))

    key = node.req_id or node.title or "SubjectThresholdGroup"
    ctx.register_aux_var(key, sat)
    ctx.register_var_name(sat, key)

    if not child_results:
        ctx.model.Add(sat == 0)
        errors.append("SubjectThresholdGroup has no valid children")
        return ContributionResult(
            sat_var=sat,
            contribution_vars=contribution_vars,
            has_nontrivial_threshold=node.cutoff > 0,
            warnings=warnings,
            errors=errors
        )

    # Threshold constraint: sum contributions >= cutoff
    if contribution_vars:
        total = sum(contribution_vars)
        if node.threshold_type == "GTE":
            ctx.model.Add(total >= node.cutoff).OnlyEnforceIf(sat)
            ctx.model.Add(total < node.cutoff).OnlyEnforceIf(sat.Not())
        else:
            ctx.model.Add(total <= node.cutoff).OnlyEnforceIf(sat)
            ctx.model.Add(total > node.cutoff).OnlyEnforceIf(sat.Not())
    else:
        ctx.model.Add(sat == 0)

    # Connection constraint
    if child_sats:
        if node.connection_type == "all":
            for child_sat in child_sats:
                ctx.model.Add(child_sat == 1).OnlyEnforceIf(sat)
        elif node.connection_type == "any" and node.cutoff > 0:
            ctx.model.Add(sum(child_sats) >= 1).OnlyEnforceIf(sat)

    # Distinct constraint
    if node.distinct_threshold is not None and node.distinct_threshold.cutoff > 0:
        children_have_thresholds = any(r.has_nontrivial_threshold for r in child_results)

        if children_have_thresholds:
            if child_sats:
                if node.distinct_threshold.comparison == "GTE":
                    ctx.model.Add(sum(child_sats) >= node.distinct_threshold.cutoff).OnlyEnforceIf(sat)
                else:
                    ctx.model.Add(sum(child_sats) <= node.distinct_threshold.cutoff).OnlyEnforceIf(sat)
        else:
            contrib_indicators: list[cp_model.IntVar] = []
            for r in child_results:
                if r.contribution_vars:
                    has_contrib = ctx.model.NewBoolVar(ctx.fresh("has_contrib"))
                    ctx.model.Add(sum(r.contribution_vars) >= 1).OnlyEnforceIf(has_contrib)
                    ctx.model.Add(sum(r.contribution_vars) == 0).OnlyEnforceIf(has_contrib.Not())
                    contrib_indicators.append(has_contrib)

            if contrib_indicators:
                if node.distinct_threshold.comparison == "GTE":
                    ctx.model.Add(sum(contrib_indicators) >= node.distinct_threshold.cutoff).OnlyEnforceIf(sat)
                else:
                    ctx.model.Add(sum(contrib_indicators) <= node.distinct_threshold.cutoff).OnlyEnforceIf(sat)

    return ContributionResult(
        sat_var=sat,
        contribution_vars=contribution_vars,
        has_nontrivial_threshold=node.cutoff > 0,
        warnings=warnings,
        errors=errors
    )


@dispatch.course_indices.register
def _subjectthreshold_course_indices(node: SubjectThresholdGroup, ctx: Ctx, path: str) -> CourseIndicesResult:
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
def _subjectthreshold_units(node: SubjectThresholdGroup, ctx: Ctx, path: str) -> UnitsResult:
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
