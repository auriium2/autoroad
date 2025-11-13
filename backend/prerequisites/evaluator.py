"""
Prerequisite Evaluator

Evaluates whether prerequisite requirements are satisfied by a set of courses.
"""

from typing import List, Set, Union

from .types import PrereqArray, EvaluationResult
from .parser import is_valid_course_id


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

        count_raw = prereq[0]
        if not isinstance(count_raw, int):
            raise ValueError(f'First element must be int, got {type(count_raw)}')
        
        count = count_raw
        items = prereq[1:]  # type: ignore

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
        return EvaluationResult(
            satisfied=False,
            unsatisfied_reasons=[
                f"Need {count} of {len(items)}: {', '.join(unsatisfied_reasons)}"
            ],
            matched_courses=[c for r in results for c in r.matched_courses]
        )

    def _evaluate_item(self, item: Union[str, PrereqArray]) -> EvaluationResult:
        """Evaluate a single prerequisite item"""
        # Nested array - recursively evaluate
        if isinstance(item, list):
            return self.evaluate(item)

        # String - simple course ID
        if isinstance(item, str):
            return self._evaluate_course(item)

        raise ValueError(f'Unknown prerequisite item type: {type(item)}')

    def _evaluate_course(self, course_id: str) -> EvaluationResult:
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

        return EvaluationResult(
            satisfied=False,
            unsatisfied_reasons=[course_id],
            matched_courses=[]
        )

    def reset(self) -> None:
        """Reset the used courses set (useful for re-evaluation)"""
        self.used_courses.clear()
