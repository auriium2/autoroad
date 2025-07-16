# %%
import pandas as pd
import re
from datetime import datetime
from enum import Enum

class NodeType(Enum):
    LEAF = 0
    AND = 1
    OR = 2


class Node:
    type: NodeType # 0 for leaf 1 for AND 2 for OR
    contents: list[Node]
# %%

# Prerequisite handling stuff
def parse_prerequisites(prereq_str):
    if pd.isna(prereq_str) or not prereq_str:
        return []
    # Remove permission of instructor and any resulting empty delimiters
    prereq_str = re.sub(r"'?permission of instructor'?", "", prereq_str, flags=re.IGNORECASE)
    prereq_str = re.sub(r",\s*,", ",", prereq_str)  # Remove double commas
    prereq_str = prereq_str.strip(", /")
    if not prereq_str.strip():
        return []

    # Tokenize, skipping empty tokens
    tokens = [tok for tok in re.findall(r'\(|\)|/|,|[^\s(),/]+', prereq_str) if tok.strip()]

    def parse_or(tokens):
        items = [parse_and(tokens)]
        while tokens and tokens[0] == '/':
            tokens.pop(0)
            items.append(parse_and(tokens))
        items = [item for item in items if item not in (None, '', [], {})]
        if len(items) == 1:
            return items[0]
        return {'or': items}

    def parse_and(tokens):
        items = [parse_term(tokens)]
        while tokens and tokens[0] == ',':
            tokens.pop(0)
            items.append(parse_term(tokens))
        items = [item for item in items if item not in (None, '', [], {})]
        if len(items) == 1:
            return items[0]
        return {'and': items}

    def parse_term(tokens):
        if not tokens:
            return None
        token = tokens.pop(0)
        if token == '(':
            expr = parse_or(tokens)
            if tokens and tokens[0] == ')':
                tokens.pop(0)
            return expr
        else:
            return token

    result = parse_or(tokens)
    return result

# Semester validation
def is_valid_class_semester(class_idx: int, semester: int, df: pd.DataFrame, planning_year_start: int) -> bool:
    # Determine the semester year and academic year string
    if semester % 3 == 1:  # Fall semester
        semester_year = planning_year_start + (semester // 3)
        academic_year = f"{semester_year}-{semester_year + 1}"
    elif semester % 3 == 2:  # IAP semester
        semester_year = planning_year_start + (semester // 3)
        academic_year = f"{semester_year - 1}-{semester_year}"
    else:  # Spring semester
        semester_year = planning_year_start + (semester // 3) - 1
        academic_year = f"{semester_year}-{semester_year + 1}"

    not_offered_year = df.loc[class_idx, 'not_offered_year']
    if pd.isna(not_offered_year):
        return True
    # Block if the academic year matches
    return str(academic_year) != str(not_offered_year)

# Current school year finder
def find_current_school_year():
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    if current_month >= 9:  # September or later
        school_year = f"{current_year}-{current_year + 1}"
        planning_for_year = f"{current_year + 1}-{current_year + 2}"
    else:  # Before September
        school_year = f"{current_year - 1}-{current_year}"
        planning_for_year = f"{current_year}-{current_year + 1}"

    return school_year, planning_for_year

# Tests
if __name__ == "__main__":
    # Test cases for prerequisite parser
    test_prereqs = [
        "6.100A",
        "6.100A, 6.100B",
        "6.100A / 6.100B",
        "6.100A, (6.100B / 6.100C)",
        "'permission of instructor'",
        "6.100A, 'permission of instructor', 6.100B",
        "(6.100A, 6.100B) / (6.100C, 6.100D)"
    ]

    print("\nTesting prerequisite parser:")
    for test in test_prereqs:
        print(f"\nInput: {test}")
        print(f"Parsed: {parse_prerequisites(test)}")
    print("\n")

    # Test cases for semester validation
    print("\nTesting is_valid_class_semester academic year blocking:")
    test_df = pd.DataFrame({
        'not_offered_year': [None, "2025-2026", "2026-2027"]
    })

    planning_year_start = 2025
    test_cases = [
        (1, 1, False, "Fall 2025 should be blocked for 2025-2026"),
        (1, 2, False, "IAP 2026 should be blocked for 2025-2026"),
        (1, 3, False, "Spring 2026 should be blocked for 2025-2026"),
        (1, 4, True,  "Fall 2026 should NOT be blocked for 2025-2026"),
        (2, 4, False, "Fall 2026 should be blocked for 2026-2027"),
        (2, 6, False, "Spring 2027 should be blocked for 2026-2027"),
        (0, 1, True,  "No not_offered_year should always be allowed"),
    ]

    for class_idx, semester, expected, desc in test_cases:
        result = is_valid_class_semester(class_idx, semester, test_df, planning_year_start)
        print(f"{desc}: {result} (expected {expected})")

    # Test current school year finder
    print("\nTesting current school year finder:")
    school_year, planning_for_year = find_current_school_year()
    print(f"Current school year: {school_year}")
    print(f"Planning for: {planning_for_year}")
