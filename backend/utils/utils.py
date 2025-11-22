# %%
import re
from datetime import datetime
from enum import Enum

import polars as pl


class NodeType(Enum):
    LEAF = 0
    AND = 1
    OR = 2


class Node:
    type: NodeType # 0 for leaf 1 for AND 2 for OR
    contents: list['Node']

    def __init__(self, type: NodeType, contents: list['Node']):
        self.type = type
        self.contents = contents
# %%

# Prerequisite handling stuff
def parse_prerequisites(prereq_str):
    if prereq_str is None or not prereq_str:
        return []
    # Remove permission of instructor and any resulting empty delimiters
    prereq_str = re.sub(r"[\"']{0,2}permission of instructor[\"']{0,2}", "", prereq_str, flags=re.IGNORECASE)
    prereq_str = re.sub(r",\s*,", ",", prereq_str)  # Remove double commas
    prereq_str = prereq_str.strip(", /")
    if not prereq_str.strip():
        return []

    # Tokenize, skipping empty tokens and empty quote tokens, treat quoted strings as atomic tokens and 'AND' as a delimiter
    tokens = [tok for tok in re.findall(r"''[^']*''|\"[^\"]*\"|\(|\)|/|,|AND|[^\s(),/]+", prereq_str, flags=re.IGNORECASE) if tok.strip() and tok not in ("''", '""')]

    def parse_or(tokens):
        items = [parse_and(tokens)]
        while tokens and tokens and tokens[0] == '/':
            tokens.pop(0)
            items.append(parse_and(tokens))
        items = [item for item in items if item not in (None, '', [], {})]
        if len(items) == 1:
            return items[0]
        return {'or': items}

    def parse_and(tokens):
        items = [parse_term(tokens)]
        while tokens and tokens and (tokens[0] == ',' or tokens[0].lower() == 'and'):
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
        elif token == ')':
            # Ignore stray closing parenthesis
            return None
        else:
            return token if token else None

    def clean_condition(cond):
        if isinstance(cond, str):
            # Remove any prerequisite that is a Corequisite or Prerequisite
            lowered = cond.lower()
            # Remove generic text requirements
            generic_texts = [ # I need to fix this lol
                "coreq:",
                "prereq:",
                "other approved laboratory subject",
                "some familiarity",
                "permission",
                "placement test",
                "placement exam",
                "fluency in a",
                "intermediate subject",
                "intermediate level subject",
                "two mathematics subjects",
                "two subjects in anthropology",
                "one intermediate subject",
                "one intermediate level subject",
                "one intermediate spanish subject",
                "one intermediate subject in spanish",
                "one intermediate subject in french",
                "one subject in literature",
                "two subjects in literature",
                "comparative media studies",
                "writing sample",
                "one subject in writing",
                "a fiction workshop",
                "as specified for particular field",
                "history",
                "media",
                "music",
                "theater",
                "film",
                "philosophy subject",
                "permission of advisor",
                "permission of department",
                "permission of director",
                "permission of the director",
                "permission of instrctor",  # typo variant
                "physical chemistry",
                "other introductory astronomy course",
                "a subject on waves",
                "Graduate-level fluid mechanics",
                "'read the book Disciplined Entrepreneurship'", #shut yo atomic habits ass up
                "'Knowledge of differentiation'",
                "'elementary integration'"
                "'Culture'",
                "'Women'",
                "'Sexuality'",
                "Freshmen need permission of instructor",
                "'above'",
                "'One philsophy subject'",
                "'Two subjects in philosophy'",
                "'one subject on probability'",
                "'Any two subjects in philosophy'",
                "based", #parsing error? based

                "'introductory subject in thermodynamics'",
                "'Graduate-level fluid mechanics'",
                "'Undergraduate mathematics'",
                "'One philsophy subject'"

            ]
            if any(txt in lowered for txt in generic_texts):
                return None #"GIR:SOCIALSKILLS"
            return cond if cond.strip() else None
        elif isinstance(cond, dict):
            cleaned = {}
            for k, v in cond.items():
                cleaned_v = [clean_condition(c) for c in v if clean_condition(c) is not None]
                if cleaned_v:
                    cleaned[k] = cleaned_v
            return cleaned if cleaned else None
        elif isinstance(cond, list):
            cleaned_list = [clean_condition(c) for c in cond if clean_condition(c) is not None]
            return cleaned_list if cleaned_list else None
        return cond

    result = parse_or(tokens)
    result = clean_condition(result)
    return result

# Semester validation

