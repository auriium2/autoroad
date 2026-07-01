"""
Basic constraint builders for course scheduling.

These constraints are always applied and form the foundation of the optimization:
- Create decision variables (take_vars)
- At-most-once constraint (can't take same course twice)
- Freshman Fall unit limit (54 units max)
- IAP unit limit (12 units max)
- Lock past semesters (can't schedule courses in the past)
"""

import time
from collections.abc import Sequence
from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from shared.models.requests import Marker
from shared.optimizer.marker_constraint_builder import get_virtual_marker_attr
from shared.optimizer.semesters import ALL_SEMESTERS
from shared.utils import get_current_semester_index, is_valid_class_semester


def _extract_courses_from_req_node(node) -> set[str]:
    from shared.courses.requirements.types import Course, AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup
    
    if hasattr(node, "subject_id"):
        return {node.subject_id}
    
    res = set()
    if hasattr(node, "children") and node.children:
        for child in node.children:
            res.update(_extract_courses_from_req_node(child))
    return res


def _extract_courses_from_prereq_node(node) -> set[str]:
    from shared.courses.prerequisites.types import PrereqCourse, PrereqGroup
    
    if isinstance(node, PrereqCourse):
        return {node.course_id}
    elif isinstance(node, PrereqGroup):
        res = set()
        for item in node.items:
            res.update(_extract_courses_from_prereq_node(item))
        return res
    return set()


