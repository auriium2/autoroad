"""
Converter from old RequirementNode types to new req_2 node types.

This allows the existing parser output to be used with the new constraint builder.
"""

from __future__ import annotations

from courses.requirements.req_2 import nodes
from courses.requirements.types import (
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementPlainString,
)


def convert(node: RequirementNode) -> nodes.Node:
    """
    Convert an old RequirementNode to a new req_2 Node.
    
    The old RequirementCourse type encodes GIR, HASS, CI, and regular courses
    all as course_id strings. This function dispatches to the appropriate
    new node type based on the course_id format.
    """
    if isinstance(node, RequirementCourse):
        return _convert_course(node)
    elif isinstance(node, RequirementPlainString):
        return _convert_plain_string(node)
    elif isinstance(node, RequirementGroup):
        return _convert_group(node)
    else:
        raise TypeError(f"Unknown node type: {type(node)}")


def _convert_course(node: RequirementCourse) -> nodes.Node:
    """Convert RequirementCourse to the appropriate leaf node type."""
    course_id = node.course_id

    # GIR: "GIR:CAL1", "GIR:PHY1", etc.
    if course_id.startswith("GIR:"):
        gir_code = course_id.split(":", 1)[1]
        return nodes.GIR(
            gir_code=gir_code,  # type: ignore  # GIRCode literal
            title=node.title,
            req_id=node.req_id,
            was_pruned=node.was_pruned,
        )

    # Generic HASS (any HASS course)
    if course_id == "HASS":
        return nodes.HASS(
            category="HASS",
            title=node.title,
            req_id=node.req_id,
            was_pruned=node.was_pruned,
        )

    # Specific HASS: "HASS-A", "HASS-H", "HASS-S", "HASS-E"
    if course_id.startswith("HASS-"):
        return nodes.HASS(
            category=course_id,  # type: ignore  # HASSCategory literal
            title=node.title,
            req_id=node.req_id,
            was_pruned=node.was_pruned,
        )

    # CI: "CI-H", "CI-HW", "CI-M"
    if course_id.startswith("CI-"):
        return nodes.CI(
            ci_type=course_id,  # type: ignore  # CIType literal
            title=node.title,
            req_id=node.req_id,
            was_pruned=node.was_pruned,
        )

    # Regular course
    return nodes.Course(
        subject_id=course_id,
        title=node.title,
        req_id=node.req_id,
        was_pruned=node.was_pruned,
    )


def _convert_plain_string(node: RequirementPlainString) -> nodes.PlainString:
    """Convert RequirementPlainString to PlainString."""
    return nodes.PlainString(
        description=node.description,
        title=node.title,
        req_id=node.req_id,
        was_pruned=node.was_pruned,
    )


def _convert_group(node: RequirementGroup) -> nodes.Node:
    """
    Convert RequirementGroup to the appropriate group node type.
    
    The old design uses a single RequirementGroup type with optional threshold.
    The new design has separate types:
    - AllGroup: connection_type='all', no threshold
    - AnyGroup: connection_type='any', no threshold
    - SubjectThresholdGroup: has threshold with criterion='subjects'
    - UnitThresholdGroup: has threshold with criterion='units'
    """
    # Convert children first
    children = tuple(convert(child) for child in node.items)

    # If there's a threshold, use the appropriate threshold group
    if node.threshold is not None:
        if node.threshold.criterion == "units":
            return nodes.UnitThresholdGroup(
                children=children,
                cutoff=node.threshold.cutoff,
                threshold_type=node.threshold.type,  # type: ignore  # ThresholdType literal
                title=node.title,
                req_id=node.req_id,
                was_pruned=node.was_pruned,
            )
        else:  # criterion == "subjects"
            distinct_threshold = None
            if node.distinct_threshold is not None:
                distinct_threshold = nodes.DistinctThreshold(
                    cutoff=node.distinct_threshold.cutoff,
                    comparison=node.distinct_threshold.type,  # type: ignore
                )

            return nodes.SubjectThresholdGroup(
                children=children,
                cutoff=node.threshold.cutoff,
                threshold_type=node.threshold.type,  # type: ignore
                connection_type=node.connection_type or "any",  # type: ignore
                distinct_threshold=distinct_threshold,
                title=node.title,
                req_id=node.req_id,
                was_pruned=node.was_pruned,
            )

    # No threshold - use AllGroup or AnyGroup based on connection_type
    if node.connection_type == "any":
        return nodes.AnyGroup(
            children=children,
            title=node.title,
            req_id=node.req_id,
            was_pruned=node.was_pruned,
        )
    else:  # "all" or None (default to all)
        return nodes.AllGroup(
            children=children,
            title=node.title,
            req_id=node.req_id,
            was_pruned=node.was_pruned,
        )
