"""
Parser for Fireroad requirement JSON into req_2 types.

This parser converts Fireroad requirements JSON directly into the typed req_2 node types,
bypassing the old RequirementNode intermediate representation.

Fireroad structure:
- Leaf course: {"req": "6.100A", "title": "..."}
- Plain-string: {"req": "description text", "plain-string": true, "title": "..."}
- Group: {"reqs": [...], "connection-type": "all"|"any", "threshold": {...}, "title": "..."}

Special course IDs:
- GIR codes: "GIR:CAL1", "GIR:PHY1", etc.
- HASS: "HASS", "HASS-A", "HASS-H", "HASS-S", "HASS-E"
- CI: "CI-H", "CI-HW"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from courses.requirements.req_2.types import (
    CI,
    GIR,
    HASS,
    AllGroup,
    AnyGroup,
    ConnectionType,
    Course,
    DistinctThreshold,
    Node,
    PlainString,
    SubjectThresholdGroup,
    ThresholdType,
    UnitThresholdGroup,
)


class ParseError(Exception):
    """Raised when requirement JSON cannot be parsed."""
    pass


@dataclass
class ParseResult:
    """Result of parsing a requirement."""
    node: Node
    warnings: list[str]


def _slugify(text: str) -> str:
    """Convert a title to a slug suitable for IDs."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '_', text)
    text = re.sub(r'[\s_]+', '_', text)
    text = text.strip('_')
    return text


def _make_id(
    title: str | None,
    fallback: str,
    parent_id: str,
    counter: dict[str, int],
) -> str:
    """
    Generate a unique ID for a node.

    Uses a counter to ensure uniqueness when multiple nodes have the same slug.
    """
    if title:
        slug = _slugify(title)
    else:
        slug = _slugify(fallback) if len(fallback) < 50 else _slugify(fallback[:50])

    # Handle empty slug (e.g., if text was only punctuation)
    if not slug:
        slug = "item"

    base_id = f"{parent_id}/{slug}" if parent_id else slug

    # Track occurrences to ensure uniqueness
    counter_key = f"leaf:{base_id}"
    count = counter.get(counter_key, 0)
    counter[counter_key] = count + 1

    if count == 0:
        return base_id
    return f"{base_id}_{count}"


def _parse_leaf(course_id: str, title: str | None, req_id: str) -> Node:
    """
    Parse a leaf node (course, GIR, HASS, CI, etc.) from a course_id string.

    Handles special course ID formats:
    - "GIR:CAL1", "GIR:PHY1", etc. -> GIR node
    - "HASS", "HASS-A", "HASS-H", "HASS-S", "HASS-E" -> HASS node
    - "CI-H", "CI-HW" -> CI node
    - Regular course IDs -> Course node
    """
    # GIR codes
    if course_id.startswith("GIR:"):
        gir_code = course_id.split(":", 1)[1]
        valid_girs: set[str] = {"CAL1", "CAL2", "PHY1", "PHY2", "CHEM", "BIOL", "REST", "LAB", "LAB2"}
        if gir_code not in valid_girs:
            # Return as plain string if unknown GIR
            return PlainString(description=course_id, title=title, req_id=req_id)
        return GIR(gir_code=gir_code, title=title, req_id=req_id)  # type: ignore

    # Generic HASS
    if course_id == "HASS":
        return HASS(category="HASS", title=title, req_id=req_id)

    # Specific HASS categories
    if course_id in ("HASS-A", "HASS-H", "HASS-S", "HASS-E"):
        return HASS(category=course_id, title=title, req_id=req_id)  # type: ignore

    # CI requirements
    if course_id in ("CI-H", "CI-HW"):
        return CI(ci_type=course_id, title=title, req_id=req_id)  # type: ignore

    # Regular course
    return Course(subject_id=course_id, title=title, req_id=req_id)


def _parse_threshold(threshold_dict: dict[str, Any]) -> tuple[int, ThresholdType, str]:
    """
    Parse a threshold dictionary.

    Returns: (cutoff, threshold_type, criterion)
    """
    try:
        cutoff = int(threshold_dict['cutoff'])
        criterion = threshold_dict['criterion']
        threshold_type: ThresholdType = threshold_dict.get('type', 'GTE')
        if threshold_type not in ('GTE', 'LTE'):
            threshold_type = 'GTE'
        return cutoff, threshold_type, criterion
    except (KeyError, ValueError, TypeError) as e:
        raise ParseError(f"Invalid threshold: {e}") from e


