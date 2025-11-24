"""
Basic constraint builders for course scheduling.

These constraints are always applied and form the foundation of the optimization:
- Create decision variables (take_vars)
- At-most-once constraint (can't take same course twice)
- Freshman Fall unit limit (48 units max)
- IAP unit limit (12 units max)
- Lock past semesters (can't schedule courses in the past)
"""

from collections.abc import Sequence

import polars as pl
from ortools.sat.python import cp_model

from api.models.requests import Marker
from utils.utils import get_current_semester_index, is_valid_class_semester


def create_take_vars(
    model: cp_model.CpModel,
    courses_df: pl.DataFrame,
    planning_year_start: int,
    max_semesters: int,
    markers: Sequence[Marker] | None = None
) -> dict[tuple[int, int], cp_model.IntVar]:
    """
    Create decision variables for taking courses.
    
    Variables are created for:
    - Regular semesters (1 to max_semesters) if course is offered and valid
    - ASE semester (-1) only if there's an ASE marker for that course
    - Must Take semester (-2) only if there's a Must Take marker for that course
    
    Args:
        model: OR-Tools CP-SAT model
        courses_df: DataFrame of courses with offering information
        planning_year_start: Starting year for planning (e.g., 2024)
        max_semesters: Maximum number of regular semesters to plan
        markers: Optional list of markers (pin, override, banish) for courses
    
    Returns:
        Dictionary mapping (course_idx, semester) to boolean decision variables
        Semester can be:
        - -2: Must Take (course must be taken in some regular semester)
        - -1: ASE (Advanced Standing Exam credit)
        - 1 to max_semesters: Regular semesters
    """
    take_vars = {}

    # Build a set of course_ids for special semesters
    # Must Take (section=-2) is handled as a requirement constraint, not a placement
    # ASE (section=-1) creates a special semester variable
    ase_courses = set()
    must_take_courses = set()

    if markers:
        for marker in markers:
            if marker.section == -1:  # ASE
                ase_courses.add(marker.courseId)
            elif marker.section == -2:  # Must Take
                must_take_courses.add(marker.courseId)

    for course_idx in range(len(courses_df)):
        subject_id = courses_df[course_idx, 'subject_id']

        # For regular semesters (1 to max_semesters)
        for semester in range(1, max_semesters + 1):
            if is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
                var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
                take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)

        # For ASE semester, only create var if there's an ASE marker
        if subject_id in ase_courses:
            var_name = f"take_{subject_id.replace('.', '_')}_s-1"
            take_vars[(course_idx, -1)] = model.NewBoolVar(var_name)

        # For Must Take semester, only create var if there's a Must Take marker
        if subject_id in must_take_courses:
            var_name = f"take_{subject_id.replace('.', '_')}_s-2"
            take_vars[(course_idx, -2)] = model.NewBoolVar(var_name)

    return take_vars


def add_at_most_once_constraint(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
    max_semesters: int
) -> int:
    """
    Add constraint: each course can be taken at most once across all semesters.
    
    This includes special semesters (ASE, Must Take) to prevent duplicates when
    a course is pinned to ASE but optimizer tries to schedule it again.
    
    Args:
        model: OR-Tools CP-SAT model
        take_vars: Decision variables mapping (course_idx, semester) to bool vars
        courses_df: DataFrame of courses
        max_semesters: Maximum number of regular semesters
    
    Returns:
        Number of constraints added
    """
    constraints_added = 0

    for course_idx in range(len(courses_df)):
        all_semester_takes = [
            take_vars[(course_idx, s)]
            for s in range(-2, max_semesters + 1)  # Include Must Take (-2), ASE (-1), regular (1-max)
            if (course_idx, s) in take_vars
        ]
        if all_semester_takes:
            model.Add(sum(all_semester_takes) <= 1)
            constraints_added += 1

    return constraints_added


def add_freshman_fall_limit(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame
) -> int:
    """
    Add constraint: hard limit of 48 units for first semester (Freshman Fall).
    
    This is an MIT policy constraint.
    
    Args:
        model: OR-Tools CP-SAT model
        take_vars: Decision variables mapping (course_idx, semester) to bool vars
        courses_df: DataFrame of courses with total_units column
    
    Returns:
        Number of constraints added (0 or 1)
    """
    semester_1_takes = [
        take_vars[(c, 1)] * courses_df[c, 'total_units']
        for c in range(len(courses_df))
        if (c, 1) in take_vars and 'total_units' in courses_df.columns and courses_df[c, 'total_units'] is not None
    ]

    if semester_1_takes:
        model.Add(sum(semester_1_takes) <= 48)
        return 1

    return 0


