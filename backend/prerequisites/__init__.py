"""
Prerequisites module for parsing and evaluating course prerequisites.

This module provides functionality to:
- Parse Fireroad prerequisite strings into typed structures
- Evaluate whether prerequisites are satisfied
- Convert between different prerequisite formats
"""

from .types import (
    PrereqNode,
    PrereqCourse,
    PrereqGroup,
    PrereqArray,
    EvaluationResult,
)

from .parser import (
    fireroad_to_prereq,
    fireroad_to_courseroad,
    array_to_prereq,
    prereq_to_array,
    is_valid_course_id,
    prereq_to_string,
)

from .evaluator import (
    PrerequisiteEvaluator,
)

__all__ = [
    # Types
    'PrereqNode',
    'PrereqCourse',
    'PrereqGroup',
    'PrereqArray',
    'EvaluationResult',
    # Parser
    'fireroad_to_prereq',
    'fireroad_to_courseroad',
    'array_to_prereq',
    'prereq_to_array',
    'is_valid_course_id',
    'prereq_to_string',
    # Evaluator
    'PrerequisiteEvaluator',
]
