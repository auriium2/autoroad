"""
Requirements Parser for Fireroad Format

This parser converts Fireroad requirements JSON structure to typed RequirementNode trees.

Fireroad requirements structure:
- Leaf: {'req': 'COURSE_ID', 'title': '...'} or {'plain-string': 'text', 'title': '...'}
- Branch: {'reqs': [...], 'connection-type': 'all'|'any', 'threshold': {...}, 'title': '...'}

Examples:
- Single course: {"req": "6.100A"}
- All required: {"connection-type": "all", "reqs": [{"req": "6.100A"}, {"req": "6.1200"}]}
- Any required: {"connection-type": "any", "reqs": [{"req": "18.05"}, {"req": "18.06"}]}
- Threshold: {"connection-type": "any", "threshold": {"cutoff": 2, "criterion": "subjects", "type": "GTE"}, "reqs": [...]}
"""

from __future__ import annotations

import re
from typing import Any

from .types import (
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementPlainString,
    RequirementThreshold,
)


class RequirementParseError(Exception):
    """Raised when a requirement structure cannot be parsed."""
    pass


def _slugify(text: str) -> str:
    """
    Convert a title to a slug suitable for IDs.

    Examples:
        "Programming Skills" -> "programming_skills"
        "6-3 Math" -> "6_3_math"
        "Centers and (Application_CIM or AI+D_AUS)" -> "centers_and_application_cim_or_aid_aus"
    """
    # Convert to lowercase
    text = text.lower()
    # Replace special characters and spaces with underscores
    text = re.sub(r'[^\w\s-]', '_', text)
    # Replace multiple spaces/underscores with single underscore
    text = re.sub(r'[\s_]+', '_', text)
    # Remove leading/trailing underscores
    text = text.strip('_')
    return text


def parse_requirement(req_item: dict[str, Any], parent_id: str = "", counter: dict[str, int] | None = None) -> RequirementNode:
    """
    Parse a Fireroad requirement item into a RequirementNode.

    Args:
        req_item: Dictionary from Fireroad API (either a leaf or branch node)
        parent_id: ID path of parent requirement (for generating unique IDs)
        counter: Counter dict for tracking unnamed groups (shared across recursive calls)

    Returns:
        RequirementNode: Parsed requirement tree

    Raises:
        RequirementParseError: If the requirement structure is invalid

    Examples:
        >>> parse_requirement({"req": "6.100A"})
        RequirementCourse(course_id='6.100A', title=None)

        >>> parse_requirement({"plain-string": "Permission required", "title": "Permission"})
        RequirementPlainString(text='Permission required', title='Permission')

        >>> parse_requirement({
        ...     "connection-type": "any",
        ...     "reqs": [{"req": "6.100A"}, {"req": "6.100L"}]
        ... })
        RequirementGroup(items=(...), connection_type='any', ...)
    """
    # Initialize counter if not provided
    if counter is None:
        counter = {}

    # Check for course/special requirement leaf
    # Note: plain-string is a boolean flag, not a separate field
    if 'req' in req_item and 'reqs' not in req_item:
        # Check if this is a plain-string (human-readable description) or a course ID
        is_plain_string = req_item.get('plain-string', False)

        # Generate ID for this leaf
        title = req_item.get('title')
        if title:
            leaf_id = f"{parent_id}/{_slugify(title)}" if parent_id else _slugify(title)
        else:
            # Use course ID or description as fallback
            course_id = req_item['req']
            leaf_slug = _slugify(course_id) if len(course_id) < 50 else _slugify(course_id[:50])
            leaf_id = f"{parent_id}/{leaf_slug}" if parent_id else leaf_slug

        if is_plain_string:
            # Parse threshold if present for plain-string requirements
            threshold = None
            if 'threshold' in req_item:
                threshold_dict = req_item['threshold']
                try:
                    threshold = RequirementThreshold(
                        cutoff=int(threshold_dict['cutoff']),
                        criterion=threshold_dict['criterion'],
                        type=threshold_dict['type']
                    )
                except (KeyError, ValueError, TypeError) as e:
                    raise RequirementParseError(f"Invalid threshold in plain-string: {e}") from e

            return RequirementPlainString(
                description=req_item['req'],
                title=req_item.get('title'),
                threshold=threshold,
                req_id=leaf_id
            )

        # Regular course ID
        return RequirementCourse(
            course_id=req_item['req'],
            title=req_item.get('title'),
            req_id=leaf_id
        )

    # Must be a branch node with 'reqs'
    if 'reqs' not in req_item:
        raise RequirementParseError(
            f"Requirement item must have 'req', 'plain-string', or 'reqs' field. Got: {req_item.keys()}"
        )

    # Generate ID for this group
    title = req_item.get('title')
    connection_type = req_item.get('connection-type')

    if title:
        # Use title as base for ID
        group_slug = _slugify(title)
        group_id = f"{parent_id}/{group_slug}" if parent_id else group_slug
    else:
        # No title, generate based on connection type and counter
        conn_type = connection_type or 'group'
        counter_key = f"{parent_id}/{conn_type}" if parent_id else conn_type
        counter[counter_key] = counter.get(counter_key, 0) + 1
        group_id = f"{parent_id}/{conn_type}{counter[counter_key]}" if parent_id else f"{conn_type}{counter[counter_key]}"

    # Parse sub-requirements recursively
    sub_reqs = req_item['reqs']
    if not isinstance(sub_reqs, list):
        raise RequirementParseError(f"'reqs' must be a list, got {type(sub_reqs)}")

    parsed_items: list[RequirementNode] = []
    for i, sub_req in enumerate(sub_reqs):
        try:
            parsed_items.append(parse_requirement(sub_req, parent_id=group_id, counter=counter))
        except RequirementParseError as e:
            raise RequirementParseError(f"Error parsing sub-requirement {i}: {e}") from e

    # Parse threshold if present
    threshold = None
    if 'threshold' in req_item:
        threshold_dict = req_item['threshold']
        if not isinstance(threshold_dict, dict):
            raise RequirementParseError(f"'threshold' must be a dict, got {type(threshold_dict)}")

        try:
            threshold = RequirementThreshold(
                cutoff=int(threshold_dict['cutoff']),
                criterion=threshold_dict['criterion'],
                type=threshold_dict['type']
            )
        except KeyError as e:
            raise RequirementParseError(f"Threshold missing required field: {e}") from e
        except (ValueError, TypeError) as e:
            raise RequirementParseError(f"Invalid threshold value: {e}") from e
    # elif connection_type is None and len(parsed_items) > 0 and parent_id == "":
    #     # Special case: Root wrapper group with no connection-type and no threshold
    #     # This handles the case where parse_requirement({'reqs': [...]}) creates a wrapper
    #     # Default to requiring all children (like connection-type='all')
    #     threshold = RequirementThreshold(
    #         cutoff=len(parsed_items),
    #         criterion='subjects',
    #         type='EQ'
    #     )

    # Validate connection type
    if connection_type is not None and connection_type not in ['all', 'any']:
        raise RequirementParseError(
            f"connection-type must be 'all' or 'any', got '{connection_type}'"
        )

    return RequirementGroup(
        items=tuple(parsed_items),
        connection_type=connection_type,
        threshold=threshold,
        title=req_item.get('title'),
        threshold_desc=req_item.get('threshold-desc'),
        req_id=group_id
    )


