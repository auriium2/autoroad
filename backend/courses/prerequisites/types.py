"""
Type definitions for prerequisite system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

@dataclass(frozen=True)
class PrereqCourse:
    """A single course prerequisite."""
    course_id: str
    was_pruned: bool = False


@dataclass(frozen=True)
class PrereqGroup:
    """
    A group of prerequisites with a threshold.

    Examples:
    - threshold=0 (or len(items)): ALL items required (AND)
    - threshold=1: ONE item required (OR)
    - threshold=2: TWO items required (2 of N)
    """
    threshold: int
    items: tuple[PrereqNode, ...]
    was_pruned: bool = False

    def __post_init__(self):
        # Convert threshold=0 to "all items" for convenience
        if self.threshold == 0:
            object.__setattr__(self, 'threshold', len(self.items))


# A prerequisite node is either a course or a group
PrereqNode = Union[PrereqCourse, PrereqGroup]




@dataclass
class EvaluationResult:
    """Result of evaluating a prerequisite requirement."""
    satisfied: bool
    unsatisfied_reasons: list[str] = field(default_factory=list)
    matched_courses: list[str] = field(default_factory=list)
