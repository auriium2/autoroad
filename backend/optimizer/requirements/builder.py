"""
Top-level entry point for building requirement constraints.

This module provides the main interface for converting requirement trees
into OR-Tools CP-SAT constraints.
"""

from __future__ import annotations

from typing import TypedDict

import polars as pl
from ortools.sat.python import cp_model

from courses.requirements import types
from optimizer.requirements import dispatch

# Import handlers to register them with the dispatch system
from optimizer.requirements import handlers as _handlers  # noqa: F401
from optimizer.requirements.context import Ctx
from optimizer.requirements.result import ContributionResult


class ConstraintSummary(TypedDict):
    warning_count: int
    error_count: int
    warnings: list[str]
    errors: list[str]
    has_issues: bool


def build_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    requirement: types.Node,
    courses_df: pl.DataFrame,
    enforce: bool = True,
) -> tuple[ContributionResult, Ctx]:
    """
    Build constraints for a requirement tree.

    Args:
        model: The CP-SAT model to add constraints to
        take_vars: Dictionary mapping (course_idx, semester) to decision variables
        requirement: Root of the requirement tree
        courses_df: DataFrame containing course information
        enforce: Whether to require the root requirement be satisfied (default: True)

    Returns:
        Tuple of (ContributionResult, Ctx)
    """
    ctx = Ctx(model=model, take_vars=take_vars, courses_df=courses_df)

    # Build the root requirement
    result = dispatch.contribution(requirement, ctx, "root")

    # Enforce if requested
    if enforce and result.sat_var is not None:
        model.Add(result.sat_var == 1)
    elif enforce and result.sat_var is None:
        raise ValueError(f"Cannot enforce requirement: {'; '.join(result.errors)}")

    return result, ctx


def get_summary(result: ContributionResult) -> ConstraintSummary:
    """Get a summary of all issues encountered during constraint building."""
    return {
        "warning_count": len(result.warnings),
        "error_count": len(result.errors),
        "warnings": result.warnings,
        "errors": result.errors,
        "has_issues": len(result.warnings) > 0 or len(result.errors) > 0,
    }


def print_summary(result: ContributionResult) -> None:
    """Print a summary of issues if any exist."""
    summary = get_summary(result)
    if summary["has_issues"]:
        print("\n=== Constraint Building Summary ===")
        print(f"Warnings: {summary['warning_count']}")
        print(f"Errors: {summary['error_count']}")

        if summary["warnings"]:
            print("\nWarnings:")
            for warning in summary["warnings"]:
                print(f"  - {warning}")

        if summary["errors"]:
            print("\nErrors:")
            for error in summary["errors"]:
                print(f"  - {error}")
        print("=" * 35)


def add_requirement_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    requirement: types.Node,
    courses_df: pl.DataFrame,
    enforce: bool = True,
) -> tuple[dict[str, cp_model.IntVar], dict[str, str], dict[int, set[str]]]:
    """
    Add constraints for a requirement tree to a CP-SAT model.

    This matches the signature of the old requirement_constraint_builder for compatibility.

    Returns:
        Tuple of:
        - Dictionary of auxiliary variables (req_id/title -> sat_var)
        - Dictionary mapping variable names to human-readable debug names
        - Dictionary mapping course indices to sets of requirement paths they satisfy
    """
    result, ctx = build_constraints(
        model=model,
        take_vars=take_vars,
        requirement=requirement,
        courses_df=courses_df,
        enforce=enforce,
    )

    print_summary(result)

    return ctx.aux_vars, ctx.var_name_map, ctx.course_to_requirements