def parse_requirement_list(reqs: list[dict[str, Any]]) -> list[RequirementNode]:
    """
    Parse a list of requirements (top-level 'reqs' field from Fireroad).

    Args:
        reqs: List of requirement dictionaries

    Returns:
        List of parsed RequirementNode objects

    Raises:
        RequirementParseError: If any requirement cannot be parsed
    """
    if not isinstance(reqs, list):
        raise RequirementParseError(f"Requirements must be a list, got {type(reqs)}")

    result: list[RequirementNode] = []
    for i, req_item in enumerate(reqs):
        try:
            result.append(parse_requirement(req_item))
        except RequirementParseError as e:
            raise RequirementParseError(f"Error parsing requirement {i}: {e}") from e

    return result


def requirement_to_string(req: RequirementNode, indent: int = 0, show_ids: bool = False) -> str:
    """
    Convert a RequirementNode to a human-readable string representation.

    Args:
        req: The requirement node to convert
        indent: Indentation level for nested requirements
        show_ids: Whether to show req_id in output

    Returns:
        Human-readable string representation
    """
    prefix = "  " * indent

    if isinstance(req, RequirementCourse):
        title_part = f" ({req.title})" if req.title else ""
        id_part = f" [ID: {req.req_id}]" if show_ids and req.req_id else ""
        pruned_mark = " ⚠️ PRUNED" if req.was_pruned else ""
        return f"{prefix}{req.course_id}{title_part}{id_part}{pruned_mark}"

    if isinstance(req, RequirementPlainString):
        title_part = f" ({req.title})" if req.title else ""
        threshold_part = ""
        if req.threshold:
            threshold_part = f" [{req.threshold.type} {req.threshold.cutoff} {req.threshold.criterion}]"
        id_part = f" [ID: {req.req_id}]" if show_ids and req.req_id else ""
        pruned_mark = " ⚠️ PRUNED" if req.was_pruned else ""
        return f"{prefix}[Plain String: {req.description}]{threshold_part}{title_part}{id_part}{pruned_mark}"

    if isinstance(req, RequirementGroup):
        lines = []

        # Build header
        header_parts = []
        if req.title:
            header_parts.append(req.title)

        if req.threshold:
            threshold_str = f"{req.threshold.type} {req.threshold.cutoff} {req.threshold.criterion}"
            header_parts.append(threshold_str)
        elif req.connection_type:
            header_parts.append(req.connection_type.upper())

        if req.threshold_desc:
            header_parts.append(f"({req.threshold_desc})")

        id_part = f" [ID: {req.req_id}]" if show_ids and req.req_id else ""
        pruned_mark = " ⚠️ PRUNED" if req.was_pruned else ""
        header = f"{prefix}[{' - '.join(header_parts) if header_parts else 'Group'}]{id_part}{pruned_mark}"
        lines.append(header)

        # Add sub-requirements
        for item in req.items:
            lines.append(requirement_to_string(item, indent + 1, show_ids=show_ids))

        return '\n'.join(lines)

    return f"{prefix}[Unknown requirement type: {type(req)}]"
