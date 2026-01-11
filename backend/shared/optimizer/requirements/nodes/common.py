"""
Common utilities for node handlers.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from shared.optimizer.requirements.context import Ctx
from shared.optimizer.requirements.result import ContributionResult


def propagate_children_to_parent(ctx: Ctx, child_paths: list[str], parent_path: str) -> None:
    """
    Propagate course-to-requirement mappings from children up to parent.

    This allows category rewards to apply at any level of the requirement tree.
    If a course satisfies root.6.0.0.0, it should also be recorded as satisfying
    root.6.0.0, root.6.0, root.6, etc.
    """
    courses_from_children: set[int] = set()
    for course_idx, req_paths in ctx.course_to_requirements.items():
        for child_path in child_paths:
            for req_path in req_paths:
                if req_path == child_path or req_path.startswith(child_path + "."):
                    courses_from_children.add(course_idx)
                    break

    for course_idx in courses_from_children:
        ctx.record_course_requirement(course_idx, parent_path)


def attr_build(ctx: Ctx, indices: list[int], name: str, path: str, need_contribution_vars: bool) -> ContributionResult:
    """Build constraints for attribute-based requirements (GIR, HASS, CI)."""
    if not indices:
        return ContributionResult(sat_var=None, errors=[f"No courses for {name}"])

    for idx in indices:
        ctx.record_course_requirement(idx, path)

    takes: list[cp_model.IntVar] = []
    for idx in indices:
        takes.extend(ctx.get_takes(idx))

    sat = ctx.model.NewBoolVar(ctx.fresh("a"))
    if not takes:
        ctx.model.Add(sat == 0)
        contribution_vars = [sat] if need_contribution_vars else []
        return ContributionResult(sat_var=sat, contribution_vars=contribution_vars, warnings=[f"No semesters for {name}"])

    ctx.model.Add(sum(takes) >= 1).OnlyEnforceIf(sat)
    ctx.model.Add(sum(takes) == 0).OnlyEnforceIf(sat.Not())

    contribution_vars = [sat] if need_contribution_vars else []
    return ContributionResult(sat_var=sat, contribution_vars=contribution_vars)
