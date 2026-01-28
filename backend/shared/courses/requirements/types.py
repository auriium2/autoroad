"""
Type definitions for req_2 requirement nodes.

These are pure dataclasses representing the requirement tree structure.
Constraint building logic is in optimizer/requirements/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# Literal types for type safety
GIRCode = Literal["CAL1", "CAL2", "PHY1", "PHY2", "CHEM", "BIOL", "REST", "LAB", "LAB2"]
HASSCategory = Literal["HASS", "HASS-A", "HASS-H", "HASS-S", "HASS-E"]
CIType = Literal["CI-H", "CI-HW"]
ThresholdType = Literal["GTE", "LTE"]
ConnectionType = Literal["all", "any"]


@dataclass(frozen=True)
class Course:
    subject_id: str
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class GIR:
    gir_code: GIRCode
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class HASS:
    category: HASSCategory | None = None
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class CI:
    ci_type: CIType
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class PlainString:
    description: str
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class AllGroup:
    children: tuple[Any, ...]
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class AnyGroup:
    children: tuple[Any, ...]
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class DistinctThreshold:
    cutoff: int
    comparison: ThresholdType = "GTE"


@dataclass(frozen=True)
class SubjectThresholdGroup:
    children: tuple[Any, ...]
    cutoff: int
    threshold_type: ThresholdType = "GTE"
    connection_type: ConnectionType = "any"
    distinct_threshold: DistinctThreshold | None = None
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class UnitThresholdGroup:
    children: tuple[Any, ...]
    cutoff: int
    threshold_type: ThresholdType = "GTE"
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class HASSThreshold:
    """Threshold requirement for HASS courses (e.g., "take 8 HASS subjects")."""
    cutoff: int
    category: HASSCategory | None = None  # None or "HASS" = generic (uses pairing)
    threshold_type: ThresholdType = "GTE"
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class CIThreshold:
    """Threshold requirement for CI courses (e.g., "take 2 CI-H courses")."""
    cutoff: int
    ci_type: CIType
    threshold_type: ThresholdType = "GTE"
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


@dataclass(frozen=True)
class GIRThreshold:
    """Threshold requirement for GIR courses (e.g., "take 2 REST subjects")."""
    cutoff: int
    gir_code: GIRCode
    threshold_type: ThresholdType = "GTE"
    title: str | None = None
    req_id: str | None = None
    was_pruned: bool = False


# Type unions
Node = Course | GIR | HASS | CI | PlainString | AllGroup | AnyGroup | SubjectThresholdGroup | UnitThresholdGroup | HASSThreshold | CIThreshold | GIRThreshold
Leaf = Course | GIR | HASS | CI | PlainString
AttributeThreshold = HASSThreshold | CIThreshold | GIRThreshold
Group = AllGroup | AnyGroup | SubjectThresholdGroup | UnitThresholdGroup
