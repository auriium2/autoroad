"""
Prerequisite Parser for Fireroad Format

Fireroad uses a specific format:
- Commas (,) mean AND
- Slashes (/) mean OR
- Parentheses for grouping
- Quoted strings like ''permission of instructor'' should be filtered out

Examples:
- "18.01, 18.02" = 18.01 AND 18.02
- "18.01/18.02" = 18.01 OR 18.02
- "(18.01/18.02), 18.03" = (18.01 OR 18.02) AND 18.03
- "18.01/''permission of instructor''" = 18.01 (filter out permission)

This parser converts Fireroad format to CourseRoad array format:
- [0, "A", "B"] = A AND B
- [1, "A", "B"] = A OR B
"""

from __future__ import annotations

import re
from typing import List, Union

from .types import PrereqArray, PrereqNode, PrereqCourse, PrereqGroup


def is_valid_course_id(s: str) -> bool:
    """
    Check if a string looks like a valid MIT course ID or GIR requirement.

    Valid formats:
    - Course IDs: 6.100A, 18.03, 14.01, IDS.012, 18.C06
    - GIR requirements: GIR:BIOL, GIR:CAL2, GIR:PHY1, etc.
    """
    s = s.strip()

    # GIR requirements
    if s.startswith('GIR:'):
        return True

    # Regular course IDs
    return bool(re.match(r'^[A-Z0-9]+\.[A-Z0-9]+$', s, re.IGNORECASE))


def tokenize(prereq_str: str) -> List[str]:
    """
    Tokenize a Fireroad prerequisite string.

    Returns tokens including:
    - Course IDs (e.g., "18.01", "6.100A")
    - Operators: "," (AND), "/" (OR)
    - Parentheses: "(", ")"
    - Quoted strings (to be filtered later)
    """
    # Pattern to match:
    # - Quoted strings: ''text'' or "text"
    # - GIR requirements: GIR:XXXX
    # - Course IDs: dept.number (both can have letters/numbers)
    # - Operators: , /
    # - Parentheses: ( )
    pattern = r"''[^']*''|\"[^\"]*\"|GIR:[A-Z0-9]+|[A-Z0-9]+\.[A-Z0-9]+|[(),/]"

    tokens = re.findall(pattern, prereq_str, re.IGNORECASE)
    return [t.strip() for t in tokens if t.strip()]


def filter_junk_tokens(tokens: List[str]) -> List[str]:
    """
    Remove junk tokens like ''permission of instructor'', empty quotes, etc.
    Keep only valid course IDs and structure tokens.
    """
    filtered = []
    for token in tokens:
        # Skip quoted strings (they're usually junk like "permission of instructor")
        # Handle both '' (escaped single quotes) and " (double quotes)
        if token.startswith("''") or token.startswith('"') or token.startswith("'"):
            continue

        # Skip if it's not a course ID and not a structural token
        if token not in ['(', ')', ',', '/']:
            # Check if it's a valid course ID
            if not is_valid_course_id(token):
                continue

        filtered.append(token)

    # Clean up trailing/leading operators
    # Remove operators at the end or beginning, or consecutive operators
    cleaned = []
    for i, token in enumerate(filtered):
        # Skip leading operators
        if i == 0 and token in [',', '/']:
            continue
        # Skip trailing operators
        if i == len(filtered) - 1 and token in [',', '/']:
            continue
        # Skip consecutive operators (keep the first one)
        if token in [',', '/'] and cleaned and cleaned[-1] in [',', '/']:
            continue
        cleaned.append(token)

    return cleaned


