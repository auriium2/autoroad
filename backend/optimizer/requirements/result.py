"""
Result types returned by build queries.

Each query type has a corresponding result type.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ortools.sat.python import cp_model


@dataclass
class SatisfactionResult:
    sat_var: cp_model.IntVar | None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ContributionResult:
    sat_var: cp_model.IntVar | None
    contribution_vars: list[cp_model.IntVar] = field(default_factory=list)
    has_nontrivial_threshold: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CourseIndicesResult:
    indices: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class UnitsResult:
    idx2units: dict[int, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
