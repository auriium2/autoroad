from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl
from ortools.sat.python import cp_model

from courses.prerequisites.types import PrereqCourse, PrereqGroup, PrereqNode


@dataclass
class CourseSchedule:
    """
    Represents the available courses and their scheduling information.
    """
    courses_df: pl.DataFrame
    planning_year_start: int

    def get_course_index(self, course_id: str) -> int | None:
        subject_ids = self.courses_df['subject_id'].to_list()
        try:
            return subject_ids.index(course_id)
        except ValueError:
            return None

    def get_courses_by_gir(self, gir_code: str) -> list[int]:
        if "gir_attribute" not in self.courses_df.columns:
            return []
        gir_attrs = self.courses_df["gir_attribute"].to_list()
        return [i for i, v in enumerate(gir_attrs) if v == gir_code]

    def get_courses_by_hass(self, hass_code: str) -> list[int]:
        if "hass_attribute" not in self.courses_df.columns:
            return []
        hass_attrs = self.courses_df["hass_attribute"].to_list()
        return [i for i, v in enumerate(hass_attrs) if v == hass_code]


@dataclass
class ConstraintContext:
    model: cp_model.CpModel
    take_vars: dict[tuple[int, int], cp_model.IntVar]
    schedule: CourseSchedule

    # Counter for generating unique variable names
    _counter: int = 0

    def fresh_name(self, prefix: str = "prereq") -> str:
        """Generate a unique variable name with the given prefix."""
        self._counter += 1
        return f"{prefix}_{self._counter}"


@dataclass
class ConstraintResult:
    """
    Result of building constraints for prerequisites.
    """
    constraints_added: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        """Whether there were any warnings or errors."""
        return len(self.warnings) > 0 or len(self.errors) > 0


