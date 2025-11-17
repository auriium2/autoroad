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
        allow_reuse_across_requirements: bool = False,
        minimal: bool = True,
        course_tags: dict[str, list[str]] | None = None
    ):
        self.available_courses = set(available_courses)
        self.allow_reuse_across_requirements = allow_reuse_across_requirements
        self.minimal = minimal
        self.course_tags: dict[str, list[str]] = course_tags or {}
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

        # Check if this is a tag requirement (GIR:XXX or HASS:XXX)
        if course_id.startswith('GIR:') or course_id.startswith('HASS:'):
            # Find any available course that has this tag
            for available_course in self.available_courses:
                tags = self.course_tags.get(available_course, [])
                can_use = self.allow_reuse_across_requirements or available_course not in self.used_courses

                if course_id in tags and can_use:
                    self.used_courses.add(available_course)
                    return EvaluationResult(
                        satisfied=True,
                        matched_courses=[available_course]
                    )

            # No course with this tag found
            return EvaluationResult(
                satisfied=False,
                unsatisfied_reasons=[course_id]
            )

        # Regular course ID check
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
        item_results: list[EvaluationResult] = []

        for item in group.items:
            result = self.evaluate(item)
            item_results.append(result)

            all_matched_courses.extend(result.matched_courses)

            if result.satisfied:
                satisfied_count += 1

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

        # For unsatisfied groups, return unsatisfied reasons based on mode
        if self.minimal:
            # MINIMAL MODE: Return smallest set of missing prerequisites
            if group.threshold == 1:
                # OR group: return the option with fewest missing prerequisites
                unsatisfied_results = [r for r in item_results if not r.satisfied]
                if not unsatisfied_results:
                    return EvaluationResult(
                        satisfied=False,
                        matched_courses=all_matched_courses
                    )

                # Find the option with the fewest unsatisfied reasons
                minimal_option = min(unsatisfied_results, key=lambda r: len(r.unsatisfied_reasons))

                return EvaluationResult(
                    satisfied=False,
                    unsatisfied_reasons=minimal_option.unsatisfied_reasons,
                    matched_courses=all_matched_courses
                )
            elif group.threshold == len(group.items):
                # AND group: return minimal set from each unsatisfied item
                all_unsatisfied_reasons: list[str] = []
                for result in item_results:
                    if not result.satisfied:
                        all_unsatisfied_reasons.extend(result.unsatisfied_reasons)

                return EvaluationResult(
                    satisfied=False,
                    unsatisfied_reasons=all_unsatisfied_reasons,
                    matched_courses=all_matched_courses
                )
            else:
                # k-of-n group: need to satisfy k items, find the k options with fewest missing
                unsatisfied_results = [r for r in item_results if not r.satisfied]
                needed = group.threshold - satisfied_count

                # Sort by number of unsatisfied reasons and take the k with fewest
                sorted_unsatisfied = sorted(unsatisfied_results, key=lambda r: len(r.unsatisfied_reasons))
                minimal_options = sorted_unsatisfied[:needed]

                kn_unsatisfied_reasons: list[str] = []
                for result in minimal_options:
                    kn_unsatisfied_reasons.extend(result.unsatisfied_reasons)

                return EvaluationResult(
                    satisfied=False,
                    unsatisfied_reasons=kn_unsatisfied_reasons,
                    matched_courses=all_matched_courses
                )
        else:
            # COMPLETE MODE: Return all unsatisfied reasons from all branches
            complete_unsatisfied_reasons: list[str] = []
            for result in item_results:
                if not result.satisfied:
                    complete_unsatisfied_reasons.extend(result.unsatisfied_reasons)

            return EvaluationResult(
                satisfied=False,
                unsatisfied_reasons=complete_unsatisfied_reasons,
                matched_courses=all_matched_courses
            )

    def reset(self) -> None:
        """Reset the used courses set."""
        self.used_courses.clear()