def parse_fireroad_to_array(prereq_str: str) -> PrereqArray:
    """
    Parse a Fireroad prerequisite string into CourseRoad array format.

    Grammar:
        expr := or_expr
        or_expr := and_expr ( "/" and_expr )*
        and_expr := term ( "," term )*
        term := course_id | "(" expr ")"
    """
    if not prereq_str or not prereq_str.strip():
        return [0]

    # Tokenize and filter
    tokens = tokenize(prereq_str)
    tokens = filter_junk_tokens(tokens)

    if not tokens:
        return [0]

    # Parse with recursive descent
    index = [0]  # Use list to make it mutable in nested functions

    def peek() -> str:
        if index[0] < len(tokens):
            return tokens[index[0]]
        return ''

    def consume() -> str:
        token = peek()
        index[0] += 1
        return token

    def parse_expr() -> PrereqItem:
        """Parse top-level expression (handles OR at lowest precedence)"""
        return parse_or()

    def parse_or() -> PrereqItem:
        """Parse OR expression: term / term / ..."""
        items: List[PrereqItem] = [parse_and()]

        while peek() == '/':
            consume()  # eat '/'
            items.append(parse_and())

        if len(items) == 1:
            return items[0]

        # OR = [1, ...] (need 1 of them)
        return [1, *items]

    def parse_and() -> PrereqItem:
        """Parse AND expression: term , term , ..."""
        items: List[PrereqItem] = [parse_term()]

        while peek() == ',':
            consume()  # eat ','
            items.append(parse_term())

        if len(items) == 1:
            return items[0]

        # AND = [0, ...] (need all of them)
        return [0, *items]

    def parse_term() -> PrereqItem:
        """Parse a term: course_id or ( expr )"""
        token = peek()

        if token == '(':
            consume()  # eat '('
            expr = parse_expr()
            if peek() == ')':
                consume()  # eat ')'
            return expr

        # Must be a course ID
        course_id = consume()
        if not is_valid_course_id(course_id):
            raise ValueError(f"Invalid course ID: {course_id}")
        return course_id

    try:
        result = parse_expr()

        # If result is a string, wrap it in an array
        if isinstance(result, str):
            return [0, result]

        return result
    except Exception as e:
        # If parsing fails, return empty
        print(f"Parse error for '{prereq_str}': {e}")
        return [0]


def fireroad_to_courseroad(prereq_str: str) -> PrereqArray:
    """
    Main conversion function from Fireroad format to CourseRoad array format.
    Returns legacy array format for backward compatibility.
    """
    return parse_fireroad_to_array(prereq_str)


def fireroad_to_prereq(prereq_str: str) -> PrereqNode:
    """
    Parse Fireroad format into proper typed PrereqNode structure.
    This is the recommended API - use this instead of fireroad_to_courseroad.
    """
    array = parse_fireroad_to_array(prereq_str)
    return array_to_prereq(array)


def array_to_prereq(array: PrereqArray) -> PrereqNode:
    """
    Convert legacy array format to proper PrereqNode structure.
    
    Array format: [count, item1, item2, ...]
    - count=0 or count=len(items): AND (all required)
    - count=1: OR (one required)  
    - count=N: N of M (threshold)
    """
    if not isinstance(array, list) or len(array) == 0:
        raise ValueError("Invalid prerequisite array")
    
    if len(array) == 1:
        # Edge case: empty array [0]
        return PrereqGroup(threshold=0, items=())
    
    count = array[0]
    if not isinstance(count, int):
        raise ValueError(f"First element must be int, got {type(count)}")
    
    # Convert each item
    items = []
    for item in array[1:]:
        if isinstance(item, str):
            items.append(PrereqCourse(course_id=item))
        elif isinstance(item, list):
            items.append(array_to_prereq(item))
        else:
            raise ValueError(f"Unexpected item type: {type(item)}")
    
    return PrereqGroup(threshold=count, items=tuple(items))


def prereq_to_array(node: PrereqNode) -> PrereqArray:
    """
    Convert PrereqNode structure to legacy array format.
    Useful for serialization or backward compatibility.
    """
    if isinstance(node, PrereqCourse):
        return [0, node.course_id]
    elif isinstance(node, PrereqGroup):
        items = [prereq_to_array(item) if isinstance(item, PrereqGroup) else item.course_id 
                 for item in node.items]
        return [node.threshold, *items]
    else:
        raise ValueError(f"Unknown node type: {type(node)}")


def prereq_to_string(prereq: PrereqArray) -> str:
    """Convert a prerequisite array to a human-readable string"""
    if not isinstance(prereq, list) or len(prereq) == 0:
        return ''

    count_raw = prereq[0]
    if not isinstance(count_raw, int):
        return ''

    count = count_raw
    items = prereq[1:]

    if count == 0:
        count = len(items)

    item_strings = []
    for item in items:
        if isinstance(item, list):
            item_strings.append(f'({prereq_to_string(item)})')
        elif isinstance(item, str):
            item_strings.append(item)
        else:
            # Should never happen with our parser
            raise ValueError(f"Unexpected item type: {type(item)}")

    if count == len(items):
        return ' AND '.join(item_strings)
    elif count == 1:
        return ' OR '.join(item_strings)
    else:
        return f"{count} of: [{', '.join(item_strings)}]"
