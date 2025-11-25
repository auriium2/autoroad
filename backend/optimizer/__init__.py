"""
Optimizer module: constraint builders and objective functions.
"""

from .marker_constraint_builder import (
    MarkerConstraintResult,
    add_marker_constraints,
)
from .prerequisite_constraint_builder import (
    ConstraintResult as PrerequisiteConstraintResult,
)
from .prerequisite_constraint_builder import (
    add_prerequisite_constraints,
)
from .requirement_constraint_builder import (
    add_requirement_constraints,
)
from .semesters import ALL_SEMESTERS, REGULAR_SEMESTERS, VALID_SEMESTERS

__all__ = [
    # Semester constants
    "REGULAR_SEMESTERS",
    "VALID_SEMESTERS",
    "ALL_SEMESTERS",
    # Marker constraints
    "add_marker_constraints",
    "MarkerConstraintResult",
    # Prerequisite constraints
    "add_prerequisite_constraints",
    "PrerequisiteConstraintResult",
    # Requirement constraints
    "add_requirement_constraints",
]
