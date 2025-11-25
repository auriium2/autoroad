"""
Handlers for PlainString nodes.
"""

from __future__ import annotations

from courses.requirements.types import PlainString
from optimizer.requirements import dispatch
from optimizer.requirements.context import Ctx
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    SatisfactionResult,
    UnitsResult,
)


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
