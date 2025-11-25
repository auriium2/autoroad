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
    UnitsResult,
)


@dispatch.build.register
def _plainstring_build(node: PlainString, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    # PlainString nodes are assumed satisfied (open-ended requirements)
    sat = ctx.model.NewBoolVar(ctx.fresh("ps"))
    ctx.model.Add(sat == 1)
    
    contribution_vars = [sat] if need_contribution_vars else []
    return ContributionResult(
        sat_var=sat,
        contribution_vars=contribution_vars,
        warnings=[f"PlainString '{node.description}' assumed satisfied"]
    )


@dispatch.course_indices.register
def _plainstring_course_indices(node: PlainString, ctx: Ctx, path: str) -> CourseIndicesResult:
    return CourseIndicesResult()  # No specific courses


@dispatch.units.register
def _plainstring_units(node: PlainString, ctx: Ctx, path: str) -> UnitsResult:
    return UnitsResult()  # No specific units
