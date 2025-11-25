"""
Constraint handlers for req_2 requirement nodes.

This module registers handlers for all node types with the dispatch system.
Import this module to ensure all handlers are registered.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from courses.requirements.types import (
    CI,
    GIR,
    HASS,
    AllGroup,
    AnyGroup,
    Course,
    PlainString,
    SubjectThresholdGroup,
    UnitThresholdGroup,
)
from optimizer.requirements import dispatch
from optimizer.requirements.context import Ctx
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    SatisfactionResult,
    UnitsResult,
)

# =============================================================================
# Course handlers
# =============================================================================

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


# =============================================================================
# GIR handlers
# =============================================================================

def _attr_satisfaction(ctx: Ctx, indices: list[int], name: str, path: str) -> SatisfactionResult:
    if not indices:
        return SatisfactionResult(sat_var=None, errors=[f"No courses for {name}"])

    for idx in indices:
        ctx.record_course_requirement(idx, path)

    takes = []
    for idx in indices:
        takes.extend(ctx.get_takes(idx))

    sat = ctx.model.NewBoolVar(ctx.fresh("a"))
    if not takes:
        ctx.model.Add(sat == 0)
        return SatisfactionResult(sat_var=sat, warnings=[f"No semesters for {name}"])

    ctx.model.Add(sum(takes) >= 1).OnlyEnforceIf(sat)
    ctx.model.Add(sum(takes) == 0).OnlyEnforceIf(sat.Not())
    return SatisfactionResult(sat_var=sat)


@dispatch.satisfaction.register
def _gir_satisfaction(node: GIR, ctx: Ctx, path: str) -> SatisfactionResult:
    return _attr_satisfaction(ctx, ctx.get_by_attr("gir_attribute", node.gir_code), f"GIR:{node.gir_code}", path)


@dispatch.contribution.register
def _gir_contribution(node: GIR, ctx: Ctx, path: str) -> ContributionResult:
    sat_result = dispatch.satisfaction(node, ctx, path)
    contribution_vars = [sat_result.sat_var] if sat_result.sat_var is not None else []
    return ContributionResult(
        sat_var=sat_result.sat_var,
        contribution_vars=contribution_vars,
        warnings=sat_result.warnings,
        errors=sat_result.errors
    )


@dispatch.course_indices.register
def _gir_course_indices(node: GIR, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult(indices=ctx.get_by_attr("gir_attribute", node.gir_code))


@dispatch.units.register
def _gir_units(node: GIR, ctx: Ctx, path: str) -> UnitsResult:
    indices = ctx.get_by_attr("gir_attribute", node.gir_code)
    return UnitsResult(idx2units={idx: ctx.get_units(idx) for idx in indices})


# =============================================================================
# HASS handlers
# =============================================================================

def _get_hass_indices(node: HASS, ctx: Ctx) -> list[int]:
    if node.category is None or node.category == "HASS":
        return ctx.get_any_hass()
    return ctx.get_by_attr("hass_attribute", node.category)


@dispatch.satisfaction.register
def _hass_satisfaction(node: HASS, ctx: Ctx, path: str) -> SatisfactionResult:
    indices = _get_hass_indices(node, ctx)
    name = node.category if node.category else "HASS"
    return _attr_satisfaction(ctx, indices, name, path)


@dispatch.contribution.register
def _hass_contribution(node: HASS, ctx: Ctx, path: str) -> ContributionResult:
    sat_result = dispatch.satisfaction(node, ctx, path)
    contribution_vars = [sat_result.sat_var] if sat_result.sat_var is not None else []
    return ContributionResult(
        sat_var=sat_result.sat_var,
        contribution_vars=contribution_vars,
        warnings=sat_result.warnings,
        errors=sat_result.errors
    )


@dispatch.course_indices.register
def _hass_course_indices(node: HASS, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult(indices=_get_hass_indices(node, ctx))


@dispatch.units.register
def _hass_units(node: HASS, ctx: Ctx, path: str) -> UnitsResult:
    indices = _get_hass_indices(node, ctx)
    return UnitsResult(idx2units={idx: ctx.get_units(idx) for idx in indices})


# =============================================================================
# CI handlers
# =============================================================================

@dispatch.satisfaction.register
def _ci_satisfaction(node: CI, ctx: Ctx, path: str) -> SatisfactionResult:
    return _attr_satisfaction(ctx, ctx.get_by_attr("communication_requirement", node.ci_type), node.ci_type, path)


@dispatch.contribution.register
def _ci_contribution(node: CI, ctx: Ctx, path: str) -> ContributionResult:
    sat_result = dispatch.satisfaction(node, ctx, path)
    contribution_vars = [sat_result.sat_var] if sat_result.sat_var is not None else []
    return ContributionResult(
        sat_var=sat_result.sat_var,
        contribution_vars=contribution_vars,
        warnings=sat_result.warnings,
        errors=sat_result.errors
    )


@dispatch.course_indices.register
def _ci_course_indices(node: CI, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult(indices=ctx.get_by_attr("communication_requirement", node.ci_type))


@dispatch.units.register
def _ci_units(node: CI, ctx: Ctx, path: str) -> UnitsResult:
    indices = ctx.get_by_attr("communication_requirement", node.ci_type)
    return UnitsResult(idx2units={idx: ctx.get_units(idx) for idx in indices})


# =============================================================================
# PlainString handlers
# =============================================================================

@dispatch.satisfaction.register
def _plainstring_satisfaction(node: PlainString, ctx: Ctx, path: str) -> SatisfactionResult:
    sat = ctx.model.NewBoolVar(ctx.fresh("p"))
    ctx.model.Add(sat == 1)
    desc = node.description[:40] + "..." if len(node.description) > 40 else node.description
    return SatisfactionResult(sat_var=sat, warnings=[f"Plain-string ignored: '{desc}'"])


@dispatch.contribution.register
def _plainstring_contribution(node: PlainString, ctx: Ctx, path: str) -> ContributionResult:
    sat_result = dispatch.satisfaction(node, ctx, path)
    contribution_vars = [sat_result.sat_var] if sat_result.sat_var is not None else []
    return ContributionResult(
        sat_var=sat_result.sat_var,
        contribution_vars=contribution_vars,
        warnings=sat_result.warnings,
        errors=sat_result.errors
    )


@dispatch.course_indices.register
def _plainstring_course_indices(node: PlainString, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult()


@dispatch.units.register
def _plainstring_units(node: PlainString, ctx: Ctx, path: str) -> UnitsResult:
    return UnitsResult()


# =============================================================================
# AllGroup handlers
# =============================================================================

@dispatch.satisfaction.register
def _allgroup_satisfaction(node: AllGroup, ctx: Ctx, path: str) -> SatisfactionResult:
    child_results = [
        dispatch.satisfaction(child, ctx, f"{path}.{i}")
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings = [w for r in child_results for w in r.warnings]
    errors = [e for r in child_results for e in r.errors]

    child_sats: list[cp_model.IntVar] = [r.sat_var for r in child_results if r.sat_var is not None]
    sat = ctx.model.NewBoolVar(ctx.fresh("all"))

    if not child_sats:
        ctx.model.Add(sat == 0)
        errors.append("AllGroup has no valid children")
    else:
        ctx.model.AddMinEquality(sat, child_sats)

    return SatisfactionResult(sat_var=sat, warnings=warnings, errors=errors)


@dispatch.contribution.register
def _allgroup_contribution(node: AllGroup, ctx: Ctx, path: str) -> ContributionResult:
    child_results = [
        dispatch.contribution(child, ctx, f"{path}.{i}")
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
        return ContributionResult(sat_var=sat, contribution_vars=[sat], warnings=warnings, errors=errors)

    ctx.model.AddMinEquality(sat, child_sats)
    return ContributionResult(sat_var=sat, contribution_vars=[sat], warnings=warnings, errors=errors)


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


# =============================================================================
# AnyGroup handlers
# =============================================================================

@dispatch.satisfaction.register
def _anygroup_satisfaction(node: AnyGroup, ctx: Ctx, path: str) -> SatisfactionResult:
    child_results = [
        dispatch.satisfaction(child, ctx, f"{path}.{i}")
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings = [w for r in child_results for w in r.warnings]
    errors = [e for r in child_results for e in r.errors]

    child_sats: list[cp_model.IntVar] = [r.sat_var for r in child_results if r.sat_var is not None]
    sat = ctx.model.NewBoolVar(ctx.fresh("any"))

    if not child_sats:
        ctx.model.Add(sat == 0)
        errors.append("AnyGroup has no valid children")
    else:
        ctx.model.AddMaxEquality(sat, child_sats)

    return SatisfactionResult(sat_var=sat, warnings=warnings, errors=errors)


@dispatch.contribution.register
def _anygroup_contribution(node: AnyGroup, ctx: Ctx, path: str) -> ContributionResult:
    child_results = [
        dispatch.contribution(child, ctx, f"{path}.{i}")
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings = [w for r in child_results for w in r.warnings]
    errors = [e for r in child_results for e in r.errors]

    child_sats: list[cp_model.IntVar] = [r.sat_var for r in child_results if r.sat_var is not None]
    contribution_vars: list[cp_model.IntVar] = []
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


# =============================================================================
# SubjectThresholdGroup handlers
# =============================================================================

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
    child_results = [
        dispatch.contribution(child, ctx, f"{path}.{i}")
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings: list[str] = [w for r in child_results for w in r.warnings]
    errors: list[str] = [e for r in child_results for e in r.errors]

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


# =============================================================================
# UnitThresholdGroup handlers
# =============================================================================

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
    child_results = [
        dispatch.contribution(child, ctx, f"{path}.{i}")
        for i, child in enumerate(node.children)
        if not child.was_pruned
    ]
    warnings: list[str] = [w for r in child_results for w in r.warnings]
    errors: list[str] = [e for r in child_results for e in r.errors]

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
