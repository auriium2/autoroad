"""
Prerequisite System - CourseRoad Compatible (Python)

Parses and evaluates prerequisites in CourseRoad's array format:
[count, item1, item2, ...]

Examples:
- [0, "18.01", "18.02"] = "18.01 AND 18.02" (0 means all)
- [1, "6.100A", "6.100B"] = "6.100A OR 6.100B" (need 1 of them)
- [2, "A", "B", "C", "D"] = "2 of: A, B, C, D"
- [0, [1, "18.01", "18.02"], "18.03"] = "(18.01 OR 18.02) AND 18.03"
"""

from typing import List, Dict, Any, Union, Set
from dataclasses import dataclass, field
import re


# ============================================================================
# Type Definitions
# ============================================================================

# CourseRoad prerequisite format:
# - First element: int (count of items needed, 0 = all)
# - Remaining elements: course IDs (str), nested lists, or dicts
PrereqArray = List[Union[int, str, List, Dict[str, Any]]]
PrereqItem = Union[str, List, Dict[str, Any]]


@dataclass
class EvaluationResult:
    satisfied: bool
    unsatisfied_reasons: List[str] = field(default_factory=list)
    matched_courses: List[str] = field(default_factory=list)


# ============================================================================
# Prerequisite Evaluator
# ============================================================================

class PrerequisiteEvaluator:
    """
    Evaluates prerequisites in CourseRoad's array format.
    
    By default, follows CourseRoad's behavior where a course can only satisfy
    one requirement (no reuse across requirements).
    """

    def __init__(
        self,
        available_courses: List[str],
        allow_reuse_across_requirements: bool = False
    ):
        self.available_courses = available_courses
        self.allow_reuse_across_requirements = allow_reuse_across_requirements
        self.used_courses: Set[str] = set()

    def evaluate(self, prereq: PrereqArray) -> EvaluationResult:
        """Evaluate a prerequisite array"""
        if not isinstance(prereq, list) or len(prereq) == 0:
            raise ValueError('Invalid prerequisite array')

        count = prereq[0]
        items = prereq[1:]

        # Handle the 0 shortcut: 0 means "all of the following"
        if count == 0:
            count = len(items)

        results: List[EvaluationResult] = []
        unsatisfied_reasons: List[str] = []
        satisfied_count = 0

        # Evaluate each item
        for item in items:
            result = self._evaluate_item(item)
            results.append(result)

            if result.satisfied:
                satisfied_count += 1
            else:
                unsatisfied_reasons.extend(result.unsatisfied_reasons)

            # Early exit if we've satisfied enough requirements
            if satisfied_count >= count:
                return EvaluationResult(
                    satisfied=True,
                    unsatisfied_reasons=[],
                    matched_courses=[c for r in results for c in r.matched_courses]
                )

        # Check if we satisfied the requirement
        satisfied = satisfied_count >= count

        if satisfied:
            return EvaluationResult(
                satisfied=True,
                unsatisfied_reasons=[],
                matched_courses=[c for r in results for c in r.matched_courses]
            )

        # Build error message
        needed = count - satisfied_count
        return EvaluationResult(
            satisfied=False,
            unsatisfied_reasons=[
                f"Need {count} of {len(items)}: {', '.join(unsatisfied_reasons)}"
            ],
            matched_courses=[c for r in results for c in r.matched_courses]
        )

    def _evaluate_item(self, item: PrereqItem) -> EvaluationResult:
        """Evaluate a single prerequisite item"""
        # Nested array - recursively evaluate
        if isinstance(item, list):
            return self.evaluate(item)

        # String - simple course ID
        if isinstance(item, str):
            return self._evaluate_course(item)

        # Dict - complex requirement
        if isinstance(item, dict):
            # Range matcher
            if item.get('range'):
                return self._evaluate_range(item)

            # Regular course with metadata
            course_id = item.get('id', '')
            coreq = item.get('coreq') == 1
            return self._evaluate_course(course_id, coreq)

        raise ValueError(f'Unknown prerequisite item type: {type(item)}')

    def _evaluate_course(self, course_id: str, coreq: bool = False) -> EvaluationResult:
        """Evaluate a simple course requirement"""
        can_use = (self.allow_reuse_across_requirements or 
                   course_id not in self.used_courses)
        has_course = course_id in self.available_courses

        if has_course and can_use:
            self.used_courses.add(course_id)
            return EvaluationResult(
                satisfied=True,
                unsatisfied_reasons=[],
                matched_courses=[course_id]
            )

        reason = f'[{course_id}]' if coreq else course_id
        return EvaluationResult(
            satisfied=False,
            unsatisfied_reasons=[reason],
            matched_courses=[]
        )

    def _evaluate_range(self, obj: Dict[str, Any]) -> EvaluationResult:
        """Evaluate a range-based requirement (pattern matching)"""
        # Get the match pattern
        match_regex = obj.get('matchRegex', '')
        if isinstance(match_regex, str):
            match_pattern = re.compile(match_regex)
        else:
            # Fallback: use the ID as a prefix pattern
            course_id = obj.get('id', '')
            match_pattern = re.compile(f'^{re.escape(course_id)}')

        # Get the exclude pattern
        exclude_pattern = None
        exclude_regex = obj.get('excludeRegex')
        if exclude_regex:
            if isinstance(exclude_regex, str):
                exclude_pattern = re.compile(exclude_regex)

        # Find matching courses
        matching_courses: List[str] = []
        for course_id in self.available_courses:
            # Check if already used
            can_use = (self.allow_reuse_across_requirements or 
                       course_id not in self.used_courses)
            if not can_use:
                continue

            # Check if matches pattern
            if not match_pattern.match(course_id):
                continue

            # Check if excluded
            if exclude_pattern and exclude_pattern.match(course_id):
                continue

            matching_courses.append(course_id)

        if len(matching_courses) > 0:
            # Mark the first matching course as used
            selected_course = matching_courses[0]
            self.used_courses.add(selected_course)
            return EvaluationResult(
                satisfied=True,
                unsatisfied_reasons=[],
                matched_courses=[selected_course]
            )

        desc = obj.get('desc', '')
        return EvaluationResult(
            satisfied=False,
            unsatisfied_reasons=[f"{obj.get('id', '')}{desc}"],
            matched_courses=[]
        )

    def reset(self) -> None:
        """Reset the used courses set (useful for re-evaluation)"""
        self.used_courses.clear()


