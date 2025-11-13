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

import re
from typing import List, Union, Dict, Any


PrereqArray = List[Union[int, str, List, Dict[str, Any]]]


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
    
    def parse_expr() -> PrereqArray:
        """Parse top-level expression (handles OR at lowest precedence)"""
        return parse_or()
    
    def parse_or() -> PrereqArray:
        """Parse OR expression: term / term / ..."""
        items = [parse_and()]
        
        while peek() == '/':
            consume()  # eat '/'
            items.append(parse_and())
        
        if len(items) == 1:
            return items[0]
        
        # OR = [1, ...] (need 1 of them)
        return [1] + items
    
    def parse_and() -> PrereqArray:
        """Parse AND expression: term , term , ..."""
        items = [parse_term()]
        
        while peek() == ',':
            consume()  # eat ','
            items.append(parse_term())
        
        if len(items) == 1:
            return items[0]
        
        # AND = [0, ...] (need all of them)
        return [0] + items
    
    def parse_term() -> Union[str, PrereqArray]:
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
    """
    return parse_fireroad_to_array(prereq_str)


def prereq_to_string(prereq: PrereqArray) -> str:
    """Convert a prerequisite array to a human-readable string"""
    if not isinstance(prereq, list) or len(prereq) == 0:
        return ''

    count = prereq[0]
    items = prereq[1:]

    if count == 0:
        count = len(items)

    item_strings = []
    for item in items:
        if isinstance(item, list):
            item_strings.append(f'({prereq_to_string(item)})')
        elif isinstance(item, str):
            item_strings.append(item)
        elif isinstance(item, dict):
            item_strings.append(item.get('id', str(item)))
        else:
            item_strings.append(str(item))

    if count == len(items):
        return ' AND '.join(item_strings)
    elif count == 1:
        return ' OR '.join(item_strings)
    else:
        return f"{count} of: [{', '.join(item_strings)}]"


# ============================================================================
# Testing
# ============================================================================

if __name__ == '__main__':
    test_cases = [
        # Simple cases
        "18.01",
        "18.01/''permission of instructor''",
        
        # AND cases
        "18.01, 18.02",
        "10.213, 10.302, 10.37",
        
        # OR cases
        "18.01/18.02",
        "6.100A/6.100B",
        
        # Nested
        "(18.01/18.02), 18.03",
        "18.01, (18.02/18.03)",
        
        # Complex from real data
        "(18.06/18.700/18.701), (18.100A/18.100B/18.100P/18.100Q)",
        "(10.302, (2.671/5.310/7.003/12.335/20.109/(1.106, 1.107)/(5.351, 5.352, 5.353)))/''permission of instructor''",
        "(6.100B, (18.03/18.06/18.C06), (6.3700/6.3800/14.30/16.09/18.05))/''permission of instructor''",
    ]
    
    print("="*80)
    print("Fireroad to CourseRoad Conversion Tests")
    print("="*80)
    
    for test in test_cases:
        print(f"\nInput:  {test}")
        try:
            result = fireroad_to_courseroad(test)
            readable = prereq_to_string(result)
            print(f"Array:  {result}")
            print(f"Human:  {readable}")
        except Exception as e:
            print(f"ERROR:  {e}")
