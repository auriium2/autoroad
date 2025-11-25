"""
Handlers for CI nodes.
"""

from __future__ import annotations

from courses.requirements.types import CI
from optimizer.requirements import dispatch
from optimizer.requirements.context import Ctx
from optimizer.requirements.nodes.common import attr_build
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


@dispatch.build.register
def _ci_build(node: CI, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    indices = ctx.get_by_attr("communication_requirement", node.ci_type)
    return attr_build(ctx, indices, node.ci_type, path, need_contribution_vars)


@dispatch.course_indices.register
def _ci_course_indices(node: CI, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult(indices=ctx.get_by_attr("communication_requirement", node.ci_type))


@dispatch.units.register
def _ci_units(node: CI, ctx: Ctx, path: str) -> UnitsResult:
    indices = ctx.get_by_attr("communication_requirement", node.ci_type)
    return UnitsResult(idx2units={idx: ctx.get_units(idx) for idx in indices})
