"""
Handlers for CI nodes.
"""

from __future__ import annotations

from courses.requirements.types import CI
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
def _ci_satisfaction(node: CI, ctx: Ctx, path: str) -> SatisfactionResult:
    return attr_satisfaction(ctx, ctx.get_by_attr("communication_requirement", node.ci_type), node.ci_type, path)


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
