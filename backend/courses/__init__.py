"""
Course requirements and prerequisites parsing system.

This module provides:
- Requirements: Fireroad major/minor requirement trees (requirements/)
- Prerequisites: Course prerequisite parsing and evaluation (prerequisites/)
"""

# Re-export requirements module
# Re-export prerequisites module
from .prerequisites import (
    EvaluationResult,
    PrereqCourse,
    PrereqGroup,
    PrereqNode,
    PrerequisiteEvaluator,
    is_valid_course_id,
    mark_invalid_prerequisites,
    parse_fireroad,
    prereq_to_string,
    remove_invalid_prerequisites,
)
from .prerequisites import (
    ValidationResult as PrereqValidationResult,
)
from .prerequisites import (
    validate_and_prune as prereq_validate_and_prune,
)
from .prerequisites import (
    validate_course_exists as prereq_validate_course_exists,
)
from .requirements import (
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementParseError,
    RequirementPlainString,
    RequirementThreshold,
    ValidationResult,
    mark_invalid_requirements,
    parse_requirement,
    parse_requirement_list,
    remove_invalid_requirements,
    requirement_to_string,
    validate_and_prune,
    validate_course_exists,
)

__all__ = [
    # Requirements
    "parse_requirement",
    "parse_requirement_list",
    "requirement_to_string",
    "RequirementParseError",
    "RequirementCourse",
    "RequirementGroup",
    "RequirementNode",
    "RequirementPlainString",
    "RequirementThreshold",
    "mark_invalid_requirements",
    "remove_invalid_requirements",
    "validate_and_prune",
    "validate_course_exists",
    "ValidationResult",
    # Prerequisites
    "parse_fireroad",
    "prereq_to_string",
    "is_valid_course_id",
    "PrereqCourse",
    "PrereqGroup",
    "PrereqNode",
    "PrerequisiteEvaluator",
    "EvaluationResult",
    "mark_invalid_prerequisites",
    "remove_invalid_prerequisites",
    "prereq_validate_and_prune",
    "prereq_validate_course_exists",
    "PrereqValidationResult",
]
