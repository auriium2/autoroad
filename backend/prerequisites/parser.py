from __future__ import annotations

import re
from typing import List

from .types import PrereqCourse, PrereqGroup, PrereqNode


def is_valid_course_id(s: str) -> bool:
    """
    Checks if a string is a valid course ID (e.g., "18.01", "6.100A") or GIR.
    """
    s = s.strip()
    # GIRs are valid
    if s.startswith("GIR:"):
        return True

    # Standard course format: <department>.<number>
    # Department can be letters or numbers (e.g., 18, 6, MAS)
    # Number can have letters (e.g., 100A, C06)
    return bool(re.match(r"^[A-Z0-9]+\.[A-Z0-9]+$", s, re.IGNORECASE))


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
    # Filter out junk tokens (quoted strings and non-structural/non-course tokens)
    filtered = []
    for token in tokens:
        if token.startswith("''") or token.startswith('"'):
            continue

        # If it's a structural token, keep it
        if token in ['(', ')', ',', '/']:
            filtered.append(token)
        # If it's a valid course ID, keep it
        elif is_valid_course_id(token):
            filtered.append(token)
        # Otherwise, it's junk
        else:
            continue

    # Clean up trailing/leading operators
    if not filtered:
        return []

    # Remove operators at the beginning
    while filtered and filtered[0] in [',', '/']:
        filtered.pop(0)

    # Remove operators at the end
    while filtered and filtered[-1] in [',', '/']:
        filtered.pop()

    # Remove consecutive operators
    cleaned = []
    if filtered:
        cleaned.append(filtered[0])
        for i in range(1, len(filtered)):
            if filtered[i] in [',', '/'] and cleaned[-1] in [',', '/']:
                continue
            cleaned.append(filtered[i])

    return cleaned

def parse_fireroad(prereq_str: str) -> PrereqNode:
    """
    Parse a Fireroad prerequisite string into PrereqNode structure.

    Grammar:
        expr := or_expr
        or_expr := and_expr ( "/" and_expr )*
        and_expr := term ( "," term )*
        term := course_id | "(" expr ")"
    """
    if not prereq_str or not prereq_str.strip():
        return PrereqGroup(threshold=0, items=())

    # Tokenize and filter
    tokens = tokenize(prereq_str)
    tokens = filter_junk_tokens(tokens)

    if not tokens:
        return PrereqGroup(threshold=0, items=())

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

    def parse_expr() -> PrereqNode:
        """Parse top-level expression (handles OR at lowest precedence)"""
        return parse_or()

    def parse_or() -> PrereqNode:
        """Parse OR expression: term / term / ..."""
        items: List[PrereqNode] = [parse_and()]

        while peek() == '/':
            consume()  # eat '/'
            items.append(parse_and())

        if len(items) == 1:
            return items[0]

        # OR = threshold of 1 (need 1 of them)
        return PrereqGroup(threshold=1, items=tuple(items))

    def parse_and() -> PrereqNode:
        """Parse AND expression: term , term , ..."""
        items: List[PrereqNode] = [parse_term()]

        while peek() == ',':
            consume()  # eat ','
            items.append(parse_term())

        if len(items) == 1:
            return items[0]

        # AND = threshold of 0 (all of them, converted in PrereqGroup.__post_init__)
        return PrereqGroup(threshold=0, items=tuple(items))

    def parse_term() -> PrereqNode:
        """Parse a term: course_id or ( expr )"""
        token = peek()

        if token == '(':
            consume()  # eat '('
            expr = parse_expr()
            if peek() == ')':
                consume()  # eat ')'
            else:
                raise ValueError("Mismatched parentheses: expected ')'")
            return expr

        # If it's a structural token that's not '(', it's an error here
        if token in [')', ',', '/']:
            raise ValueError(f"Unexpected token: {token}")

        # Must be a course ID
        course_id = consume()
        if not is_valid_course_id(course_id):
            raise ValueError(f"Invalid course ID: {course_id}")
        return PrereqCourse(course_id=course_id)

    result = parse_expr()
    return result


def prereq_to_string(prereq: PrereqNode) -> str:
    """Converts a PrereqNode to a human-readable string."""
    if isinstance(prereq, PrereqCourse):
        return prereq.course_id
    if not isinstance(prereq, PrereqGroup):
        raise TypeError(f"Unknown node type: {type(prereq)}")

    if not prereq.items:
        return ''

    item_strings = [
        f'({prereq_to_string(item)})' if isinstance(item, PrereqGroup) else prereq_to_string(item)
        for item in prereq.items
    ]

    # In __post_init__, a threshold of 0 is converted to len(items)
    if prereq.threshold == len(prereq.items):
        return ' AND '.join(item_strings)
    if prereq.threshold == 1:
        return ' OR '.join(item_strings)

    return f"{prereq.threshold} of: [{', '.join(item_strings)}]"
