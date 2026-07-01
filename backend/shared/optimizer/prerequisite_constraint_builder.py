from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl
from ortools.sat.python import cp_model

from shared.courses.prerequisites.types import PrereqCourse, PrereqGroup, PrereqNode


class CourseSchedule:
    """
    Represents the available courses and their scheduling information.
    Pre-computes indexes for O(1) lookups.
    """
    _instance: "CourseSchedule | None" = None
    _df_id: int | None = None
    _custom_equiv_hash: int | None = None

    courses_df: pl.DataFrame
    planning_year_start: int
    _course_id_to_index: dict[str, int]
    _gir_to_courses: dict[str, list[int]]
    _hass_to_courses: dict[str, list[int]]
    _equivalent_courses: dict[str, list[int]]#id -> equivalents

    def __init__(self, courses_df: pl.DataFrame, planning_year_start: int, custom_equivalencies: dict[str, list[str]] | None = None):
        self.courses_df = courses_df
        self.planning_year_start = planning_year_start

        # Pre-compute course_id -> index mapping
        subject_ids = courses_df['subject_id'].to_list()
        self._course_id_to_index = {cid: i for i, cid in enumerate(subject_ids)}

        # Pre-compute GIR -> course indices mapping
        self._gir_to_courses = {}
        if "gir_attribute" in courses_df.columns:
            gir_attrs = courses_df["gir_attribute"].to_list()
            for i, gir in enumerate(gir_attrs):
                if gir is not None:
                    if gir not in self._gir_to_courses:
                        self._gir_to_courses[gir] = []
                    self._gir_to_courses[gir].append(i)

        # Pre-compute HASS -> course indices mapping
        self._hass_to_courses = {}
        if "hass_attribute" in courses_df.columns:
            hass_attrs = courses_df["hass_attribute"].to_list()
            for i, hass in enumerate(hass_attrs):
                if hass is not None:
                    if hass not in self._hass_to_courses:
                        self._hass_to_courses[hass] = []
                    self._hass_to_courses[hass].append(i)


        self._equivalent_courses = {}

        if "equivalent_subjects" in courses_df.columns:
            equiv_subjects = courses_df["equivalent_subjects"].to_list()
            for course_id, equiv_list in zip(subject_ids, equiv_subjects):
                if equiv_list:
                    if course_id not in self._equivalent_courses:
                        self._equivalent_courses[course_id] = set()
                    self._equivalent_courses[course_id].update(equiv_list)

        if custom_equivalencies:
            for course_id, equivalents in custom_equivalencies.items():
                if course_id not in self._equivalent_courses:
                    self._equivalent_courses[course_id] = set()
                self._equivalent_courses[course_id].update(equivalents)
                # Add reverse mappings
                for equiv_id in equivalents:
                    if equiv_id not in self._equivalent_courses:
                        self._equivalent_courses[equiv_id] = set()
                    self._equivalent_courses[equiv_id].add(course_id)

        # Convert sets to lists of indices (including the course itself)
        equiv_courses_final: dict[str, list[int]] = {}
        for course_id, equiv_set in self._equivalent_courses.items():
            if course_id in self._course_id_to_index:
                equiv_indices = [self._course_id_to_index[course_id]]  # Include the course itself
                for equiv_id in equiv_set:
                    if equiv_id in self._course_id_to_index:
                        equiv_idx = self._course_id_to_index[equiv_id]
                        if equiv_idx not in equiv_indices:
                            equiv_indices.append(equiv_idx)
                if len(equiv_indices) > 1:
                    equiv_courses_final[course_id] = equiv_indices
        self._equivalent_courses = equiv_courses_final

    @classmethod
    def get(cls, courses_df: pl.DataFrame, planning_year_start: int, custom_equivalencies: dict[str, list[str]] | None = None) -> "CourseSchedule":
        """Get or create a cached CourseSchedule instance."""
        df_id = id(courses_df)
        # Hash custom equivalencies to detect changes
        equiv_hash = hash(frozenset((k, tuple(v)) for k, v in (custom_equivalencies or {}).items()))
        if cls._instance is None or cls._df_id != df_id or cls._custom_equiv_hash != equiv_hash:
            cls._instance = cls(courses_df, planning_year_start, custom_equivalencies)
            cls._df_id = df_id
            cls._custom_equiv_hash = equiv_hash
        return cls._instance

    def get_course_index(self, course_id: str) -> int | None:
        return self._course_id_to_index.get(course_id)

    def get_courses_by_gir(self, gir_code: str) -> list[int]:
        return self._gir_to_courses.get(gir_code, [])

    def get_courses_by_hass(self, hass_code: str) -> list[int]:
        normalized = hass_code if hass_code.startswith("HASS-") else f"HASS-{hass_code}"
        return self._hass_to_courses.get(normalized, [])

    def get_equivalent_course_indices(self, course_id: str) -> list[int]:
        """Get indices of all courses equivalent to the given course (including itself)."""
        if course_id in self._equivalent_courses:
            return self._equivalent_courses[course_id]
        # Fall back to just the course itself if no equivalents
        idx = self._course_id_to_index.get(course_id)
        return [idx] if idx is not None else []


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

        self._prereq_taken_before_cache: dict[tuple[int, int], cp_model.IntVar] = {}
        self._gir_taken_before_cache: dict[tuple[str, int], cp_model.IntVar] = {}
        self._hass_taken_before_cache: dict[tuple[str, int], cp_model.IntVar] = {}

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

        # Regular course prerequisite - also check equivalent courses
        # Get all equivalent course indices (includes the prereq itself if it exists)
        equiv_indices = self.ctx.schedule.get_equivalent_course_indices(prereq_course_id)

        if not equiv_indices:
            # Course not found and has no equivalents
            self.warnings.append(
                f"Prerequisite course '{prereq_course_id}' not found for {course_id}"
            )
            return self.ctx.model.NewConstant(0)

        # Use a cache key that includes all equivalent courses (sorted for consistency)
        cache_key = (tuple(sorted(equiv_indices)), semester)
        if cache_key in self._prereq_taken_before_cache:
            return self._prereq_taken_before_cache[cache_key]

        var_name = self.ctx.fresh_name(f"prereq_{prereq_course_id.replace('.', '_')}_before_s{semester}")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

        # Prerequisite is satisfied if the prereq OR any equivalent course is taken in any earlier semester
        # Include special semesters (-2, -1) as they happen before regular semesters
        earlier_semesters = list(range(-2, 0)) + list(range(1, semester))
        taken_vars = [
            self.ctx.take_vars[equiv_idx, s]
            for equiv_idx in equiv_indices
            for s in earlier_semesters
            if (equiv_idx, s) in self.ctx.take_vars
        ]

        if taken_vars:
            # satisfied_var = 1 iff any of the taken_vars is 1
            self.ctx.model.AddMaxEquality(satisfied_var, taken_vars)
        else:
            # No valid semesters - cannot be satisfied
            self.ctx.model.Add(satisfied_var == 0)

        self._prereq_taken_before_cache[cache_key] = satisfied_var
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
        cache_key = (gir_code, semester)
        if cache_key in self._gir_taken_before_cache:
            return self._gir_taken_before_cache[cache_key]

        gir_courses = self.ctx.schedule.get_courses_by_gir(gir_code)

        if not gir_courses:
            self.warnings.append(
                f"No courses found with GIR attribute '{gir_code}' for {course_id}"
            )
            return self.ctx.model.NewConstant(0)

        var_name = self.ctx.fresh_name(f"prereq_GIR_{gir_code}_before_s{semester}")
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

        self._gir_taken_before_cache[cache_key] = satisfied_var
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
        cache_key = (hass_code, semester)
        if cache_key in self._hass_taken_before_cache:
            return self._hass_taken_before_cache[cache_key]

        hass_courses = self.ctx.schedule.get_courses_by_hass(hass_code)

        if not hass_courses:
            self.warnings.append(
                f"No courses found with HASS attribute '{hass_code}' for {course_id}"
            )
            return self.ctx.model.NewConstant(0)

        var_name = self.ctx.fresh_name(f"prereq_HASS_{hass_code}_before_s{semester}")
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

        self._hass_taken_before_cache[cache_key] = satisfied_var
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

        # Threshold logic: satisfied if at least 'threshold' children are satisfied
        threshold = node.threshold

        # TEMPORARY FIX: Handle empty groups with threshold=0 (from unparseable prereqs like "Permission of instructor")
        # TODO: This should be fixed in the parser instead - don't create PrereqGroup(threshold=0, items=())
        if threshold <= 0 and not child_vars:
            # Empty threshold and no children - treat as "no prerequisites" (always satisfied)
            return self.ctx.model.NewConstant(1)

        if not child_vars:
            # No valid children - cannot be satisfied
            return self.ctx.model.NewConstant(0)

        # Create variable for group satisfaction
        var_name = self.ctx.fresh_name(f"prereq_group_for_{course_id.replace('.', '_')}_s{semester}")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

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
    override_course_ids: set[str] | None = None,
    custom_equivalencies: dict[str, list[str]] | None = None
) -> tuple[ConstraintResult, PrerequisiteConstraintBuilder]:
    """
    Add prerequisite constraints to a CP-SAT model.

    Args:
        model: The CP-SAT model to add constraints to
        take_vars: Decision variables for taking courses (course_idx, semester) -> BoolVar
        courses_df: DataFrame containing course information
        planning_year_start: The starting year for planning
        prereq_trees: Map from course index to its prerequisite tree
        override_course_ids: Set of course IDs marked as override (skip prerequisite checks)
        custom_equivalencies: User-defined course equivalencies (e.g., {"18.06": ["18.C06"]})

    Returns:
        Tuple of (ConstraintResult, PrerequisiteConstraintBuilder) - result has summary, builder has cache stats
    """
    import time
    start = time.time()

    if override_course_ids is None:
        override_course_ids = set()

    # Filter out override courses from prereq_trees
    filtered_prereq_trees = {}
    for course_idx, prereq_tree in prereq_trees.items():
        course_id = courses_df[course_idx, 'subject_id']
        if course_id not in override_course_ids:
            filtered_prereq_trees[course_idx] = prereq_tree

    schedule = CourseSchedule.get(courses_df, planning_year_start, custom_equivalencies)
    ctx = ConstraintContext(model, take_vars, schedule)
    builder = PrerequisiteConstraintBuilder(ctx)

    result = builder.add_all_prerequisite_constraints(filtered_prereq_trees)

    print(f"[add_prerequisite_constraints] Added {result.constraints_added} constraints in {time.time() - start:.3f}s")
    return result, builder
