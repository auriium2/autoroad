from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.courses.requirements.types import (
    CI,
    GIR,
    HASS,
    AllGroup,
    AnyGroup,
    CIThreshold,
    Course,
    GIRThreshold,
    HASSThreshold,
    Node,
    PlainString,
    SubjectThresholdGroup,
    UnitThresholdGroup,
)

DEFAULT_UNIT_COUNT = 12


@dataclass
class ProgressResult:
    """Progress information for a requirement node."""
    fulfilled: bool
    progress: int
    max: int
    percent_fulfilled: float
    sat_courses: list[str]
    children: list[ProgressResult] | None = None
    title: str | None = None
    req_id: str | None = None


def compute_progress(
    node: Node,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """
    Compute progress for a requirement node.

    Args:
        node: The requirement node to evaluate
        selected_subjects: Set of course IDs the student has selected
        id2course: Map from course ID to course data dict

    Returns:
        ProgressResult with fulfillment status and satisfied courses
    """
    if isinstance(node, Course):
        return _compute_course_progress(node, selected_subjects, id2course)
    elif isinstance(node, GIR):
        return _compute_gir_progress(node, selected_subjects, id2course)
    elif isinstance(node, GIRThreshold):
        return _compute_gir_threshold_progress(node, selected_subjects, id2course)
    elif isinstance(node, HASS):
        return _compute_hass_progress(node, selected_subjects, id2course)
    elif isinstance(node, HASSThreshold):
        return _compute_hass_threshold_progress(node, selected_subjects, id2course)
    elif isinstance(node, CI):
        return _compute_ci_progress(node, selected_subjects, id2course)
    elif isinstance(node, CIThreshold):
        return _compute_ci_threshold_progress(node, selected_subjects, id2course)
    elif isinstance(node, PlainString):
        return _compute_plainstring_progress(node)
    elif isinstance(node, AllGroup):
        return _compute_allgroup_progress(node, selected_subjects, id2course)
    elif isinstance(node, AnyGroup):
        return _compute_anygroup_progress(node, selected_subjects, id2course)
    elif isinstance(node, SubjectThresholdGroup):
        return _compute_subject_threshold_progress(node, selected_subjects, id2course)
    else:  # UnitThresholdGroup
        return _compute_unit_threshold_progress(node, selected_subjects, id2course)


def _compute_course_progress(
    node: Course,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """Check if a specific course is satisfied."""
    sat_courses = _find_satisfying_courses(node.subject_id, selected_subjects, id2course)
    fulfilled = len(sat_courses) > 0
    return ProgressResult(
        fulfilled=fulfilled,
        progress=1 if fulfilled else 0,
        max=1,
        percent_fulfilled=100.0 if fulfilled else 0.0,
        sat_courses=list(sat_courses),
        title=node.title,
        req_id=node.req_id,
    )


def _compute_gir_progress(
    node: GIR,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """Check if a GIR requirement is satisfied."""
    sat_courses: list[str] = []
    for course_id in selected_subjects:
        course = id2course.get(course_id, {})
        if course.get("gir_attribute") == node.gir_code:
            sat_courses.append(course_id)
            break  # Only need one

    fulfilled = len(sat_courses) > 0
    return ProgressResult(
        fulfilled=fulfilled,
        progress=1 if fulfilled else 0,
        max=1,
        percent_fulfilled=100.0 if fulfilled else 0.0,
        sat_courses=sat_courses,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_hass_progress(
    node: HASS,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """Check if a HASS requirement is satisfied."""
    sat_courses: list[str] = []
    for course_id in selected_subjects:
        course = id2course.get(course_id, {})
        hass_attr = course.get("hass_attribute", "")
        if not hass_attr:
            continue
        hass_attrs = hass_attr.split(",") if "," in hass_attr else [hass_attr]

        if node.category is None or node.category == "HASS":
            # Any HASS course satisfies
            if any(h.startswith("HASS") for h in hass_attrs):
                sat_courses.append(course_id)
        elif node.category in hass_attrs:
            sat_courses.append(course_id)

    fulfilled = len(sat_courses) > 0
    return ProgressResult(
        fulfilled=fulfilled,
        progress=1 if fulfilled else 0,
        max=1,
        percent_fulfilled=100.0 if fulfilled else 0.0,
        sat_courses=sat_courses,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_ci_progress(
    node: CI,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """Check if a CI requirement is satisfied."""
    sat_courses: list[str] = []
    for course_id in selected_subjects:
        course = id2course.get(course_id, {})
        if course.get("communication_requirement") == node.ci_type:
            sat_courses.append(course_id)

    fulfilled = len(sat_courses) > 0
    return ProgressResult(
        fulfilled=fulfilled,
        progress=1 if fulfilled else 0,
        max=1,
        percent_fulfilled=100.0 if fulfilled else 0.0,
        sat_courses=sat_courses,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_gir_threshold_progress(
    node: GIRThreshold,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """Threshold requirement for GIR courses (e.g., 'take 2 REST subjects')."""
    sat_courses: list[str] = []
    for course_id in selected_subjects:
        course = id2course.get(course_id, {})
        if course.get("gir_attribute") == node.gir_code:
            sat_courses.append(course_id)

    cutoff = node.cutoff
    progress = min(len(sat_courses), cutoff)
    fulfilled = len(sat_courses) >= cutoff

    return ProgressResult(
        fulfilled=fulfilled,
        progress=progress,
        max=cutoff,
        percent_fulfilled=(progress / cutoff * 100) if cutoff > 0 else 100.0,
        sat_courses=sat_courses,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_hass_threshold_progress(
    node: HASSThreshold,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """Threshold requirement for HASS courses (e.g., 'take 8 HASS subjects')."""
    sat_courses: list[str] = []
    for course_id in selected_subjects:
        course = id2course.get(course_id, {})
        hass_attr = course.get("hass_attribute", "")
        if not hass_attr:
            continue
        hass_attrs = hass_attr.split(",") if "," in hass_attr else [hass_attr]

        if node.category is None or node.category == "HASS":
            # Any HASS course satisfies
            if any(h.startswith("HASS") for h in hass_attrs):
                sat_courses.append(course_id)
        elif node.category in hass_attrs:
            sat_courses.append(course_id)

    cutoff = node.cutoff
    progress = min(len(sat_courses), cutoff)
    fulfilled = len(sat_courses) >= cutoff

    return ProgressResult(
        fulfilled=fulfilled,
        progress=progress,
        max=cutoff,
        percent_fulfilled=(progress / cutoff * 100) if cutoff > 0 else 100.0,
        sat_courses=sat_courses,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_ci_threshold_progress(
    node: CIThreshold,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """Threshold requirement for CI courses (e.g., 'take 2 CI-H courses')."""
    sat_courses: list[str] = []
    for course_id in selected_subjects:
        course = id2course.get(course_id, {})
        if course.get("communication_requirement") == node.ci_type:
            sat_courses.append(course_id)

    cutoff = node.cutoff
    progress = min(len(sat_courses), cutoff)
    fulfilled = len(sat_courses) >= cutoff

    return ProgressResult(
        fulfilled=fulfilled,
        progress=progress,
        max=cutoff,
        percent_fulfilled=(progress / cutoff * 100) if cutoff > 0 else 100.0,
        sat_courses=sat_courses,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_plainstring_progress(node: PlainString) -> ProgressResult:
    """Plain strings are informational - always 'fulfilled'."""
    return ProgressResult(
        fulfilled=True,
        progress=1,
        max=1,
        percent_fulfilled=100.0,
        sat_courses=[],
        title=node.title,
        req_id=node.req_id,
    )


def _compute_allgroup_progress(
    node: AllGroup,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """All children must be satisfied."""
    child_results = [
        compute_progress(child, selected_subjects, id2course)
        for child in node.children
    ]

    all_sat_courses: set[str] = set()
    fulfilled_count = 0
    for result in child_results:
        all_sat_courses.update(result.sat_courses)
        if result.fulfilled:
            fulfilled_count += 1

    total = len(child_results)
    fulfilled = fulfilled_count == total
    progress = fulfilled_count
    max_val = total

    return ProgressResult(
        fulfilled=fulfilled,
        progress=progress,
        max=max_val,
        percent_fulfilled=(progress / max_val * 100) if max_val > 0 else 100.0,
        sat_courses=list(all_sat_courses),
        children=child_results,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_anygroup_progress(
    node: AnyGroup,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """At least one child must be satisfied."""
    child_results = [
        compute_progress(child, selected_subjects, id2course)
        for child in node.children
    ]

    all_sat_courses: set[str] = set()
    any_fulfilled = False
    best_result: ProgressResult | None = None

    for result in child_results:
        all_sat_courses.update(result.sat_courses)
        if result.fulfilled:
            any_fulfilled = True
        # Track best progress for display
        if best_result is None or (result.max > 0 and result.progress / result.max > best_result.progress / max(best_result.max, 1)):
            best_result = result

    if best_result:
        progress = best_result.progress
        max_val = best_result.max
    else:
        progress, max_val = 0, 1

    return ProgressResult(
        fulfilled=any_fulfilled,
        progress=progress,
        max=max_val,
        percent_fulfilled=(progress / max_val * 100) if max_val > 0 else 100.0,
        sat_courses=list(all_sat_courses),
        children=child_results,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_subject_threshold_progress(
    node: SubjectThresholdGroup,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """
    Threshold group counting subjects.

    Implements Fireroad's logic from progress.py:809-816:
    - ALL groups with children contribute 1 when fulfilled
    - Other children contribute their count of satisfied courses

    FIXED: distinct_threshold no longer clips to top N categories.
    """
    child_results = [
        compute_progress(child, selected_subjects, id2course)
        for child in node.children
    ]

    all_sat_courses: set[str] = set()
    satisfied_by_category: list[list[str]] = []
    num_reqs_satisfied = 0
    num_courses_satisfied = 0

    for child_node, result in zip(node.children, child_results):
        all_sat_courses.update(result.sat_courses)
        satisfied_by_category.append(result.sat_courses)

        if result.fulfilled and len(result.sat_courses) > 0:
            num_reqs_satisfied += 1

        # Fireroad's contribution logic
        if isinstance(child_node, AllGroup) and len(child_node.children) > 0:
            # ALL group with children contributes 1 when fulfilled
            if result.fulfilled and len(result.sat_courses) > 0:
                num_courses_satisfied += 1
        else:
            # Everything else contributes count of satisfied courses
            num_courses_satisfied += len(result.sat_courses)

    cutoff = node.cutoff
    progress = min(num_courses_satisfied, cutoff)
    is_fulfilled = num_courses_satisfied >= cutoff

    # Handle distinct_threshold (FIXED - no clipping bug)
    if node.distinct_threshold is not None:
        distinct_cutoff = node.distinct_threshold.cutoff
        distinct_type = node.distinct_threshold.comparison

        # Count categories that contributed at least one course
        # FIX: Don't clip to top N categories - count ALL that contributed
        categories_with_courses = sum(
            1 for cat_courses in satisfied_by_category if len(cat_courses) > 0
        )

        if distinct_type == "GTE":
            distinct_satisfied = categories_with_courses >= distinct_cutoff
        else:  # LTE
            distinct_satisfied = categories_with_courses <= distinct_cutoff

        is_fulfilled = is_fulfilled and distinct_satisfied

    # For connection_type='all', also require all children satisfied
    if node.connection_type == "all":
        is_fulfilled = is_fulfilled and (num_reqs_satisfied == len(child_results))

    return ProgressResult(
        fulfilled=is_fulfilled,
        progress=progress,
        max=cutoff,
        percent_fulfilled=(progress / cutoff * 100) if cutoff > 0 else 100.0,
        sat_courses=list(all_sat_courses),
        children=child_results,
        title=node.title,
        req_id=node.req_id,
    )


def _compute_unit_threshold_progress(
    node: UnitThresholdGroup,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> ProgressResult:
    """Threshold group counting units."""
    child_results = [
        compute_progress(child, selected_subjects, id2course)
        for child in node.children
    ]

    all_sat_courses: set[str] = set()
    for result in child_results:
        all_sat_courses.update(result.sat_courses)

    # Sum units from all satisfied courses
    total_units = 0
    for course_id in all_sat_courses:
        course = id2course.get(course_id, {})
        total_units += course.get("total_units", DEFAULT_UNIT_COUNT)

    cutoff = node.cutoff
    progress = min(total_units, cutoff)
    is_fulfilled = total_units >= cutoff

    return ProgressResult(
        fulfilled=is_fulfilled,
        progress=progress,
        max=cutoff,
        percent_fulfilled=(progress / cutoff * 100) if cutoff > 0 else 100.0,
        sat_courses=list(all_sat_courses),
        children=child_results,
        title=node.title,
        req_id=node.req_id,
    )


def _find_satisfying_courses(
    req_id: str,
    selected_subjects: set[str],
    id2course: dict[str, dict[str, Any]],
) -> set[str]:
    """
    Find courses that satisfy a specific course requirement.

    Handles direct matches, equivalents, joints, and parent/child relationships.
    """
    satisfied: set[str] = set()

    for course_id in selected_subjects:
        course = id2course.get(course_id, {})

        # Direct match
        if course_id == req_id:
            satisfied.add(course_id)
            continue

        # Equivalent subjects (can be list or comma-separated string)
        equiv = course.get("equivalent_subjects", [])
        if equiv:
            equiv_list = equiv if isinstance(equiv, list) else equiv.split(",")
            if req_id in equiv_list:
                satisfied.add(course_id)
                continue

        # Joint subjects (can be list or comma-separated string)
        joint = course.get("joint_subjects", [])
        if joint:
            joint_list = joint if isinstance(joint, list) else joint.split(",")
            if req_id in joint_list:
                satisfied.add(course_id)
                continue

        # Parent/child (e.g., 6.00 vs 6.0001+6.0002)
        children = course.get("children", [])
        if children:
            children_list = children if isinstance(children, list) else children.split(",")
            if req_id in children_list:
                satisfied.add(course_id)
                continue

        if course.get("parent") == req_id:
            parent = id2course.get(req_id, {})
            parent_children = parent.get("children", [])
            if parent_children:
                parent_children_list = parent_children if isinstance(parent_children, list) else parent_children.split(",")
                if all(c in selected_subjects for c in parent_children_list if c):
                    satisfied.add(course_id)

    return satisfied


def progress_to_json(
    result: ProgressResult, 
    node: Node, 
    id2course: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Convert a ProgressResult to JSON format matching Fireroad's API response.
    """
    output: dict[str, Any] = {
        "fulfilled": result.fulfilled,
        "progress": result.progress,
        "max": result.max,
        "percent_fulfilled": result.percent_fulfilled,
        "sat_courses": result.sat_courses,
    }

    if result.title:
        output["title"] = result.title

    # Add node-specific fields
    if isinstance(node, Course):
        output["req"] = node.subject_id
        # Mark as invalid if the course doesn't exist in the catalog
        if id2course is not None and node.subject_id not in id2course:
            output["invalid"] = True
    elif isinstance(node, GIR):
        output["req"] = f"GIR:{node.gir_code}"
    elif isinstance(node, HASS):
        output["req"] = node.category or "HASS"
    elif isinstance(node, CI):
        output["req"] = node.ci_type
    elif isinstance(node, PlainString):
        output["req"] = node.description
        output["plain-string"] = True
    else:  # Group types
        if result.children:
            output["reqs"] = [
                progress_to_json(child_result, child_node, id2course)
                for child_result, child_node in zip(result.children, node.children)
            ]

        if isinstance(node, AllGroup):
            output["connection-type"] = "all"
        elif isinstance(node, AnyGroup):
            output["connection-type"] = "any"
        elif isinstance(node, SubjectThresholdGroup):
            output["connection-type"] = node.connection_type
            output["threshold"] = {
                "type": node.threshold_type,
                "cutoff": node.cutoff,
                "criterion": "subjects",
            }
            if node.distinct_threshold:
                output["distinct-threshold"] = {
                    "type": node.distinct_threshold.comparison,
                    "cutoff": node.distinct_threshold.cutoff,
                    "criterion": "subjects",
                }
        else:  # UnitThresholdGroup
            output["threshold"] = {
                "type": node.threshold_type,
                "cutoff": node.cutoff,
                "criterion": "units",
            }

    return output
