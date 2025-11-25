"""
Type definitions for Fireroad requirements tree structure.

Fireroad requirements have a hierarchical structure:
- Leaf nodes: {'req': 'course_code', 'title': '...'} or {'req': 'SPECIAL_REQ'}
- Branch nodes: {'reqs': [...], 'connection-type': 'all'|'any', 'threshold': {...}, 'title': '...'}

Connection types:
- 'all': All sub-requirements must be satisfied (AND)
- 'any': At least one sub-requirement must be satisfied (OR)

Threshold format:
- {'cutoff': N, 'criterion': 'subjects'|'units', 'type': 'GTE'|'LTE'}
- Specifies how many sub-requirements need to be satisfied

Special requirements:
- Course codes: "6.100A", "18.01", etc.
- GIRs: "GIR:CAL1", "GIR:PHY1", etc.
- HASS: "HASS", "HASS-A", "HASS-H", etc.
- Communication: "CI-H", "CI-HW"
- Plain strings: {'plain-string': 'description', 'title': '...'}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True)
class RequirementCourse:
    """
    A leaf requirement representing a single course or special requirement.

    Examples:
    - Course: RequirementCourse(course_id="6.100A")
    - GIR: RequirementCourse(course_id="GIR:CAL1")
    - HASS: RequirementCourse(course_id="HASS-A")
    """
    course_id: str
    title: str | None = None
    req_id: str | None = None  # Unique identifier for constraint naming
    was_pruned: bool = False  # Set to True if this or descendants were removed during validation


@dataclass(frozen=True)
class RequirementPlainString:
    """
    A leaf requirement that's descriptive text rather than a parseable course ID.

    This is used for requirements that cannot be encoded as simple course IDs,
    like "2 math subjects (first decimal ≥ 1)" or "72 units of unrestricted electives".

    The plain-string flag in the API indicates the req field is human-readable text
    rather than a course code to validate against.

    Example: RequirementPlainString(description="2 math subjects (first decimal ≥ 1)")
    """
    description: str
    title: str | None = None
    threshold: RequirementThreshold | None = None
    req_id: str | None = None  # Unique identifier for constraint naming
    was_pruned: bool = False  # Set to True if this or descendants were removed during validation


@dataclass(frozen=True)
class RequirementThreshold:
    """
    Threshold specification for how many sub-requirements must be satisfied.

    Examples:
    - RequirementThreshold(cutoff=2, criterion="subjects", type="GTE")
      means "at least 2 subjects"
    - RequirementThreshold(cutoff=12, criterion="units", type="GTE")
      means "at least 12 units"
    """
    cutoff: int
    criterion: Literal["subjects", "units"]
    type: Literal["GTE", "LTE"]


@dataclass(frozen=True)
class RequirementGroup:
    """
    A branch requirement containing sub-requirements.

    Attributes:
    - items: List of sub-requirements (can be courses or groups)
    - connection_type: 'all' (AND) or 'any' (OR)
    - threshold: Optional threshold specification
    - distinct_threshold: Optional threshold for distinct categories (e.g., "from at least 3 categories")
    - title: Optional descriptive title
    - threshold_desc: Optional human-readable threshold description
    - req_id: Unique identifier for constraint naming
    - was_pruned: True if any items were removed during validation

    Examples:
    - All courses required:
      RequirementGroup(items=[...], connection_type="all")

    - Any course required:
      RequirementGroup(items=[...], connection_type="any")

    - At least 2 of 5 courses:
      RequirementGroup(
          items=[...],
          connection_type="any",
          threshold=RequirementThreshold(cutoff=2, criterion="subjects", type="GTE")
      )

    - At least 4 subjects from at least 3 categories:
      RequirementGroup(
          items=[...],
          connection_type="any",
          threshold=RequirementThreshold(cutoff=4, criterion="subjects", type="GTE"),
          distinct_threshold=RequirementThreshold(cutoff=3, criterion="subjects", type="GTE")
      )
    """
    items: tuple[RequirementNode, ...]
    connection_type: Literal["all", "any"] | None = None
    threshold: RequirementThreshold | None = None
    distinct_threshold: RequirementThreshold | None = None
    title: str | None = None
    threshold_desc: str | None = None
    req_id: str | None = None  # Unique identifier for constraint naming
    was_pruned: bool = False  # Set to True if this or descendants were removed during validation

    def __post_init__(self):
        # Validate that items is a tuple
        if not isinstance(self.items, tuple):
            raise TypeError(f"items must be a tuple, got {type(self.items)}")


# Union type for any requirement node
RequirementNode = Union[RequirementCourse, RequirementPlainString, RequirementGroup]