class PrerequisiteConstraintBuilder:
    """
    Builds CP-SAT constraints from PrereqNode trees.

    For each course in the schedule, this builder ensures that if the course
    is taken in semester S, then its prerequisites must be satisfied by courses
    taken in semesters 1 through S-1.
    """

    def __init__(self, ctx: ConstraintContext):
        self.ctx: ConstraintContext = ctx
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.constraints_added: int = 0

    def add_all_prerequisite_constraints(
        self,
        prereq_trees: dict[int, PrereqNode]
    ) -> ConstraintResult:
        """
        Add prerequisite constraints for all courses.

        Args:
            prereq_trees: Map from course index to its prerequisite tree

        Returns:
            ConstraintResult with summary of constraints added and any issues
        """
        for course_idx, prereq_tree in prereq_trees.items():
            course_id = self.ctx.schedule.courses_df[course_idx, 'subject_id']

            # For each semester where this course can be taken
            for semester in range(1, 13):
                if (course_idx, semester) not in self.ctx.take_vars:
                    continue

                take_var = self.ctx.take_vars[course_idx, semester]

                # Build a variable representing whether prerequisites are satisfied
                prereq_satisfied_var = self._build_prereq_satisfaction(
                    prereq_tree,
                    course_idx,
                    semester,
                    course_id
                )

                if prereq_satisfied_var is None:
                    # If we couldn't build the constraint, log a warning but continue
                    self.warnings.append(
                        f"Could not build prerequisite constraints for {course_id} in semester {semester}"
                    )
                    continue

                # Constraint: can only take course if prerequisites are satisfied
                # take_var <= prereq_satisfied_var
                # Equivalently: take_var=1 implies prereq_satisfied_var=1
                self.ctx.model.Add(prereq_satisfied_var >= take_var)
                self.constraints_added += 1

        return ConstraintResult(
            constraints_added=self.constraints_added,
            warnings=self.warnings,
            errors=self.errors
        )

    def _build_prereq_satisfaction(
        self,
        node: PrereqNode,
        course_idx: int,
        semester: int,
        course_id: str
    ) -> cp_model.IntVar | None:
        """
        Build a boolean variable representing whether a prerequisite is satisfied.

        Args:
            node: The prerequisite node to evaluate
            course_idx: The index of the course requiring this prerequisite
            semester: The semester in which the course is being taken
            course_id: The course ID (for variable naming)

        Returns:
            A boolean variable that is 1 if the prerequisite is satisfied, 0 otherwise
        """
        if isinstance(node, PrereqCourse):
            return self._build_course_prereq(node, course_idx, semester, course_id)
        elif isinstance(node, PrereqGroup):
            return self._build_group_prereq(node, course_idx, semester, course_id)
        else:
            self.errors.append(f"Unknown prerequisite node type: {type(node).__name__}")
            return None

    def _build_course_prereq(
        self,
        node: PrereqCourse,
        course_idx: int,
        semester: int,
        course_id: str
    ) -> cp_model.IntVar | None:
        """
        Build constraints for a single course prerequisite.

        Returns a boolean variable that is 1 if this course was taken in any
        earlier semester, 0 otherwise.
        """
        prereq_course_id = node.course_id

        # Handle GIR requirements
        if prereq_course_id.startswith('GIR:'):
            gir_code = prereq_course_id.split(':', 1)[1]
            return self._build_gir_prereq(gir_code, semester, course_id)

        # Handle HASS requirements
        if prereq_course_id.startswith('HASS:'):
            hass_code = prereq_course_id.split(':', 1)[1]
            return self._build_hass_prereq(hass_code, semester, course_id)

        # Regular course prerequisite
        prereq_idx = self.ctx.schedule.get_course_index(prereq_course_id)

        if prereq_idx is None:
            # Course not found - could be a special string or typo
            # Assume satisfied to avoid blocking the optimization
            self.warnings.append(
                f"Prerequisite course '{prereq_course_id}' not found for {course_id}"
            )
            return self.ctx.model.NewConstant(1)

        # Create variable for whether this prerequisite is satisfied
        var_name = self.ctx.fresh_name(f"prereq_{prereq_course_id.replace('.', '_')}_for_{course_id.replace('.', '_')}_s{semester}")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

        # Prerequisite is satisfied if taken in any earlier semester
        # Include special semesters (-2, -1) as they happen before regular semesters
        earlier_semesters = list(range(-2, 0)) + list(range(1, semester))
        taken_vars = [
            self.ctx.take_vars[prereq_idx, s]
            for s in earlier_semesters
            if (prereq_idx, s) in self.ctx.take_vars
        ]

        if taken_vars:
            # satisfied_var = 1 iff any of the taken_vars is 1
            self.ctx.model.AddMaxEquality(satisfied_var, taken_vars)
        else:
            # No valid semesters - cannot be satisfied
            self.ctx.model.Add(satisfied_var == 0)

        return satisfied_var

    def _build_gir_prereq(
        self,
        gir_code: str,
        semester: int,
        course_id: str
    ) -> cp_model.IntVar | None:
        """
        Build constraints for a GIR prerequisite (e.g., GIR:CAL1, GIR:BIOL).

        Returns a boolean variable that is 1 if any course with this GIR attribute
        was taken in an earlier semester.
        """
        gir_courses = self.ctx.schedule.get_courses_by_gir(gir_code)

        if not gir_courses:
            self.warnings.append(
                f"No courses found with GIR attribute '{gir_code}' for {course_id}"
            )
            return self.ctx.model.NewConstant(0)

        var_name = self.ctx.fresh_name(f"prereq_GIR_{gir_code}_for_{course_id.replace('.', '_')}_s{semester}")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

        # Satisfied if any course with this GIR was taken in an earlier semester
        # Include special semesters (-2, -1) as they happen before regular semesters
        earlier_semesters = list(range(-2, 0)) + list(range(1, semester))
        taken_vars = [
            self.ctx.take_vars[c, s]
            for c in gir_courses
            for s in earlier_semesters
            if (c, s) in self.ctx.take_vars
        ]

        if taken_vars:
            self.ctx.model.AddMaxEquality(satisfied_var, taken_vars)
        else:
            self.ctx.model.Add(satisfied_var == 0)

        return satisfied_var

    def _build_hass_prereq(
        self,
        hass_code: str,
        semester: int,
        course_id: str
    ) -> cp_model.IntVar | None:
        """
        Build constraints for a HASS prerequisite (e.g., HASS:A, HASS:H).

        Returns a boolean variable that is 1 if any course with this HASS attribute
        was taken in an earlier semester.
        """
        hass_courses = self.ctx.schedule.get_courses_by_hass(hass_code)

        if not hass_courses:
            self.warnings.append(
                f"No courses found with HASS attribute '{hass_code}' for {course_id}"
            )
            return self.ctx.model.NewConstant(0)

        var_name = self.ctx.fresh_name(f"prereq_HASS_{hass_code}_for_{course_id.replace('.', '_')}_s{semester}")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

        # Satisfied if any course with this HASS was taken in an earlier semester
        # Include special semesters (-2, -1) as they happen before regular semesters
        earlier_semesters = list(range(-2, 0)) + list(range(1, semester))
        taken_vars = [
            self.ctx.take_vars[c, s]
            for c in hass_courses
            for s in earlier_semesters
            if (c, s) in self.ctx.take_vars
        ]

        if taken_vars:
            self.ctx.model.AddMaxEquality(satisfied_var, taken_vars)
        else:
            self.ctx.model.Add(satisfied_var == 0)

        return satisfied_var

    def _build_group_prereq(
        self,
        node: PrereqGroup,
        course_idx: int,
        semester: int,
        course_id: str
    ) -> cp_model.IntVar | None:
        """
        Build constraints for a group of prerequisites with a threshold.

        Examples:
        - threshold = len(items): ALL required (AND)
        - threshold = 1: ONE required (OR)
        - threshold = 2: TWO required (2 of N)
        """
        # Recursively build satisfaction variables for each child
        child_vars = []
        for child in node.items:
            child_var = self._build_prereq_satisfaction(child, course_idx, semester, course_id)
            if child_var is not None:
                child_vars.append(child_var)

        if not child_vars:
            # No valid children - cannot be satisfied
            return self.ctx.model.NewConstant(0)

        # Create variable for group satisfaction
        var_name = self.ctx.fresh_name(f"prereq_group_for_{course_id.replace('.', '_')}_s{semester}")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

        # Threshold logic: satisfied if at least 'threshold' children are satisfied
        threshold = node.threshold

        if threshold <= 0:
            # Empty threshold - always satisfied
            self.ctx.model.Add(satisfied_var == 1)
        elif threshold >= len(child_vars):
            # ALL children must be satisfied (AND)
            self.ctx.model.AddMinEquality(satisfied_var, child_vars)
        elif threshold == 1:
            # At least ONE child must be satisfied (OR)
            self.ctx.model.AddMaxEquality(satisfied_var, child_vars)
        else:
            # At least 'threshold' children must be satisfied
            sum_satisfied = sum(child_vars)
            self.ctx.model.Add(sum_satisfied >= threshold).OnlyEnforceIf(satisfied_var)
            self.ctx.model.Add(sum_satisfied < threshold).OnlyEnforceIf(satisfied_var.Not())

        return satisfied_var


