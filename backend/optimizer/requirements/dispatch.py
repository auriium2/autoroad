"""
Single dispatch functions for building requirement constraints.

Each handler module registers its handlers with these dispatchers.
"""

from __future__ import annotations

from functools import singledispatch
from typing import Any

from optimizer.requirements.context import Ctx
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    SatisfactionResult,
    UnitsResult,
)


@singledispatch
def satisfaction(node: Any, ctx: Ctx, path: str) -> SatisfactionResult:
    raise NotImplementedError(f"No satisfaction handler for {type(node)}")


@singledispatch
def contribution(node: Any, ctx: Ctx, path: str) -> ContributionResult:
    raise NotImplementedError(f"No contribution handler for {type(node)}")


@singledispatch
def course_indices(node: Any, ctx: Ctx, path: str) -> CourseIndicesResult:
    raise NotImplementedError(f"No course_indices handler for {type(node)}")


@singledispatch
def units(node: Any, ctx: Ctx, path: str) -> UnitsResult:
    raise NotImplementedError(f"No units handler for {type(node)}")