def add_iap_limits(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
    max_semesters: int
) -> int:
    """
    Add constraints: hard limit of 12 units for IAP semesters.
    
    IAP (Independent Activities Period) is MIT's January term with restricted unit load.
    IAP semesters are: 2, 5, 8, 11 (every 3rd semester starting from 2).
    
    This is an MIT policy constraint.
    
    Args:
        model: OR-Tools CP-SAT model
        take_vars: Decision variables mapping (course_idx, semester) to bool vars
        courses_df: DataFrame of courses with total_units column
        max_semesters: Maximum number of regular semesters
    
    Returns:
        Number of constraints added
    """
    constraints_added = 0

    for semester in range(1, max_semesters + 1):
        # IAP semesters: (semester - 2) % 3 == 0, for semesters 2, 5, 8, 11
        is_iap = (semester - 2) % 3 == 0 and semester >= 2 and semester <= 11
        if is_iap:
            semester_takes = [
                take_vars[(c, semester)] * courses_df[c, 'total_units']
                for c in range(len(courses_df))
                if (c, semester) in take_vars and 'total_units' in courses_df.columns and courses_df[c, 'total_units'] is not None
            ]
            if semester_takes:
                model.Add(sum(semester_takes) <= 12)
                constraints_added += 1

    return constraints_added


def add_basic_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
    max_semesters: int
) -> int:
    """
    Add all basic constraints to the model.
    
    This is a convenience function that adds:
    - At most once constraint
    - Freshman Fall unit limit
    - IAP unit limits
    
    Args:
        model: OR-Tools CP-SAT model
        take_vars: Decision variables mapping (course_idx, semester) to bool vars
        courses_df: DataFrame of courses
        max_semesters: Maximum number of regular semesters
    
    Returns:
        Total number of constraints added
    """
    total_constraints = 0

    total_constraints += add_at_most_once_constraint(model, take_vars, courses_df, max_semesters)
    total_constraints += add_freshman_fall_limit(model, take_vars, courses_df)
    total_constraints += add_iap_limits(model, take_vars, courses_df, max_semesters)

    return total_constraints


def add_past_semester_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
    planning_year_start: int,
    markers: Sequence[Marker] | None = None
) -> int:
    """
    Prevent optimizer from placing courses in semesters that have already passed.
    
    Pinned courses in past semesters are allowed (user explicitly placed them there).
    
    Args:
        model: OR-Tools CP-SAT model
        take_vars: Decision variables mapping (course_idx, semester) to bool vars
        courses_df: DataFrame of courses
        planning_year_start: Starting year for planning (e.g., 2024)
        markers: Optional list of markers (pin, override, banish) for courses
    
    Returns:
        Number of constraints added
    """
    current_semester = get_current_semester_index(planning_year_start)

    if current_semester <= 0:
        return 0

    # Build a set of (course_id, semester) tuples for pinned courses in past semesters
    pinned_past_courses = set()
    if markers:
        # Build course_id -> course_idx mapping
        course_id_to_idx = {}
        for idx in range(len(courses_df)):
            subject_id = courses_df[idx, 'subject_id']
            course_id_to_idx[subject_id] = idx

        for marker in markers:
            if (marker.status == "pin" or marker.status == "override") and marker.section >= 0:
                course_idx = course_id_to_idx.get(marker.courseId)
                if course_idx is not None:
                    # Convert section (0-based) to semester (1-based)
                    semester = marker.section + 1
                    if semester <= current_semester:
                        pinned_past_courses.add((course_idx, semester))

    constraints_added = 0

    # For all semesters up to and including the current one, prevent new placements
    # We lock the current semester too since it's already in progress
    for course_idx in range(len(courses_df)):
        for semester in range(1, current_semester + 1):
            if (course_idx, semester) in take_vars:
                # Skip if this course is pinned to this past semester
                if (course_idx, semester) in pinned_past_courses:
                    continue

                # Force this variable to 0 (cannot take this course in this past semester)
                model.Add(take_vars[(course_idx, semester)] == 0)
                constraints_added += 1

    return constraints_added
