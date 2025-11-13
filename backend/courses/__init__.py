"""
Course requirements and prerequisites parsing system.

This module provides:
- Requirements: Fireroad major/minor requirement trees (requirements/)
- Prerequisites: Course prerequisite parsing and evaluation (prerequisites/)
"""

# Re-export requirements module
from .requirements import (
    parse_requirement,
    parse_requirement_list,
    requirement_to_string,
    RequirementParseError,
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementPlainString,
    RequirementThreshold,
    mark_invalid_requirements,
    remove_invalid_requirements,
    validate_and_prune,
    validate_course_exists,
    ValidationResult,
)

# Re-export prerequisites module
from .prerequisites import (
    parse_fireroad,
    prereq_to_string,
    is_valid_course_id,
    PrereqCourse,
    PrereqGroup,
    PrereqNode,
    PrerequisiteEvaluator,
    EvaluationResult,
    mark_invalid_prerequisites,
    remove_invalid_prerequisites,
    validate_and_prune as prereq_validate_and_prune,
    validate_course_exists as prereq_validate_course_exists,
    ValidationResult as PrereqValidationResult,
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