def add_prerequisite_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
    planning_year_start: int,
    prereq_trees: dict[int, PrereqNode],
    override_course_ids: set[str] | None = None
) -> ConstraintResult:
    """
    Add prerequisite constraints to a CP-SAT model.

    Args:
        model: The CP-SAT model to add constraints to
        take_vars: Decision variables for taking courses (course_idx, semester) -> BoolVar
        courses_df: DataFrame containing course information
        planning_year_start: The starting year for planning
        prereq_trees: Map from course index to its prerequisite tree
        override_course_ids: Set of course IDs marked as override (skip prerequisite checks)

    Returns:
        ConstraintResult with summary of constraints added and any issues
    """
    if override_course_ids is None:
        override_course_ids = set()

    # Filter out override courses from prereq_trees
    filtered_prereq_trees = {}
    for course_idx, prereq_tree in prereq_trees.items():
        course_id = courses_df[course_idx, 'subject_id']
        if course_id not in override_course_ids:
            filtered_prereq_trees[course_idx] = prereq_tree

    schedule = CourseSchedule(courses_df, planning_year_start)
    ctx = ConstraintContext(model, take_vars, schedule)
    builder = PrerequisiteConstraintBuilder(ctx)

    return builder.add_all_prerequisite_constraints(filtered_prereq_trees)
