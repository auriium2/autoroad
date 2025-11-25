"""
Handlers for GIR nodes.
"""

from __future__ import annotations

from courses.requirements.types import GIR
from optimizer.requirements import dispatch
from optimizer.requirements.context import Ctx
from optimizer.requirements.nodes.common import attr_satisfaction
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    SatisfactionResult,
    UnitsResult,
)


@dispatch.satisfaction.register
def _gir_satisfaction(node: GIR, ctx: Ctx, path: str) -> SatisfactionResult:
    return attr_satisfaction(ctx, ctx.get_by_attr("gir_attribute", node.gir_code), f"GIR:{node.gir_code}", path)


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
