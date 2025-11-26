"""
Handlers for HASS nodes.
"""

from __future__ import annotations

from shared.courses.requirements.types import HASS
from shared.optimizer.requirements import dispatch
from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.nodes.common import attr_build
from shared.optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


def _get_hass_indices(node: HASS, ctx: Ctx) -> list[int]:
    if node.category is None or node.category == "HASS":
        return ctx.get_any_hass()
    return ctx.get_by_attr("hass_attribute", node.category)


@dispatch.build.register
def _hass_build(node: HASS, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    indices = _get_hass_indices(node, ctx)
    name = node.category if node.category else "HASS"
    return attr_build(ctx, indices, name, path, need_contribution_vars)


@dispatch.course_indices.register
def _hass_course_indices(node: HASS, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult(indices=_get_hass_indices(node, ctx))


@dispatch.units.register
def _hass_units(node: HASS, ctx: Ctx, path: str) -> UnitsResult:
    indices = _get_hass_indices(node, ctx)
    return UnitsResult(idx2units={idx: ctx.get_units(idx) for idx in indices})