def is_valid_class_semester(class_idx: int, semester: int, df: pl.DataFrame, planning_year_start: int, musician: bool = False) -> bool:
    # Determine the semester year and academic year string
    semester_ok = True
    if semester % 3 == 1:  # Fall semester
        semester_year = planning_year_start + (semester // 3)
        academic_year = f"{semester_year}-{semester_year + 1}"
        semester_ok = df[class_idx, 'offered_fall']
    elif semester % 3 == 2:  # IAP semester
        semester_year = planning_year_start + (semester // 3)
        academic_year = f"{semester_year - 1}-{semester_year}"
        semester_ok = df[class_idx, 'offered_IAP']
    else:  # Spring semester
        semester_year = planning_year_start + (semester // 3) - 1
        academic_year = f"{semester_year}-{semester_year + 1}"
        semester_ok = df[class_idx, 'offered_spring']


    not_offered_year = df[class_idx, 'not_offered_year']
    if not_offered_year is None:
        year_ok = True
    else:
        year_ok = str(academic_year) != str(not_offered_year)

    if not musician and df[class_idx, 'subject_id'].lower().startswith('21m'): #stupid cheating
        return False
    return semester_ok and year_ok


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


def get_current_semester_index(planning_year_start: int) -> int:
    """
    Calculate which semester index (1-12) is the current semester.
    Returns 0 if we're before the planning year starts.
    
    Semester mapping:
    1 = Freshman Fall, 2 = Freshman IAP, 3 = Freshman Spring
    4 = Sophomore Fall, 5 = Sophomore IAP, 6 = Sophomore Spring
    ...
    10 = Senior Fall, 11 = Senior IAP, 12 = Senior Spring
    """
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    # Determine which academic year we're in
    # Note: backend months are 1-indexed (1=January, 12=December)
    if current_month >= 9:  # Fall semester (September onwards)
        academic_year_start = current_year
        semester_in_year = 0  # Fall
    elif current_month == 1:  # IAP (January only)
        academic_year_start = current_year - 1
        semester_in_year = 1  # IAP
    elif current_month >= 2:  # Spring semester (February onwards)
        academic_year_start = current_year - 1
        semester_in_year = 2  # Spring
    else:  # August or earlier (before fall semester starts)
        # Still in previous academic year's spring/summer
        academic_year_start = current_year - 1
        semester_in_year = 2  # Spring

    # Calculate year offset from planning start
    years_since_start = academic_year_start - planning_year_start

    # Calculate semester index (1-12)
    # Each year has 3 semesters (Fall=0, IAP=1, Spring=2)
    semester_index = years_since_start * 3 + semester_in_year + 1

    # Clamp to valid range
    if semester_index < 1:
        return 0  # Not started yet
    if semester_index > 12:
        return 12  # Already graduated

    return semester_index

# Tests
if __name__ == "__main__":
    # Test cases for prerequisite parser
    test_prereqs = [
        "6.100A",
        "6.100A, 6.100B",
        "6.100A / 6.100B",
        "6.100A, (6.100B / 6.100C)",
        # harder cases
        "'permission of instructor'",
        "6.100A, 'permission of instructor', 6.100B",
        "(6.100A, 6.100B) / (6.100C, 6.100D)",
        # real world cases
        "(GIR:PHY2, 18.03, (2.086/6.100B/18.06))/''permission of instructor''",
        "(2.001, 2.003, (2.005/2.051), (2.00B/2.670/2.678))/''permission of instructor''",
        "GIR:PHY2/6.100A/(''Coreq: 6.1903''/6.1904)/''permission of instructor''",
        "5.310/7.002/(''Coreq: 12 units UROP''/''other approved laboratory subject'', ''permission of instructor'')",
        "(6.2300/8.07), (18.04/''Coreq: 18.075'')",
        "''Prereq: 10.213''/10.40/(5.601 AND 5.602)",
    ]

    print("\nTesting prerequisite parser:")
    for test in test_prereqs:
        print(f"\nInput: {test}")
        print(f"Parsed: {parse_prerequisites(test)}")
    print("\n")

    # # Test cases for semester validation
    # print("\nTesting is_valid_class_semester academic year blocking:")
    # test_df = pl.DataFrame({
    #     'not_offered_year': [None, "2025-2026", "2026-2027"]
    # })

    # planning_year_start = 2025
    # test_cases = [
    #     (1, 1, False, "Fall 2025 should be blocked for 2025-2026"),
    #     (1, 2, False, "IAP 2026 should be blocked for 2025-2026"),
    #     (1, 3, False, "Spring 2026 should be blocked for 2025-2026"),
    #     (1, 4, True,  "Fall 2026 should NOT be blocked for 2025-2026"),
    #     (2, 4, False, "Fall 2026 should be blocked for 2026-2027"),
    #     (2, 6, False, "Spring 2027 should be blocked for 2026-2027"),
    #     (0, 1, True,  "No not_offered_year should always be allowed"),
    # ]

    # for class_idx, semester, expected, desc in test_cases:
    #     result = is_valid_class_semester(class_idx, semester, test_df, planning_year_start)
    #     print(f"{desc}: {result} (expected {expected})")

    # # Test current school year finder
    # print("\nTesting current school year finder:")
    # school_year, planning_for_year = find_current_school_year()
    # print(f"Current school year: {school_year}")
    # print(f"Planning for: {planning_for_year}")
