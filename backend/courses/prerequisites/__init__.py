"""
Prerequisites module for parsing and evaluating course prerequisites.

This module provides functionality to:
- Parse Fireroad prerequisite strings into typed structures
- Evaluate whether prerequisites are satisfied
- Validate and prune invalid courses
"""

from .evaluator import (
    PrerequisiteEvaluator,
)
from .parser import (
    is_valid_course_id,
    parse_fireroad,
    prereq_to_string,
)
from .types import (
    EvaluationResult,
    PrereqCourse,
    PrereqGroup,
    PrereqNode,
)
from .validator import (
    ValidationResult,
    mark_invalid_prerequisites,
    remove_invalid_prerequisites,
    validate_and_prune,
    validate_course_exists,
)

__all__ = [
    # Types
    'PrereqNode',
    'PrereqCourse',
    'PrereqGroup',
    'EvaluationResult',
    # Parser
    'parse_fireroad',
    'is_valid_course_id',
    'prereq_to_string',
    # Evaluator
    'PrerequisiteEvaluator',
    # Validator
    'mark_invalid_prerequisites',
    'remove_invalid_prerequisites',
    'validate_and_prune',
    'validate_course_exists',
    'ValidationResult',
]