def create_take_vars(
    model: cp_model.CpModel,
    courses_df: pl.DataFrame,
    planning_year_start: int,
    max_semesters: int,
    markers: Sequence[Marker] | None = None,
    requirements_data: dict[str, Any] | None = None,
    prereq_trees: dict[int, Any] | None = None,
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
        requirements_data: Optional requirements dictionary for pruning irrelevant courses
        prereq_trees: Optional prerequisite trees map for pruning recursive prerequisites
    """
    start = time.time()

    take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

    ase_courses: set[str] = set()
    must_take_courses: set[str] = set()
    override_semesters: dict[str, set[int]] = {} # Override markers force creation of take_vars for specific semesters, so you can add historical classes

    if markers:
        for marker in markers:
            if marker.section == -1:  # ASE
                ase_courses.add(marker.courseId)
            elif marker.section == -2:  # Must Take
                must_take_courses.add(marker.courseId)
            elif marker.status == "override" and marker.section >= 0: #override
                semester = marker.section + 1
                if marker.courseId not in override_semesters:
                    override_semesters[marker.courseId] = set()
                override_semesters[marker.courseId].add(semester)

    # Pruning logic: identify relevant course indices
    relevant_indices: set[int] = set()
    subject_ids = courses_df['subject_id'].to_list()
    subject_id2idx = {sid: i for i, sid in enumerate(subject_ids)}

    if requirements_data is not None:
        relevant_subject_ids: set[str] = set()

        # 1. Always include courses in markers (pin, override, banish)
        if markers:
            for marker in markers:
                relevant_subject_ids.add(marker.courseId)

        # 2. Extract course leaves from requirement trees
        from shared.courses.requirements.parser import parse_fireroad_response
        from shared.courses.requirements.validator import validate_and_prune

        for req_key, req_data in requirements_data.items():
            if isinstance(req_data, dict):
                try:
                    req_tree = parse_fireroad_response(req_data)
                    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                    if validation.pruned_tree is not None:
                        relevant_subject_ids.update(_extract_courses_from_req_node(validation.pruned_tree))
                except Exception:
                    pass

        # 3. Add all courses with HASS, GIR, or Communication attributes
        for col in ('hass_attribute', 'gir_attribute', 'communication_requirement'):
            if col in courses_df.columns:
                col_vals = courses_df[col].to_list()
                for i, val in enumerate(col_vals):
                    if val is not None:
                        relevant_subject_ids.add(subject_ids[i])

        # 4. Recursively include prerequisites of any included course
        if prereq_trees is not None:
            added = True
            while added:
                added_subject_ids = set()
                for subj_id in relevant_subject_ids:
                    idx = subject_id2idx.get(subj_id)
                    if idx is not None and idx in prereq_trees:
                        try:
                            p_courses = _extract_courses_from_prereq_node(prereq_trees[idx])
                            for pc in p_courses:
                                if pc not in relevant_subject_ids:
                                    added_subject_ids.add(pc)
                        except Exception:
                            pass
                if added_subject_ids:
                    relevant_subject_ids.update(added_subject_ids)
                    added = True
                else:
                    added = False

        # Map to DataFrame indices
        for subj_id in relevant_subject_ids:
            idx = subject_id2idx.get(subj_id)
            if idx is not None:
                relevant_indices.add(idx)

    for course_idx in range(len(courses_df)):
        if requirements_data is not None and course_idx not in relevant_indices:
            continue

        subject_id = courses_df[course_idx, 'subject_id']
        forced_semesters = override_semesters.get(subject_id, set())

        # For regular semesters (1 to max_semesters)
        for semester in range(1, max_semesters + 1):
            if is_valid_class_semester(course_idx, semester, courses_df, planning_year_start) or semester in forced_semesters:
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

    print(f"[create_take_vars] Created {len(take_vars)} variables in {time.time() - start:.3f}s")
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
            for s in ALL_SEMESTERS  # Must Take (-2), ASE (-1), regular (1-12)
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
    Add constraint: hard limit of 54 units for first semester (Freshman Fall).

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
        model.Add(sum(semester_1_takes) <= 54)
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


def add_hass_total_constraint(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    courses_df: pl.DataFrame,
    required_count: int = 8
) -> int:
    """
    Add constraint: must take at least N HASS courses total.

    MIT requires 8 HASS (Humanities, Arts, and Social Sciences) courses.

    Args:
        model: OR-Tools CP-SAT model
        take_vars: Decision variables mapping (course_idx, semester) to bool vars
        courses_df: DataFrame of courses with hass_attribute column
        required_count: Number of HASS courses required (default 8)

    Returns:
        Number of constraints added (0 or 1)
    """
    if 'hass_attribute' not in courses_df.columns:
        return 0

    hass_takes: list[cp_model.IntVar] = []
    for course_idx in range(len(courses_df)):
        hass_attr = courses_df[course_idx, 'hass_attribute']
        if hass_attr and str(hass_attr).startswith('HASS'):
            course_takes = [
                take_vars[(course_idx, s)]
                for s in range(-2, 13)  # All possible semesters
                if (course_idx, s) in take_vars
            ]
            if course_takes:
                # Course is taken if any semester var is 1
                taken = model.NewBoolVar(f"hass_taken_{course_idx}")
                model.AddMaxEquality(taken, course_takes)
                hass_takes.append(taken)

    if hass_takes:
        model.Add(sum(hass_takes) >= required_count)
        return 1

    return 0


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
    - 8 HASS total requirement

    Args:
        model: OR-Tools CP-SAT model
        take_vars: Decision variables mapping (course_idx, semester) to bool vars
        courses_df: DataFrame of courses
        max_semesters: Maximum number of regular semesters

    Returns:
        Total number of constraints added
    """
    start = time.time()

    total_constraints = 0

    total_constraints += add_at_most_once_constraint(model, take_vars, courses_df, max_semesters)
    total_constraints += add_freshman_fall_limit(model, take_vars, courses_df)
    total_constraints += add_iap_limits(model, take_vars, courses_df, max_semesters)
    total_constraints += add_hass_total_constraint(model, take_vars, courses_df)

    print(f"[add_basic_constraints] Added {total_constraints} constraints in {time.time() - start:.3f}s")
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
    start = time.time()

    current_semester = get_current_semester_index(planning_year_start)

    if current_semester <= 0:
        return 0

    pinned_past_courses = set()
    if markers:
        course_id_to_idx = {}
        for idx in range(len(courses_df)):
            subject_id = courses_df[idx, 'subject_id']
            course_id_to_idx[subject_id] = idx

        for marker in markers:
            if (marker.status == "pin" or marker.status == "override") and marker.section >= 0:
                semester = marker.section + 1
                if semester <= current_semester:
                    course_idx = course_id_to_idx.get(marker.courseId)
                    if course_idx is not None:
                        pinned_past_courses.add((course_idx, semester))
                    else:
                        attr = get_virtual_marker_attr(marker.courseId)
                        if attr is not None:
                            col, val = attr
                            if col in courses_df.columns:
                                for idx in range(len(courses_df)):
                                    if courses_df[idx, col] == val:
                                        pinned_past_courses.add((idx, semester))

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

    print(f"[add_past_semester_constraints] Added {constraints_added} constraints in {time.time() - start:.3f}s")
    return constraints_added
