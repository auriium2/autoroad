"""
Handlers for GIR nodes.
"""

from __future__ import annotations

from shared.courses.requirements.types import GIR
from shared.optimizer.requirements import dispatch
from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.nodes.common import attr_build
from shared.optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


@dispatch.build.register
def _gir_build(node: GIR, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    indices = ctx.get_by_attr("gir_attribute", node.gir_code)
    return attr_build(ctx, indices, f"GIR:{node.gir_code}", path, need_contribution_vars)


@dispatch.course_indices.register
def _gir_course_indices(node: GIR, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult(indices=ctx.get_by_attr("gir_attribute", node.gir_code))


@dispatch.units.register
def _gir_units(node: GIR, ctx: Ctx, path: str) -> UnitsResult:
    indices = ctx.get_by_attr("gir_attribute", node.gir_code)
    return UnitsResult(idx2units={idx: ctx.get_units(idx) for idx in indices})