def _parse_distinct_threshold(distinct_dict: dict[str, Any]) -> DistinctThreshold:
    """Parse a distinct-threshold dictionary."""
    try:
        cutoff = int(distinct_dict['cutoff'])
        comparison: ThresholdType = distinct_dict.get('type', 'GTE')
        if comparison not in ('GTE', 'LTE'):
            comparison = 'GTE'
        return DistinctThreshold(cutoff=cutoff, comparison=comparison)
    except (KeyError, ValueError, TypeError) as e:
        raise ParseError(f"Invalid distinct-threshold: {e}") from e


def parse(
    req_item: dict[str, Any],
    parent_id: str = "",
    counter: dict[str, int] | None = None,
) -> Node:
    """
    Parse a Fireroad requirement item into a req_2 Node.

    Args:
        req_item: Dictionary from Fireroad API
        parent_id: ID path of parent requirement (for generating unique IDs)
        counter: Counter dict for tracking unnamed groups

    Returns:
        Parsed req_2 Node

    Raises:
        ParseError: If the requirement structure is invalid
    """
    if counter is None:
        counter = {}

    title = req_item.get('title')

    # Case 1: Leaf node with 'req' but no 'reqs'
    if 'req' in req_item and 'reqs' not in req_item:
        course_id = req_item['req']
        is_plain_string = req_item.get('plain-string', False)

        req_id = _make_id(title, course_id, parent_id, counter)

        if is_plain_string:
            return PlainString(description=course_id, title=title, req_id=req_id)

        return _parse_leaf(course_id, title, req_id)

    # Case 2: Group node with 'reqs'
    if 'reqs' not in req_item:
        raise ParseError(f"Requirement must have 'req' or 'reqs' field. Got: {list(req_item.keys())}")

    sub_reqs = req_item['reqs']
    if not isinstance(sub_reqs, list):
        raise ParseError(f"'reqs' must be a list, got {type(sub_reqs)}")

    # Generate group ID
    connection_type = req_item.get('connection-type')
    if title:
        group_id = _make_id(title, "", parent_id, counter)
    else:
        conn_type = connection_type or 'group'
        counter_key = f"group:{parent_id}/{conn_type}" if parent_id else f"group:{conn_type}"
        count = counter.get(counter_key, 0)
        counter[counter_key] = count + 1
        group_id = f"{parent_id}/{conn_type}{count + 1}" if parent_id else f"{conn_type}{count + 1}"

    # Parse children recursively
    children: list[Node] = []
    for i, sub_req in enumerate(sub_reqs):
        try:
            children.append(parse(sub_req, parent_id=group_id, counter=counter))
        except ParseError as e:
            raise ParseError(f"Error parsing child {i}: {e}") from e

    children_tuple = tuple(children)

    # Parse threshold if present
    threshold = req_item.get('threshold')
    distinct_threshold = req_item.get('distinct-threshold')

    # Determine group type based on threshold and connection_type
    if threshold is not None:
        cutoff, threshold_type, criterion = _parse_threshold(threshold)

        if criterion == 'units':
            return UnitThresholdGroup(
                children=children_tuple,
                cutoff=cutoff,
                threshold_type=threshold_type,
                title=title,
                req_id=group_id,
            )
        else:  # criterion == 'subjects' (default)
            distinct = None
            if distinct_threshold is not None:
                distinct = _parse_distinct_threshold(distinct_threshold)

            conn: ConnectionType = 'any'
            if connection_type == 'all':
                conn = 'all'

            return SubjectThresholdGroup(
                children=children_tuple,
                cutoff=cutoff,
                threshold_type=threshold_type,
                connection_type=conn,
                distinct_threshold=distinct,
                title=title,
                req_id=group_id,
            )

    # No threshold - use AllGroup or AnyGroup
    if connection_type == 'any':
        return AnyGroup(children=children_tuple, title=title, req_id=group_id)
    else:  # 'all' or None (default to all)
        return AllGroup(children=children_tuple, title=title, req_id=group_id)


