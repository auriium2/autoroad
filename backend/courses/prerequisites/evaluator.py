"""
Prerequisite Evaluator

Evaluates whether prerequisite requirements are satisfied by a set of courses.
"""

from __future__ import annotations

from .types import EvaluationResult, PrereqCourse, PrereqGroup, PrereqNode


class PrerequisiteEvaluator:
    """
    Evaluates prerequisites in PrereqNode format.
    
    By default, a course can only satisfy one requirement (no reuse).
    """

    def __init__(
        self,
        available_courses: list[str],
        allow_reuse_across_requirements: bool = False
    ):
        self.available_courses = set(available_courses)
        self.allow_reuse_across_requirements = allow_reuse_across_requirements
        self.used_courses: set[str] = set()

    def evaluate(self, prereq: PrereqNode) -> EvaluationResult:
        """
        Recursively evaluate a prerequisite node.
        """
        if isinstance(prereq, PrereqCourse):
            return self._evaluate_course(prereq)

        if isinstance(prereq, PrereqGroup):
            return self._evaluate_group(prereq)

        raise TypeError(f"Unknown prerequisite node type: {type(prereq)}")

    def _evaluate_course(self, course: PrereqCourse) -> EvaluationResult:
        """Evaluate a simple course requirement."""
        course_id = course.course_id

        can_use = self.allow_reuse_across_requirements or course_id not in self.used_courses

        if course_id in self.available_courses and can_use:
            self.used_courses.add(course_id)
            return EvaluationResult(
                satisfied=True,
                matched_courses=[course_id]
            )

        return EvaluationResult(
            satisfied=False,
            unsatisfied_reasons=[course_id]
        )

    def _evaluate_group(self, group: PrereqGroup) -> EvaluationResult:
        """Evaluate a group of prerequisite items."""
        if not group.items:
            return EvaluationResult(satisfied=True)

        satisfied_count = 0
        all_matched_courses: list[str] = []
        all_unsatisfied_reasons: list[str] = []

        for item in group.items:
            result = self.evaluate(item)

            all_matched_courses.extend(result.matched_courses)

            if result.satisfied:
                satisfied_count += 1
            else:
                all_unsatisfied_reasons.extend(result.unsatisfied_reasons)

            if satisfied_count >= group.threshold:
                return EvaluationResult(
                    satisfied=True,
                    matched_courses=all_matched_courses
                )

        if satisfied_count >= group.threshold:
            return EvaluationResult(
                satisfied=True,
                matched_courses=all_matched_courses
            )

        return EvaluationResult(
            satisfied=False,
            unsatisfied_reasons=all_unsatisfied_reasons,
            matched_courses=all_matched_courses
        )

    def reset(self) -> None:
        """Reset the used courses set."""
        self.used_courses.clear()
