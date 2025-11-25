"""
Handlers for HASS nodes.
"""

from __future__ import annotations

from courses.requirements.types import HASS
from optimizer.requirements import dispatch
from optimizer.requirements.context import Ctx
from optimizer.requirements.nodes.common import attr_satisfaction
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    SatisfactionResult,
    UnitsResult,
)


def _get_hass_indices(node: HASS, ctx: Ctx) -> list[int]:
    if node.category is None or node.category == "HASS":
        return ctx.get_any_hass()
    return ctx.get_by_attr("hass_attribute", node.category)


@dispatch.satisfaction.register
def _hass_satisfaction(node: HASS, ctx: Ctx, path: str) -> SatisfactionResult:
    indices = _get_hass_indices(node, ctx)
    name = node.category if node.category else "HASS"
    return attr_satisfaction(ctx, indices, name, path)


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