def parse_requirement_list(reqs: list[dict[str, Any]], root_title: str = "root") -> Node:
    """
    Parse a list of requirements (top-level 'reqs' field from Fireroad).

    Wraps the list in an AllGroup since all top-level requirements must be satisfied.

    Args:
        reqs: List of requirement dictionaries
        root_title: Title for the root group

    Returns:
        AllGroup containing all parsed requirements
    """
    if not isinstance(reqs, list):
        raise ParseError(f"Requirements must be a list, got {type(reqs)}")

    # Ensure root_title is non-empty
    root_id = root_title if root_title else "root"

    counter: dict[str, int] = {}
    children: list[Node] = []

    for i, req_item in enumerate(reqs):
        try:
            children.append(parse(req_item, parent_id=root_id, counter=counter))
        except ParseError as e:
            raise ParseError(f"Error parsing requirement {i}: {e}") from e

    return AllGroup(children=tuple(children), title=root_title, req_id=root_id)


def parse_fireroad_response(data: dict[str, Any]) -> Node:
    """
    Parse a complete Fireroad requirement response.

    Args:
        data: Full Fireroad API response with 'reqs', 'title', etc.

    Returns:
        Parsed requirement tree
    """
    if 'reqs' not in data:
        raise ParseError("Fireroad response missing 'reqs' field")

    title = data.get('title', data.get('medium-title', 'requirement'))
    slug = _slugify(title)
    # Ensure we have a non-empty root title
    root_title = slug if slug else "requirement"
    return parse_requirement_list(data['reqs'], root_title=root_title)


def node_to_string(node: Node, indent: int = 0, show_ids: bool = False) -> str:
    """Convert a req_2 Node to a human-readable string representation."""
    prefix = "  " * indent
    id_part = f" [ID: {node.req_id}]" if show_ids and node.req_id else ""
    pruned_mark = " [PRUNED]" if node.was_pruned else ""

    if isinstance(node, Course):
        title_part = f" ({node.title})" if node.title else ""
        return f"{prefix}Course: {node.subject_id}{title_part}{id_part}{pruned_mark}"

    if isinstance(node, GIR):
        title_part = f" ({node.title})" if node.title else ""
        return f"{prefix}GIR: {node.gir_code}{title_part}{id_part}{pruned_mark}"

    if isinstance(node, HASS):
        cat = node.category or "any"
        title_part = f" ({node.title})" if node.title else ""
        return f"{prefix}HASS: {cat}{title_part}{id_part}{pruned_mark}"

    if isinstance(node, CI):
        title_part = f" ({node.title})" if node.title else ""
        return f"{prefix}CI: {node.ci_type}{title_part}{id_part}{pruned_mark}"

    if isinstance(node, PlainString):
        desc = node.description[:40] + "..." if len(node.description) > 40 else node.description
        title_part = f" ({node.title})" if node.title else ""
        return f"{prefix}PlainString: '{desc}'{title_part}{id_part}{pruned_mark}"

    # Group types
    lines = []

    if isinstance(node, AllGroup):
        header = f"{prefix}AllGroup"
    elif isinstance(node, AnyGroup):
        header = f"{prefix}AnyGroup"
    elif isinstance(node, SubjectThresholdGroup):
        distinct_part = ""
        if node.distinct_threshold:
            distinct_part = f", distinct>={node.distinct_threshold.cutoff}"
        header = f"{prefix}SubjectThreshold(>={node.cutoff}, conn={node.connection_type}{distinct_part})"
    elif isinstance(node, UnitThresholdGroup):
        header = f"{prefix}UnitThreshold(>={node.cutoff} units)"
    else:
        raise Exception("Unknown node type in node_to_string")
        #header = f"{prefix}Unknown"

    title_part = f": {node.title}" if node.title else ""
    lines.append(f"{header}{title_part}{id_part}{pruned_mark}")

    for child in node.children:
        lines.append(node_to_string(child, indent + 1, show_ids=show_ids))

    return '\n'.join(lines)