# ============================================================================
# Helper Functions
# ============================================================================

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
            desc = item.get('desc', '')
            item_strings.append(f"{item.get('id', '')}{desc}")
        else:
            item_strings.append(str(item))

    if count == len(items):
        return ' AND '.join(item_strings)
    elif count == 1:
        return ' OR '.join(item_strings)
    else:
        return f"{count} of: [{', '.join(item_strings)}]"


def parse_prereq_string(s: str) -> PrereqArray:
    """
    Parse a simple string into a prerequisite array.
    This is a basic implementation - expand as needed.
    """
    cleaned = s.strip()

    # Handle parentheses
    paren_match = re.match(r'^\(([^)]+)\)(.*)$', cleaned)
    if paren_match:
        inner = parse_prereq_string(paren_match.group(1))
        rest = paren_match.group(2).strip()
        if rest.startswith(' and '):
            rest_parsed = parse_prereq_string(rest[5:])
            return [0, inner] + rest_parsed[1:]
        elif rest.startswith(' or '):
            rest_parsed = parse_prereq_string(rest[4:])
            return [1, inner] + rest_parsed[1:]
        return inner

    # Handle AND
    if ' and ' in cleaned:
        parts = [p.strip() for p in cleaned.split(' and ')]
        return [0] + parts

    # Handle OR
    if ' or ' in cleaned:
        parts = [p.strip() for p in cleaned.split(' or ')]
        return [1] + parts

    # Single course
    return [0, cleaned]


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == '__main__':
    print("CourseRoad Prerequisite System - Python\n")

    # Example 1: "18.01 and 18.02"
    prereq1 = [0, "18.01", "18.02"]
    print(f"Example 1: {prereq_to_string(prereq1)}")

    # Example 2: "6.100A or 6.100B"
    prereq2 = [1, "6.100A", "6.100B"]
    print(f"Example 2: {prereq_to_string(prereq2)}")

    # Example 3: "(18.01 or 18.02) and 18.03"
    prereq3 = [0, [1, "18.01", "18.02"], "18.03"]
    print(f"Example 3: {prereq_to_string(prereq3)}")

    # Example 4: "2 of: 6.041, 6.042, 18.03, 18.06"
    prereq4 = [2, "6.041", "6.042", "18.03", "18.06"]
    print(f"Example 4: {prereq_to_string(prereq4)}")

    # Example 5: "Any 8.xxx course except 8.01-8.03"
    prereq5 = [1, {
        "id": "8.03-999",
        "range": 1,
        "matchRegex": r"^8\.",
        "excludeRegex": r"^8\.0[1-3]$"
    }]
    print(f"Example 5: {prereq_to_string(prereq5)}")

    # Evaluate examples
    print("\n--- Evaluation Tests ---")
    
    available = ['18.01', '18.03', '6.100A', '8.04', '8.05']
    
    evaluator = PrerequisiteEvaluator(available)
    result1 = evaluator.evaluate(prereq1)
    print(f"\n{prereq_to_string(prereq1)}")
    print(f"  Satisfied: {result1.satisfied}")
    print(f"  Reasons: {result1.unsatisfied_reasons}")
    print(f"  Matched: {result1.matched_courses}")
    
    evaluator.reset()
    result2 = evaluator.evaluate(prereq2)
    print(f"\n{prereq_to_string(prereq2)}")
    print(f"  Satisfied: {result2.satisfied}")
    print(f"  Matched: {result2.matched_courses}")
    
    evaluator.reset()
    result3 = evaluator.evaluate(prereq3)
    print(f"\n{prereq_to_string(prereq3)}")
    print(f"  Satisfied: {result3.satisfied}")
    print(f"  Matched: {result3.matched_courses}")
    
    evaluator.reset()
    result4 = evaluator.evaluate(prereq4)
    print(f"\n{prereq_to_string(prereq4)}")
    print(f"  Satisfied: {result4.satisfied}")
    print(f"  Reasons: {result4.unsatisfied_reasons}")
    print(f"  Matched: {result4.matched_courses}")
    
    evaluator.reset()
    result5 = evaluator.evaluate(prereq5)
    print(f"\n{prereq_to_string(prereq5)}")
    print(f"  Satisfied: {result5.satisfied}")
    print(f"  Matched: {result5.matched_courses}")

    # Test string parsing
    print("\n--- String Parsing Test ---")
    parsed = parse_prereq_string("(18.01 or 18.02) and 18.03")
    print(f"Input: '(18.01 or 18.02) and 18.03'")
    print(f"Parsed: {parsed}")
    print(f"Back to string: {prereq_to_string(parsed)}")
