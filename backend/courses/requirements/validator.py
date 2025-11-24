"""
Requirements validator for pruning invalid/unavailable courses.

This module provides functionality to:
- Validate course IDs against the Fireroad course catalog
- Mark invalid courses in requirement trees (mark_invalid_requirements)
- Remove invalid courses from requirement trees (remove_invalid_requirements)
- Report which requirements become infeasible after pruning
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .types import (
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementPlainString,
)


@dataclass
class ValidationResult:
    """Result of validating and marking/pruning a requirement tree."""
    pruned_tree: RequirementNode | None
    removed_courses: list[str]
    warnings: list[str]
    is_feasible: bool


def validate_course_exists(course_id: str, courses_df: Any) -> bool:
    """
    Check if a course exists in the course catalog.

    Args:
        course_id: The course ID to check (e.g., "6.100A", "GIR:CAL1")
        courses_df: DataFrame containing course data with 'subject_id' column

    Returns:
        True if the course exists or is a special requirement, False otherwise
    """
    # Special requirements always "exist"
    if course_id in ["HASS"]:
        return True
    if course_id.startswith("GIR:"):
        return True
    if course_id.startswith("HASS-"):
        return True
    if course_id.startswith("CI-"):
        return True

    # Check if course exists in catalog
    if courses_df is not None and 'subject_id' in courses_df.columns:
        return course_id in courses_df['subject_id'].to_list()

    return False


def mark_invalid_requirements(
    req: RequirementNode,
    courses_df: Any,
    removed_courses: list[str] | None = None,
    warnings: list[str] | None = None
) -> RequirementNode:
    """
    Mark unavailable courses in a requirement tree without removing them.

    Sets was_pruned=True on invalid courses and propagates the flag up to parent groups.
    The tree structure remains intact - all courses are kept for debugging purposes.

    Args:
        req: The requirement node to validate
        courses_df: DataFrame containing valid course data
        removed_courses: List to accumulate invalid course IDs
        warnings: List to accumulate warning messages

    Returns:
        RequirementNode with was_pruned flags set (never returns None)
    """
    if removed_courses is None:
        removed_courses = []
    if warnings is None:
        warnings = []

    # Handle leaf nodes (courses)
    if isinstance(req, RequirementCourse):
        if validate_course_exists(req.course_id, courses_df):
            return req
        else:
            removed_courses.append(req.course_id)
            warnings.append(f"Marked unavailable course: {req.course_id} (ID: {req.req_id})")
            return RequirementCourse(
                course_id=req.course_id,
                title=req.title,
                req_id=req.req_id,
                was_pruned=True
            )

    # Plain strings always remain (they're descriptive, not course-specific)
    if isinstance(req, RequirementPlainString):
        return req

    # Handle group nodes
    if isinstance(req, RequirementGroup):
        # Recursively mark sub-requirements
        marked_items: list[RequirementNode] = []
        valid_children_count = 0

        for item in req.items:
            marked = mark_invalid_requirements(item, courses_df, removed_courses, warnings)
            marked_items.append(marked)
            # Count children that are NOT pruned (i.e., valid/feasible)
            if not (hasattr(marked, 'was_pruned') and marked.was_pruned):
                valid_children_count += 1

        # Determine if this group is infeasible based on connection-type and threshold
        # A group is infeasible if it cannot satisfy its requirements with the valid children
        # NOTE: Both threshold AND connection_type can be present - BOTH must be satisfied
        is_group_infeasible = False
        total_children = len(marked_items)

        # Check threshold requirement (if present)
        if req.threshold:
            # Threshold-based requirement (e.g., "select 3 subjects")
            # For thresholds with criterion='subjects', count total COURSES, not direct children
            required_count = req.threshold.cutoff

            if req.threshold.criterion == 'subjects':
                # Count total valid courses in the subtree
                def count_valid_courses(node):
                    if isinstance(node, RequirementCourse):
                        return 0 if node.was_pruned else 1
                    elif isinstance(node, RequirementGroup):
                        return sum(count_valid_courses(item) for item in node.items)
                    return 0

                available_subjects = count_valid_courses(RequirementGroup(
                    items=tuple(marked_items),
                    connection_type=req.connection_type,
                    threshold=req.threshold,
                    title=req.title,
                    threshold_desc=req.threshold_desc,
                    req_id=req.req_id,
                    was_pruned=False
                ))

                if available_subjects < required_count:
                    is_group_infeasible = True
                    warnings.append(
                        f"Group '{req.title or req.req_id}' is infeasible: "
                        f"threshold requires {required_count} subjects but only {available_subjects} valid courses available"
                    )
            else:
                # For other criteria (e.g., 'units'), count direct children
                if valid_children_count < required_count:
                    is_group_infeasible = True
                    warnings.append(
                        f"Group '{req.title or req.req_id}' is infeasible: "
                        f"threshold requires {required_count} valid items but only {valid_children_count}/{total_children} are valid"
                    )

        # Check connection_type requirement (if present and not already infeasible)
        # Note: We check this separately so both threshold AND connection_type are enforced
        if not is_group_infeasible and req.connection_type == "all":
            # "all" means ALL direct children must be satisfied
            if valid_children_count < total_children:
                is_group_infeasible = True
                warnings.append(
                    f"Group '{req.title or req.req_id}' is infeasible: "
                    f"'all' requires all {total_children} children to be valid but only {valid_children_count} are valid"
                )
        elif not is_group_infeasible and req.connection_type == "any":
            # "any" means at least ONE direct child must be satisfied
            if valid_children_count == 0:
                is_group_infeasible = True
                warnings.append(
                    f"Group '{req.title or req.req_id}' is infeasible: "
                    f"'any' requires at least 1 valid child but all {total_children} are invalid"
                )
        # If connection_type is None, it's likely a container group - not infeasible unless all children are
        elif not is_group_infeasible and req.connection_type is None and not req.threshold:
            if valid_children_count == 0:
                is_group_infeasible = True

        # Return group with correct was_pruned flag
        return RequirementGroup(
            items=tuple(marked_items),
            connection_type=req.connection_type,
            threshold=req.threshold,
            title=req.title,
            threshold_desc=req.threshold_desc,
            req_id=req.req_id,
            was_pruned=is_group_infeasible
        )

    # Unknown node type
    return req


def remove_invalid_requirements(
    req: RequirementNode,
    courses_df: Any,
    removed_courses: list[str] | None = None,
    warnings: list[str] | None = None
) -> RequirementNode | None:
    """
    Remove unavailable courses from a requirement tree.

    This actually removes invalid items, potentially making the tree infeasible.
    Use mark_invalid_requirements() if you want to keep the structure intact.

    Args:
        req: The requirement node to prune
        courses_df: DataFrame containing valid course data
        removed_courses: List to accumulate removed course IDs
        warnings: List to accumulate warning messages

    Returns:
        Pruned requirement node, or None if the entire requirement is infeasible
    """
    if removed_courses is None:
        removed_courses = []
    if warnings is None:
        warnings = []

    # Handle leaf nodes (courses)
    if isinstance(req, RequirementCourse):
        if validate_course_exists(req.course_id, courses_df):
            return req
        else:
            removed_courses.append(req.course_id)
            warnings.append(f"Removed unavailable course: {req.course_id} (ID: {req.req_id})")
            return None

    # Plain strings always remain
    if isinstance(req, RequirementPlainString):
        return req

    # Handle group nodes
    if isinstance(req, RequirementGroup):
        # Recursively prune sub-requirements
        pruned_items: list[RequirementNode] = []
        valid_children_count = 0

        for item in req.items:
            pruned = remove_invalid_requirements(item, courses_df, removed_courses, warnings)
            if pruned is not None:
                pruned_items.append(pruned)
                # Count valid (non-pruned) children
                if not (hasattr(pruned, 'was_pruned') and pruned.was_pruned):
                    valid_children_count += 1

        # Check if group is still feasible based on connection-type and threshold
        # NOTE: Both threshold AND connection_type can be present - BOTH must be satisfied
        original_count = len(req.items)
        remaining_count = len(pruned_items)

        # Determine if group is infeasible
        is_infeasible = False

        # Check threshold requirement (if present)
        if req.threshold:
            # Threshold-based requirement (e.g., "select 3 subjects")
            # For thresholds with criterion='subjects', count total COURSES, not direct children
            cutoff = req.threshold.cutoff

            if req.threshold.criterion == 'subjects':
                # Count total valid courses in the subtree
                def count_valid_courses(node):
                    if isinstance(node, RequirementCourse):
                        return 0 if node.was_pruned else 1
                    elif isinstance(node, RequirementGroup):
                        return sum(count_valid_courses(item) for item in node.items)
                    return 0

                available_subjects = sum(count_valid_courses(item) for item in pruned_items)

                if available_subjects < cutoff:
                    is_infeasible = True
                    warnings.append(
                        f"Group '{req.title or req.req_id}' is infeasible: "
                        f"threshold requires {cutoff} subjects but only {available_subjects} valid courses available"
                    )
            else:
                # For other criteria (e.g., 'units'), count direct children
                if valid_children_count < cutoff:
                    is_infeasible = True
                    warnings.append(
                        f"Group '{req.title or req.req_id}' is infeasible: "
                        f"threshold requires {cutoff} valid items but only {valid_children_count}/{remaining_count} are valid"
                    )

        # Check connection_type requirement (if present and not already infeasible)
        # Note: We check this separately so both threshold AND connection_type are enforced
        if not is_infeasible and req.connection_type == "all":
            # "all" means ALL direct children must be satisfied
            if valid_children_count < remaining_count:
                is_infeasible = True
                warnings.append(
                    f"Group '{req.title or req.req_id}' is infeasible: "
                    f"'all' requires all {remaining_count} children to be valid but only {valid_children_count} are valid"
                )
        elif not is_infeasible and req.connection_type == "any":
            # "any" means at least ONE direct child must be satisfied
            if valid_children_count == 0:
                is_infeasible = True
                warnings.append(
                    f"Group '{req.title or req.req_id}' is infeasible: "
                    f"'any' requires at least 1 valid child but all {remaining_count} are invalid"
                )
        elif not is_infeasible and req.connection_type is None and not req.threshold:
            # No connection type or threshold - infeasible if no children remain
            if remaining_count == 0:
                is_infeasible = True
                warnings.append(
                    f"Group '{req.title or req.req_id}' is infeasible: all {original_count} items were removed"
                )

        if is_infeasible:
            return None

        # Simplify single-item groups
        if remaining_count == 1 and req.threshold is None:
            single_item = pruned_items[0]
            return single_item

        # Return pruned group with was_pruned flag indicating some children were removed/pruned
        some_children_affected = (remaining_count < original_count) or any(
            hasattr(item, 'was_pruned') and item.was_pruned for item in pruned_items
        )

        return RequirementGroup(
            items=tuple(pruned_items),
            connection_type=req.connection_type,
            threshold=req.threshold,
            title=req.title,
            threshold_desc=req.threshold_desc,
            req_id=req.req_id,
            was_pruned=some_children_affected
        )

    return req


def validate_and_prune(
    req: RequirementNode,
    courses_df: Any,
    remove_invalid: bool = False
) -> ValidationResult:
    """
    Validate a requirement tree and either mark or remove invalid courses.

    Args:
        req: The requirement node to validate
        courses_df: DataFrame containing valid course data
        remove_invalid: If True, remove invalid courses. If False, just mark them.

    Returns:
        ValidationResult with pruned tree and metadata
    """
    removed_courses: list[str] = []
    warnings: list[str] = []

    if remove_invalid:
        pruned_tree = remove_invalid_requirements(req, courses_df, removed_courses, warnings)
    else:
        pruned_tree = mark_invalid_requirements(req, courses_df, removed_courses, warnings)

    return ValidationResult(
        pruned_tree=pruned_tree,
        removed_courses=removed_courses,
        warnings=warnings,
        is_feasible=(pruned_tree is not None)
    )
