"""
Handlers for SubjectThresholdGroup nodes.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from shared.courses.requirements.types import HASS, Leaf, SubjectThresholdGroup
from shared.optimizer.requirements import dispatch
from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.nodes.common import propagate_children_to_parent
from shared.optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)

# shitty hack for fireroad parity, full class is apparently 9 units according to fireroad
HASS_FULL_CREDIT_UNITS = 9


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


def _is_generic_hass_threshold(node: SubjectThresholdGroup) -> bool:
    """
    Check if this is a threshold on generic HASS (the "8 subjects" requirement).
    
    Generic HASS uses special counting: courses with >=9 units count as 1,
    courses with <9 units count as 0.5 (two half-credit courses = 1 full).
    
    Category requirements (HASS-A, HASS-H, HASS-S) don't use this pairing.
    """
    if len(node.children) != 1:
        return False
    child = node.children[0]
    if not isinstance(child, HASS):
        return False
    # Generic HASS has category None or "HASS"
    return child.category is None or child.category == "HASS"


@dispatch.propagate.register
def _subjectthreshold_propagate(node: SubjectThresholdGroup, ctx: Ctx, path: str) -> None:
    child_paths = [f"{path}.{i}" for i, child in enumerate(node.children) if not child.was_pruned]
    propagate_children_to_parent(ctx, child_paths, path)


def _build_hass_pairing_constraint(
    node: SubjectThresholdGroup,
    ctx: Ctx,
    path: str,
    sat: cp_model.IntVar,
) -> tuple[list[cp_model.IntVar], list[str], list[str]]:
    """
    Build HASS threshold constraint with pairing logic for half-credit courses.
    
    MIT counts HASS subjects as:
    - Courses with >=9 units: 1 full credit
    - Courses with <9 units: 0.5 credit (two = 1 full credit)
    
    Formula: full_count + floor(half_count / 2) >= cutoff
    """
    warnings: list[str] = []
    errors: list[str] = []
    
    # Get all HASS course indices
    child_path = f"{path}.0"
    indices_result = dispatch.course_indices(node.children[0], ctx, child_path)
    all_indices = indices_result.indices
    warnings.extend(indices_result.warnings)
    errors.extend(indices_result.errors)
    
    # Separate into full-credit and half-credit courses
    full_indices: list[int] = []
    half_indices: list[int] = []
    for idx in all_indices:
        units = ctx.get_units(idx)
        if units >= HASS_FULL_CREDIT_UNITS:
            full_indices.append(idx)
        else:
            half_indices.append(idx)
    
    # Create taken vars for each category
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
    
    # Build the constraint: full_count + floor(half_count / 2) >= cutoff
    if not full_taken_vars and not half_taken_vars:
        ctx.model.Add(sat == 0)
        errors.append("No HASS courses available")
        return [], warnings, errors
    
    full_count = sum(full_taken_vars) if full_taken_vars else 0
    
    if half_taken_vars:
        half_count = sum(half_taken_vars)
        # Model integer division: paired_count = half_count // 2
        max_pairs = len(half_taken_vars) // 2
        paired_count = ctx.model.NewIntVar(0, max_pairs, ctx.fresh("hass_pairs"))
        # paired_count * 2 <= half_count <= paired_count * 2 + 1
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
    
    # Return all taken vars as contribution_vars
    all_taken_vars = full_taken_vars + half_taken_vars
    return all_taken_vars, warnings, errors


@dispatch.build.register
def _subjectthreshold_build(node: SubjectThresholdGroup, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    child_paths = [f"{path}.{i}" for i in range(len(node.children))]
    
    # Check for special HASS pairing logic
    use_hass_pairing = _is_generic_hass_threshold(node)

    use_unique_counting = _has_duplicate_courses(node, ctx, path) if not use_hass_pairing else False

    # we need contribution_vars only if children are leaves. For unique counting, we use course_indices instead.
    child_results = [
        dispatch.build(child, ctx, child_paths[i], need_contribution_vars=(not use_unique_counting and not use_hass_pairing))
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

    # Handle HASS pairing logic
    if use_hass_pairing:
        threshold_vars, hass_warnings, hass_errors = _build_hass_pairing_constraint(
            node, ctx, path, sat
        )
        warnings.extend(hass_warnings)
        errors.extend(hass_errors)
    elif use_unique_counting:
        all_indices: list[int] = [] #deduplicate
        for i, child in enumerate(node.children):
            if child.was_pruned:
                continue
            result = dispatch.course_indices(child, ctx, child_paths[i])
            all_indices.extend(result.indices)
            warnings.extend(result.warnings)
            errors.extend(result.errors)
        
        unique_indices = list(set(all_indices))
        
        #threshold counting
        unique_taken_vars: list[cp_model.IntVar] = []
        for idx in unique_indices:
            taken = ctx.get_or_create_taken_var(idx)
            if taken is not None:
                unique_taken_vars.append(taken)
        
        if unique_taken_vars:
            total = sum(unique_taken_vars)
            if node.threshold_type == "GTE":
                ctx.model.Add(total >= node.cutoff).OnlyEnforceIf(sat)
                ctx.model.Add(total < node.cutoff).OnlyEnforceIf(sat.Not())
            else:
                ctx.model.Add(total <= node.cutoff).OnlyEnforceIf(sat)
                ctx.model.Add(total > node.cutoff).OnlyEnforceIf(sat.Not())
        else:
            ctx.model.Add(sat == 0)
        
        # unique is contribution
        threshold_vars = unique_taken_vars
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
