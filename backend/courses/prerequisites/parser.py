"""
Prerequisites Parser for Fireroad Format

This parser converts Fireroad prerequisite strings into typed PrereqNode trees.

Fireroad prerequisite format:
- Operators: "," (AND), "/" (OR)
- Grouping: parentheses for precedence
- Course IDs: "6.100A", "18.01", "GIR:CAL1"

Examples:
- Single course: "6.100A"
- AND: "6.100A,6.1200"
- OR: "18.05/18.06"
- Complex: "(6.100A,6.1200)/(6.100L,6.1200)"
"""

from __future__ import annotations

import re

from .types import PrereqCourse, PrereqGroup, PrereqNode


def is_valid_course_id(s: str) -> bool:
    """
    Check if a string is a valid course ID (e.g., "18.01", "6.100A") or GIR/HASS tag.
    """
    s = s.strip()

    if s.startswith("GIR:") or s.startswith("HASS:"):
        return True

    # Standard course format: <department>.<number>
    # Department can be letters or numbers (e.g., 18, 6, MAS)
    # Number can have letters (e.g., 100A, C06)
    return bool(re.match(r"^[A-Z0-9]+\.[A-Z0-9]+$", s, re.IGNORECASE))


def tokenize(prereq_str: str) -> list[str]:
    """
    Tokenize a Fireroad prerequisite string.

    Returns tokens including:
    - Course IDs (e.g., "18.01", "6.100A")
    - Operators: "," (AND), "/" (OR)
    - Parentheses: "(", ")"
    - Quoted strings (to be filtered later)
    - Text operators: AND, OR (convert to symbols)
    """
    # Pattern to match:
    # - Quoted strings: ''text'' or "text"
    # - GIR/HASS requirements: GIR:XXXX, HASS:X
    # - Course IDs: dept.number (both can have letters/numbers)
    # - Text operators: AND, OR (case insensitive)
    # - Operators: , /
    # - Parentheses: ( )
    pattern = r"''[^']*''|\"[^\"]*\"|(?:GIR|HASS):[A-Z0-9]+|[A-Z0-9]+\.[A-Z0-9]+|\bAND\b|\bOR\b|[(),/]"

    tokens = re.findall(pattern, prereq_str, re.IGNORECASE)

    # Convert text operators to symbols
    normalized = []
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        if t.upper() == 'AND':
            normalized.append(',')
        elif t.upper() == 'OR':
            normalized.append('/')
        else:
            normalized.append(t)

    return normalized


def filter_junk_tokens(tokens: list[str]) -> list[str]:
    """
    Remove junk tokens like ''permission of instructor'', empty quotes, etc.
    Keep only valid course IDs and structure tokens.
    """
    filtered = []
    for token in tokens:
        if token.startswith("''") or token.startswith('"'):
            continue

        if token in ['(', ')', ',', '/']:
            filtered.append(token)
        elif is_valid_course_id(token):
            filtered.append(token)

    if not filtered:
        return []

    while filtered and filtered[0] in [',', '/']:
        filtered.pop(0)

    while filtered and filtered[-1] in [',', '/']:
        filtered.pop()

    # Remove consecutive operators and operators after opening parens
    cleaned = []
    if filtered:
        cleaned.append(filtered[0])
        for i in range(1, len(filtered)):
            current = filtered[i]
            prev = cleaned[-1]

            # Skip operators that follow other operators
            if current in [',', '/'] and prev in [',', '/']:
                continue

            # Skip operators that directly follow opening parentheses
            if current in [',', '/'] and prev == '(':
                continue

            # Skip operators that directly precede closing parentheses
            if prev in [',', '/'] and current == ')':
                cleaned.pop()  # Remove the operator before the closing paren

            cleaned.append(current)

    # Remove empty parentheses: ()
    final = []
    i = 0
    while i < len(cleaned):
        if i < len(cleaned) - 1 and cleaned[i] == '(' and cleaned[i + 1] == ')':
            # Skip both ( and )
            i += 2
            # Also remove preceding operator if exists
            if final and final[-1] in [',', '/']:
                final.pop()
        else:
            final.append(cleaned[i])
            i += 1

    return final

def parse_fireroad(prereq_str: str) -> PrereqNode:
    """
    Parse a Fireroad prerequisite string into PrereqNode structure.
    
    Grammar:
        expr := or_expr
        or_expr := and_expr ( "/" and_expr )*
        and_expr := term ( "," term )*
        term := course_id | "(" expr ")"
    
    Args:
        prereq_str: Prerequisite string from Fireroad
    
    Returns:
        PrereqNode: Parsed prerequisite tree
    
    Examples:
        >>> parse_fireroad("6.100A")
        PrereqCourse(course_id='6.100A')
        
        >>> parse_fireroad("6.100A,6.1200")
        PrereqGroup(threshold=2, items=(PrereqCourse(...), PrereqCourse(...)))
    """
    if not prereq_str or not prereq_str.strip():
        return PrereqGroup(threshold=0, items=())

    tokens = tokenize(prereq_str)
    tokens = filter_junk_tokens(tokens)

    if not tokens:
        return PrereqGroup(threshold=0, items=())

    index = [0]

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
        items: list[PrereqNode] = [parse_and()]

        while peek() == '/':
            consume()
            items.append(parse_and())

        if len(items) == 1:
            return items[0]

        return PrereqGroup(threshold=1, items=tuple(items))

    def parse_and() -> PrereqNode:
        """Parse AND expression: term , term , ..."""
        items: list[PrereqNode] = [parse_term()]

        while peek() == ',':
            consume()
            items.append(parse_term())

        if len(items) == 1:
            return items[0]

        return PrereqGroup(threshold=0, items=tuple(items))

    def parse_term() -> PrereqNode:
        """Parse a term: course_id or ( expr )"""
        token = peek()

        if token == '(':
            consume()
            expr = parse_expr()
            if peek() == ')':
                consume()
            else:
                raise ValueError("Mismatched parentheses: expected ')'")
            return expr

        if token in [')', ',', '/']:
            raise ValueError(f"Unexpected token: {token}")

        course_id = consume()
        if not is_valid_course_id(course_id):
            raise ValueError(f"Invalid course ID: {course_id}")
        return PrereqCourse(course_id=course_id)

    return parse_expr()


def prereq_to_string(prereq: PrereqNode) -> str:
    """
    Convert a PrereqNode to a human-readable string.
    
    Args:
        prereq: The prerequisite node to convert
    
    Returns:
        Human-readable string representation
    """
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

    if prereq.threshold == len(prereq.items):
        return ' AND '.join(item_strings)
    if prereq.threshold == 1:
        return ' OR '.join(item_strings)

    return f"{prereq.threshold} of: [{', '.join(item_strings)}]"


def extract_course_ids(prereq_tree: PrereqNode | None) -> list[str]:
    """
    Extract all course IDs from a prerequisite tree.

    Args:
        prereq_tree: The prerequisite tree to extract from

    Returns:
        List of all course IDs in the tree
    """
    if not prereq_tree:
        return []

    if isinstance(prereq_tree, PrereqCourse):
        return [prereq_tree.course_id]

    if isinstance(prereq_tree, PrereqGroup):
        course_ids = []
        for child in prereq_tree.items:
            course_ids.extend(extract_course_ids(child))
        return course_ids

    return []
