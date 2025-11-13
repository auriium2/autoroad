"""
Requirements module for parsing Fireroad requirement trees.

This module provides functionality to:
- Parse Fireroad requirement JSON structures into typed trees
- Validate and analyze requirement structures
- Prune invalid/unavailable courses from requirements
"""

from .parser import (
    RequirementParseError,
    parse_requirement,
    parse_requirement_list,
    requirement_to_string,
)
from .types import (
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementPlainString,
    RequirementThreshold,
)
from .validator import (
    ValidationResult,
    mark_invalid_requirements,
    remove_invalid_requirements,
    validate_and_prune,
    validate_course_exists,
)

__all__ = [
    # Types
    'RequirementNode',
    'RequirementCourse',
    'RequirementPlainString',
    'RequirementGroup',
    'RequirementThreshold',
    # Parser
    'parse_requirement',
    'parse_requirement_list',
    'requirement_to_string',
    'RequirementParseError',
    # Validator
    'validate_course_exists',
    'mark_invalid_requirements',
    'remove_invalid_requirements',
    'validate_and_prune',
    'ValidationResult',
]
