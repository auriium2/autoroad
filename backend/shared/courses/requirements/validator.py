"""
Validator for req_2 requirement nodes.

Validates courses against the catalog and marks/removes invalid courses.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from shared.courses.requirements.types import (
    CI,
    GIR,
    HASS,
    AllGroup,
    AnyGroup,
    Course,
    Group,
    Node,
    PlainString,
    SubjectThresholdGroup,
    UnitThresholdGroup,
)


@dataclass
class ValidationResult:
    """Result of validating and pruning a requirement tree."""
    pruned_tree: Node | None
    removed_courses: list[str]
    warnings: list[str]
    is_feasible: bool


def validate_course_exists(node: Node, courses_df: Any) -> bool:
    """
    Check if a course/requirement node is satisfiable.

    Special requirements (GIR, HASS, CI) always return True.
    Regular courses are checked against the catalog.
    """
    if isinstance(node, GIR):
        return True
    if isinstance(node, HASS):
        return True
    if isinstance(node, CI):
        return True
    if isinstance(node, PlainString):
        return True  # Plain strings don't need validation
    if isinstance(node, Course):
        if courses_df is not None and 'subject_id' in courses_df.columns:
            return node.subject_id in courses_df['subject_id'].to_list()
        return False
    # Groups are validated by their children
    return True


def _mark_node(
    node: Node,
    courses_df: Any,
    removed_courses: list[str],
    warnings: list[str],
) -> Node:
    """Mark invalid courses in a node without removing them."""

    # Leaf nodes
    if isinstance(node, Course):
        if validate_course_exists(node, courses_df):
            return node
        removed_courses.append(node.subject_id)
        warnings.append(f"Marked unavailable course: {node.subject_id} (ID: {node.req_id})")
        return replace(node, was_pruned=True)

    if isinstance(node, (GIR, HASS, CI, PlainString)):
        # These are always valid
        return node

    # Group nodes
    if isinstance(node, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
        marked_children = tuple(
            _mark_node(child, courses_df, removed_courses, warnings)
            for child in node.children
        )

        valid_count = sum(1 for c in marked_children if not c.was_pruned)
        total_count = len(marked_children)

        is_infeasible = _check_group_feasibility(
            node, marked_children, valid_count, total_count, courses_df, warnings
        )

        if isinstance(node, AllGroup):
            return AllGroup(
                children=marked_children,
                title=node.title,
                req_id=node.req_id,
                was_pruned=is_infeasible,
            )
        elif isinstance(node, AnyGroup):
            return AnyGroup(
                children=marked_children,
                title=node.title,
                req_id=node.req_id,
                was_pruned=is_infeasible,
            )
        elif isinstance(node, SubjectThresholdGroup):
            return SubjectThresholdGroup(
                children=marked_children,
                cutoff=node.cutoff,
                threshold_type=node.threshold_type,
                connection_type=node.connection_type,
                distinct_threshold=node.distinct_threshold,
                title=node.title,
                req_id=node.req_id,
                was_pruned=is_infeasible,
            )
        elif isinstance(node, UnitThresholdGroup):
            return UnitThresholdGroup(
                children=marked_children,
                cutoff=node.cutoff,
                threshold_type=node.threshold_type,
                title=node.title,
                req_id=node.req_id,
                was_pruned=is_infeasible,
            )

    return node


def _remove_node(
    node: Node,
    courses_df: Any,
    removed_courses: list[str],
    warnings: list[str],
) -> Node | None:
    """Remove invalid courses from a node."""

    # Leaf nodes
    if isinstance(node, Course):
        if validate_course_exists(node, courses_df):
            return node
        removed_courses.append(node.subject_id)
        warnings.append(f"Removed unavailable course: {node.subject_id} (ID: {node.req_id})")
        return None

    if isinstance(node, (GIR, HASS, CI, PlainString)):
        return node

    # Group nodes
    if isinstance(node, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
        pruned_children: list[Node] = []
        for child in node.children:
            pruned = _remove_node(child, courses_df, removed_courses, warnings)
            if pruned is not None:
                pruned_children.append(pruned)

        valid_count = sum(1 for c in pruned_children if not c.was_pruned)
        total_count = len(pruned_children)

        is_infeasible = _check_group_feasibility(
            node, tuple(pruned_children), valid_count, total_count, courses_df, warnings
        )

        if is_infeasible:
            return None

        # Simplify single-item groups (only for non-threshold groups)
        if len(pruned_children) == 1 and isinstance(node, (AllGroup, AnyGroup)):
            return pruned_children[0]

        children_tuple = tuple(pruned_children)

        if isinstance(node, AllGroup):
            return AllGroup(
                children=children_tuple,
                title=node.title,
                req_id=node.req_id,
                was_pruned=False,
            )
        elif isinstance(node, AnyGroup):
            return AnyGroup(
                children=children_tuple,
                title=node.title,
                req_id=node.req_id,
                was_pruned=False,
            )
        elif isinstance(node, SubjectThresholdGroup):
            return SubjectThresholdGroup(
                children=children_tuple,
                cutoff=node.cutoff,
                threshold_type=node.threshold_type,
                connection_type=node.connection_type,
                distinct_threshold=node.distinct_threshold,
                title=node.title,
                req_id=node.req_id,
                was_pruned=False,
            )
        elif isinstance(node, UnitThresholdGroup):
            return UnitThresholdGroup(
                children=children_tuple,
                cutoff=node.cutoff,
                threshold_type=node.threshold_type,
                title=node.title,
                req_id=node.req_id,
                was_pruned=False,
            )

    return node


def _check_group_feasibility(
    node: Group,
    children: tuple[Node, ...],
    valid_count: int,
    total_count: int,
    courses_df: Any,
    warnings: list[str],
) -> bool:
    """Check if a group is feasible. Returns True if infeasible."""

    if isinstance(node, AllGroup):
        # All children must be valid
        if valid_count < total_count:
            warnings.append(
                f"Group '{node.title or node.req_id}' is infeasible: "
                f"'all' requires all {total_count} children but only {valid_count} are valid"
            )
            return True
        return False

    elif isinstance(node, AnyGroup):
        # At least one child must be valid
        if valid_count == 0:
            warnings.append(
                f"Group '{node.title or node.req_id}' is infeasible: "
                f"'any' requires at least 1 valid child but all are invalid"
            )
            return True
        return False

    elif isinstance(node, SubjectThresholdGroup):
        # Count total valid courses in subtree
        available = _count_valid_courses(children)
        if available < node.cutoff:
            warnings.append(
                f"Group '{node.title or node.req_id}' is infeasible: "
                f"requires {node.cutoff} subjects but only {available} valid courses available"
            )
            return True
        return False

    elif isinstance(node, UnitThresholdGroup):
        # Count total available units
        available_units = _count_available_units(children, courses_df)
        if available_units < node.cutoff:
            # Not enough units - but this might be an open-ended elective group
            # Don't mark as infeasible, just warn
            warnings.append(
                f"Group '{node.title or node.req_id}' is open-ended: "
                f"requires {node.cutoff} units but only {available_units} units available from listed courses"
            )
        return False

    return False


def _count_valid_courses(children: tuple[Node, ...]) -> int:
    """
    Count valid (non-pruned) courses in a subtree.

    """
    count = 0
    for child in children:
        if isinstance(child, Course):
            if not child.was_pruned:
                count += 1
        elif isinstance(child, (GIR, HASS, CI)):
            # nuclear bomb tier hack
            if not child.was_pruned:
                count += 1000  # Large number to indicate "effectively unlimited"
        elif isinstance(child, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
            count += _count_valid_courses(child.children)
    return count


def _count_available_units(children: tuple[Node, ...], courses_df: Any) -> int:
    """
    Count available units from valid courses in a subtree.
    
    Special nodes (GIR, HASS, CI) represent categories that can match
    many courses, so we return a large number to indicate "satisfiable".
    """
    total = 0
    for child in children:
        if isinstance(child, Course):
            if not child.was_pruned:
                if courses_df is not None and 'subject_id' in courses_df.columns:
                    matches = courses_df.filter(courses_df['subject_id'] == child.subject_id)
                    if len(matches) > 0 and 'total_units' in courses_df.columns:
                        units = matches[0, 'total_units']
                        total += int(units) if units is not None else 12
                    else:
                        total += 12
                else:
                    total += 12
        elif isinstance(child, (GIR, HASS, CI)):
            # These are wildcards that match many courses - always satisfiable
            if not child.was_pruned:
                total += 10000  # Large number to indicate "effectively unlimited"
        elif isinstance(child, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
            total += _count_available_units(child.children, courses_df)
    return total


def validate_and_prune(
    node: Node,
    courses_df: Any,
    remove_invalid: bool = False,
) -> ValidationResult:
    """
    Validate a requirement tree and either mark or remove invalid courses.

    Args:
        node: The requirement node to validate
        courses_df: DataFrame containing valid course data
        remove_invalid: If True, remove invalid courses. If False, just mark them.

    Returns:
        ValidationResult with pruned tree and metadata
    """
    removed_courses: list[str] = []
    warnings: list[str] = []

    if remove_invalid:
        pruned_tree = _remove_node(node, courses_df, removed_courses, warnings)
    else:
        pruned_tree = _mark_node(node, courses_df, removed_courses, warnings)

    return ValidationResult(
        pruned_tree=pruned_tree,
        removed_courses=removed_courses,
        warnings=warnings,
        is_feasible=(pruned_tree is not None),
    )
