"""
Handlers for SubjectThresholdGroup nodes.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from shared.courses.requirements.types import SubjectThresholdGroup
from shared.optimizer.requirements import dispatch
from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.nodes.common import propagate_children_to_parent
from shared.optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


def _has_duplicate_courses(node: SubjectThresholdGroup, ctx: Ctx, path: str) -> bool:
    """
    Returns True if the same course appears in multiple children, meaning
    we need to deduplicate when counting toward the threshold.
    """
    seen: set[int] = set()
    child_paths = [f"{path}.{i}" for i in range(len(node.children))]

    for i, child in enumerate(node.children):
        if child.was_pruned:
            continue
        result = dispatch.course_indices(child, ctx, child_paths[i])
        for idx in result.indices:
            if idx in seen:
                return True
            seen.add(idx)
    return False


@dispatch.propagate.register
def _subjectthreshold_propagate(node: SubjectThresholdGroup, ctx: Ctx, path: str) -> None:
    child_paths = [f"{path}.{i}" for i, child in enumerate(node.children) if not child.was_pruned]
    propagate_children_to_parent(ctx, child_paths, path)


@dispatch.build.register
def _subjectthreshold_build(node: SubjectThresholdGroup, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    child_paths = [f"{path}.{i}" for i in range(len(node.children))]

    use_unique_counting = _has_duplicate_courses(node, ctx, path)

    # we need contribution_vars only if children are leaves. For unique counting, we use course_indices instead.
    child_results = [
        dispatch.build(child, ctx, child_paths[i], need_contribution_vars=(not use_unique_counting))
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings: list[str] = [w for r in child_results for w in r.warnings]
    errors: list[str] = [e for r in child_results for e in r.errors]

    if node.threshold_type == "LTE":
        warnings.append(f"Group '{node.title}' uses LTE threshold which may need manual review")

    child_sats: list[cp_model.IntVar] = [r.sat_var for r in child_results if r.sat_var is not None]

    sat = ctx.model.NewBoolVar(ctx.fresh("subj_thresh"))

    key = node.req_id or node.title or "SubjectThresholdGroup"
    ctx.register_aux_var(key, sat)
    ctx.register_var_name(sat, key)

    if not child_results:
        ctx.model.Add(sat == 0)
        errors.append("SubjectThresholdGroup has no valid children")
        return ContributionResult(
            sat_var=sat,
            contribution_vars=[],
            has_nontrivial_threshold=node.cutoff > 0,
            warnings=warnings,
            errors=errors
        )

    if use_unique_counting:
        all_indices: list[int] = []  # deduplicate
        child_idx_to_indices = {}
        for i, child in enumerate(node.children):
            if child.was_pruned:
                continue
            result = dispatch.course_indices(child, ctx, child_paths[i])
            all_indices.extend(result.indices)
            child_idx_to_indices[i] = set(result.indices)
            warnings.extend(result.warnings)
            errors.extend(result.errors)

        unique_indices = list(set(all_indices))

        # threshold counting with structural validation
        contrib_vars: list[cp_model.IntVar] = []
        for idx in unique_indices:
            taken = ctx.get_or_create_taken_var(idx)
            if taken is None:
                continue
            
            # Find all children of this SubjectThresholdGroup that contain this course
            containing_sats = []
            for i, child_result in enumerate(child_results):
                # Map the index in child_results back to the original node.children index
                # since pruned children are skipped in child_results
                orig_i = [index for index, c in enumerate(node.children) if not c.was_pruned][i]
                if idx in child_idx_to_indices.get(orig_i, set()):
                    if child_result.sat_var is not None:
                        containing_sats.append(child_result.sat_var)
            
            if containing_sats:
                # The course contributes if it is taken AND at least one of the children containing it is satisfied
                any_sat = ctx.model.NewBoolVar(ctx.fresh("any_sat"))
                if len(containing_sats) == 1:
                    ctx.model.Add(any_sat == containing_sats[0])
                else:
                    ctx.model.AddMaxEquality(any_sat, containing_sats)
                
                contrib = ctx.model.NewBoolVar(ctx.fresh("course_contrib"))
                ctx.model.AddMinEquality(contrib, [taken, any_sat])
                contrib_vars.append(contrib)

        if contrib_vars:
            total = sum(contrib_vars)
            if node.threshold_type == "GTE":
                ctx.model.Add(total >= node.cutoff).OnlyEnforceIf(sat)
                ctx.model.Add(total < node.cutoff).OnlyEnforceIf(sat.Not())
            else:
                ctx.model.Add(total <= node.cutoff).OnlyEnforceIf(sat)
                ctx.model.Add(total > node.cutoff).OnlyEnforceIf(sat.Not())
        else:
            ctx.model.Add(sat == 0)

        threshold_vars = contrib_vars
    else:
        # Simple case: children are leaves, use contribution_vars directly
        child_contribution_vars: list[cp_model.IntVar] = []
        for r in child_results:
            child_contribution_vars.extend(r.contribution_vars)

        if child_contribution_vars:
            total = sum(child_contribution_vars)
            if node.threshold_type == "GTE":
                ctx.model.Add(total >= node.cutoff).OnlyEnforceIf(sat)
                ctx.model.Add(total < node.cutoff).OnlyEnforceIf(sat.Not())
            else:
                ctx.model.Add(total <= node.cutoff).OnlyEnforceIf(sat)
                ctx.model.Add(total > node.cutoff).OnlyEnforceIf(sat.Not())
        else:
            ctx.model.Add(sat == 0)

        threshold_vars = child_contribution_vars

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

    # Propagate course-to-requirement mappings from children up to this node
    dispatch.propagate(node, ctx, path)

    contribution_vars = threshold_vars if need_contribution_vars else []
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
