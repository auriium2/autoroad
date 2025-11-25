"""
Single dispatch functions for building requirement constraints.

Each handler module registers its handlers with these dispatchers.
"""

from __future__ import annotations

from functools import singledispatch
from typing import Any, Callable

from optimizer.requirements.context import Ctx
from optimizer.requirements.result import (
    ContributionResult,
    CourseIndicesResult,
    UnitsResult,
)


@singledispatch
def _build_impl(node: Any, ctx: Ctx, path: str, need_contribution_vars: bool) -> ContributionResult:
    raise NotImplementedError(f"No build handler for {type(node)}")


class BuildDispatcher:
    """
    Wrapper around singledispatch that provides a cleaner interface.
    
    This allows calling build(node, ctx, path, need_contribution_vars=False)
    while still using singledispatch for the implementation.
    """
    
    def __call__(self, node: Any, ctx: Ctx, path: str, need_contribution_vars: bool = False) -> ContributionResult:
        """
        Build constraints for a requirement node.
        
        Args:
            node: The requirement node to process
            ctx: The constraint building context
            path: The path to this node in the tree (e.g., "root.0.1")
            need_contribution_vars: Whether to collect contribution variables.
                Only SubjectThresholdGroup needs these, so this is False by default
                to avoid unnecessary work.
        
        Returns:
            ContributionResult with sat_var and optionally contribution_vars
        """
        return _build_impl(node, ctx, path, need_contribution_vars)
    
    @property
    def register(self) -> Callable[..., Any]:
        return _build_impl.register


build = BuildDispatcher()


@singledispatch
def course_indices(node: Any, ctx: Ctx, path: str) -> CourseIndicesResult:
    raise NotImplementedError(f"No course_indices handler for {type(node)}")


@singledispatch
def units(node: Any, ctx: Ctx, path: str) -> UnitsResult:
    raise NotImplementedError(f"No units handler for {type(node)}")


@singledispatch
def propagate(node: Any, ctx: Ctx, path: str) -> None:
    """Propagate course-to-requirement mappings from children up to this node's path."""
    pass  # Default: no-op for leaf nodes
