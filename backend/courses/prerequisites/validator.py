"""
Prerequisites validator for pruning invalid/unavailable courses.

This module provides functionality to:
- Validate course IDs against the Fireroad course catalog
- Mark invalid courses in prerequisite trees (mark_invalid_prerequisites)
- Remove invalid courses from prerequisite trees (remove_invalid_prerequisites)
- Report which prerequisites become infeasible after pruning
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import PrereqCourse, PrereqGroup, PrereqNode


@dataclass
class ValidationResult:
    """Result of validating and marking/pruning a prerequisite tree."""
    pruned_tree: PrereqNode | None
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
    if course_id in ["HASS"]:
        return True
    if course_id.startswith("GIR:"):
        return True
    if course_id.startswith("HASS-"):
        return True
    if course_id.startswith("CI-"):
        return True

    if courses_df is not None and hasattr(courses_df, 'subject_id'):
        return course_id in courses_df['subject_id'].values

    return False


def mark_invalid_prerequisites(
    prereq: PrereqNode,
    courses_df: Any,
    removed_courses: list[str] | None = None,
    warnings: list[str] | None = None
) -> PrereqNode:
    """
    Mark unavailable courses in a prerequisite tree without removing them.

    Sets was_pruned=True on invalid courses and propagates the flag up to parent groups.
    The tree structure remains intact - all courses are kept for debugging purposes.

    Args:
        prereq: The prerequisite node to validate
        courses_df: DataFrame containing valid course data
        removed_courses: List to accumulate invalid course IDs
        warnings: List to accumulate warning messages

    Returns:
        PrereqNode with was_pruned flags set (never returns None)
    """
    if removed_courses is None:
        removed_courses = []
    if warnings is None:
        warnings = []

    if isinstance(prereq, PrereqCourse):
        if validate_course_exists(prereq.course_id, courses_df):
            return prereq
        else:
            removed_courses.append(prereq.course_id)
            warnings.append(f"Marked unavailable course: {prereq.course_id}")
            return PrereqCourse(
                course_id=prereq.course_id,
                was_pruned=True
            )

    if isinstance(prereq, PrereqGroup):
        marked_items: list[PrereqNode] = []
        valid_children_count = 0

        for item in prereq.items:
            marked = mark_invalid_prerequisites(item, courses_df, removed_courses, warnings)
            marked_items.append(marked)
            if not (hasattr(marked, 'was_pruned') and marked.was_pruned):
                valid_children_count += 1

        is_group_infeasible = valid_children_count < prereq.threshold

        if is_group_infeasible:
            warnings.append(
                f"Prerequisite group is infeasible: "
                f"threshold requires {prereq.threshold} valid items but only {valid_children_count}/{len(marked_items)} are valid"
            )

        return PrereqGroup(
            threshold=prereq.threshold,
            items=tuple(marked_items),
            was_pruned=is_group_infeasible
        )

    return prereq


def remove_invalid_prerequisites(
    prereq: PrereqNode,
    courses_df: Any,
    removed_courses: list[str] | None = None,
    warnings: list[str] | None = None
) -> PrereqNode | None:
    """
    Remove unavailable courses from a prerequisite tree.

    This actually removes invalid items, potentially making the tree infeasible.
    Use mark_invalid_prerequisites() if you want to keep the structure intact.

    Args:
        prereq: The prerequisite node to prune
        courses_df: DataFrame containing valid course data
        removed_courses: List to accumulate removed course IDs
        warnings: List to accumulate warning messages

    Returns:
        Pruned prerequisite node, or None if the entire prerequisite is infeasible
    """
    if removed_courses is None:
        removed_courses = []
    if warnings is None:
        warnings = []

    if isinstance(prereq, PrereqCourse):
        if validate_course_exists(prereq.course_id, courses_df):
            return prereq
        else:
            removed_courses.append(prereq.course_id)
            warnings.append(f"Removed unavailable course: {prereq.course_id}")
            return None

    if isinstance(prereq, PrereqGroup):
        pruned_items: list[PrereqNode] = []
        valid_children_count = 0

        for item in prereq.items:
            pruned = remove_invalid_prerequisites(item, courses_df, removed_courses, warnings)
            if pruned is not None:
                pruned_items.append(pruned)
                if not (hasattr(pruned, 'was_pruned') and pruned.was_pruned):
                    valid_children_count += 1

        original_count = len(prereq.items)
        remaining_count = len(pruned_items)

        is_infeasible = valid_children_count < prereq.threshold

        if is_infeasible:
            warnings.append(
                f"Prerequisite group is infeasible: "
                f"threshold requires {prereq.threshold} valid items but only {valid_children_count}/{remaining_count} are valid"
            )
            return None

        if remaining_count == 1:
            return pruned_items[0]

        some_children_affected = (remaining_count < original_count) or any(
            hasattr(item, 'was_pruned') and item.was_pruned for item in pruned_items
        )

        return PrereqGroup(
            threshold=prereq.threshold,
            items=tuple(pruned_items),
            was_pruned=some_children_affected
        )

    return prereq


def validate_and_prune(
    prereq: PrereqNode,
    courses_df: Any,
    remove_invalid: bool = False
) -> ValidationResult:
    """
    Validate a prerequisite tree and either mark or remove invalid courses.

    Args:
        prereq: The prerequisite node to validate
        courses_df: DataFrame containing valid course data
        remove_invalid: If True, remove invalid courses. If False, just mark them.

    Returns:
        ValidationResult with pruned tree and metadata
    """
    removed_courses: list[str] = []
    warnings: list[str] = []

    if remove_invalid:
        pruned_tree = remove_invalid_prerequisites(prereq, courses_df, removed_courses, warnings)
    else:
        pruned_tree = mark_invalid_prerequisites(prereq, courses_df, removed_courses, warnings)

    return ValidationResult(
        pruned_tree=pruned_tree,
        removed_courses=removed_courses,
        warnings=warnings,
        is_feasible=(pruned_tree is not None)
    )
