"""
Marker constraint builder: converts user-defined markers into optimization constraints.

Markers allow users to manually place courses in specific semesters or exclude them entirely.
This module translates those user intentions into hard constraints for the optimizer.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import polars as pl
from ortools.sat.python import cp_model
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from shared.models.requests import Marker


class MarkerConstraintResult(BaseModel):
    """Result of applying marker constraints."""
    constraints_added: int
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# Virtual course IDs that represent generic requirement categories
VIRTUAL_COURSE_IDS = {"HASS-A", "HASS-H", "HASS-S", "HASS-E"}


def is_virtual_marker(course_id: str) -> bool:
    return course_id in VIRTUAL_COURSE_IDS


def add_marker_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    markers: list['Marker'],
    courses_df: pl.DataFrame,
    planning_year_start: int,
) -> MarkerConstraintResult:
    """
    Add marker constraints to the optimization model.

    This converts user-defined course placements (markers) into hard constraints.

    Args:
        model: CP-SAT model
        take_vars: Decision variables mapping (course_idx, semester) -> BoolVar
        markers: List of user-defined markers
        courses_df: DataFrame with course data (must have 'subject_id' column)
        planning_year_start: Starting year for planning (e.g., 2026)

    Returns:
        MarkerConstraintResult with statistics and any warnings/errors
    """
    import time
    start = time.time()

    constraints_added = 0
    warnings = []
    errors = []

    t0 = time.time()
    course_id_to_idx = {}
    for idx in range(len(courses_df)):
        subject_id = courses_df[idx, 'subject_id']
        course_id_to_idx[subject_id] = idx
    build_idx_time = time.time() - t0

    t0 = time.time()
    hass_attr_to_indices: dict[str, list[int]] = {
        "HASS-A": [],
        "HASS-H": [],
        "HASS-S": [],
        "HASS-E": [],
    }
    if "hass_attribute" in courses_df.columns:
        for idx in range(len(courses_df)):
            hass_attr = courses_df[idx, "hass_attribute"]
            if hass_attr in hass_attr_to_indices:
                hass_attr_to_indices[hass_attr].append(idx)
    build_hass_time = time.time() - t0

    # Count HASS markers by (category, section) to handle multiple markers of same type
    hass_pin_counts: Counter[tuple[str, int]] = Counter()
    hass_banish_markers: list[tuple[str, int]] = []

    for marker in markers:
        if is_virtual_marker(marker.courseId):
            if marker.status == "pin":
                if marker.section == -2:
                    errors.append(f"{marker.courseId} markers cannot be placed in Must Take section")
                else:
                    hass_pin_counts[(marker.courseId, marker.section)] += 1
            elif marker.status == "banish":
                hass_banish_markers.append((marker.courseId, marker.section))
            elif marker.status == "override":
                errors.append(f"Override is not supported for generic {marker.courseId} markers")
            continue

    # Add constraints for HASS pin markers (grouped by category and section)
    for (hass_category, section), count in hass_pin_counts.items():
        matching_indices = hass_attr_to_indices.get(hass_category, [])

        if not matching_indices:
            errors.append(f"No courses found with {hass_category} attribute")
            continue

        if section == -1:
            # ASE semester
            semester_vars = [
                take_vars[(idx, -1)]
                for idx in matching_indices
                if (idx, -1) in take_vars
            ]
            if semester_vars:
                model.Add(sum(semester_vars) >= count)
                constraints_added += 1
            else:
                errors.append(f"No {hass_category} courses available in ASE semester")
        elif section >= 0:
            # Specific semester: require `count` courses of this category
            semester = section + 1
            semester_vars = [
                take_vars[(idx, semester)]
                for idx in matching_indices
                if (idx, semester) in take_vars
            ]
            if semester_vars:
                model.Add(sum(semester_vars) >= count)
                constraints_added += 1
            else:
                errors.append(f"No {hass_category} courses available in semester {semester}")

    # Add constraints for HASS banish markers
    for hass_category, section in hass_banish_markers:
        matching_indices = hass_attr_to_indices.get(hass_category, [])

        if section < 0:
            errors.append(f"Cannot banish {hass_category} from special semesters")
            continue

        semester = section + 1
        for idx in matching_indices:
            if (idx, semester) in take_vars:
                model.Add(take_vars[(idx, semester)] == 0)
                constraints_added += 1

    # Regular course marker handling
    for marker in markers:
        if is_virtual_marker(marker.courseId):
            continue

        course_idx = course_id_to_idx.get(marker.courseId)

        if course_idx is None:
            warnings.append(f"Course {marker.courseId} not found in course catalog")
            continue

        if marker.status == "pin":
            if marker.section == -2:
                # Must Take: course must be taken in any regular semester (1-12)
                # Don't pin to a specific semester, just ensure it's taken
                any_semester_vars = [
                    take_vars[(course_idx, s)]
                    for s in range(1, 13)
                    if (course_idx, s) in take_vars
                ]

                if not any_semester_vars:
                    errors.append(
                        f"Cannot fulfill Must Take marker for {marker.courseId}: "
                        f"course not offered in any semester"
                    )
                    continue

                # Add constraint: must take this course in at least one semester
                model.Add(sum(any_semester_vars) >= 1)
                constraints_added += 1
                continue

            elif marker.section == -1:
                semester = -1  # ASE
            elif marker.section >= 0:
                semester = marker.section + 1  # Regular semesters (0->1, 1->2, etc.)
            else:
                warnings.append(
                    f"Pin marker for {marker.courseId} has invalid section {marker.section}, skipping"
                )
                continue

            # Check if take_var exists for this (course, semester)
            if (course_idx, semester) not in take_vars:
                errors.append(
                    f"Cannot pin {marker.courseId} to semester {semester}: "
                    f"course not offered in that semester"
                )
                continue

            # Add constraint: must take this course in this semester
            model.Add(take_vars[(course_idx, semester)] == 1)
            constraints_added += 1

        elif marker.status == "banish":
            # Banish: Prevent course from being taken
            if marker.section == -2:
                # Must Take banish: never take this course in any semester
                any_semester_vars = [
                    take_vars[(course_idx, s)]
                    for s in range(1, 13)
                    if (course_idx, s) in take_vars
                ]
                # Also include ASE if available
                if (course_idx, -1) in take_vars:
                    any_semester_vars.append(take_vars[(course_idx, -1)])

                if not any_semester_vars:
                    warnings.append(
                        f"Course {marker.courseId} has no available semesters, "
                        f"banish constraint has no effect"
                    )
                    continue

                # Add constraint: must NOT take this course in any semester
                for var in any_semester_vars:
                    model.Add(var == 0)
                constraints_added += len(any_semester_vars)
                continue

            if marker.section == -1:
                # ASE banish: don't allow in ASE
                errors.append(
                    f"Banish marker for {marker.courseId} in ASE section is not supported"
                )
                continue

            semester = marker.section + 1  # Regular semesters only

            # Check if take_var exists for this (course, semester)
            if (course_idx, semester) not in take_vars:
                warnings.append(
                    f"Course {marker.courseId} is not offered in semester {semester}, "
                    f"banish constraint has no effect"
                )
                continue

            # Add constraint: must NOT take this course in this semester
            model.Add(take_vars[(course_idx, semester)] == 0)
            constraints_added += 1

        elif marker.status == "override":
            # Override: Force course to be taken in specific semester, skip prerequisite checking
            # Must Take (section -2): not allowed for override - must pick a specific semester
            # ASE (section -1): override in ASE semester
            # Regular sections: override in that specific semester
            if marker.section == -2:
                errors.append(
                    f"Override marker for {marker.courseId} cannot be in Must Take column. "
                    f"Please move to a specific semester to use override mode."
                )
                continue
            elif marker.section == -1:
                semester = -1  # ASE
            elif marker.section >= 0:
                semester = marker.section + 1  # Regular semesters
            else:
                errors.append(
                    f"Override marker for {marker.courseId} has invalid section {marker.section}"
                )
                continue

            # Check if take_var exists for this (course, semester)
            if (course_idx, semester) not in take_vars:
                errors.append(
                    f"Cannot override {marker.courseId} to semester {semester}: "
                    f"course not offered in that semester"
                )
                continue

            # Must take this course in this semester (prerequisite checking skipped elsewhere)
            model.Add(take_vars[(course_idx, semester)] == 1)
            constraints_added += 1
        else:
            warnings.append(f"Unknown marker status: {marker.status}")

    total_time = time.time() - start
    print(f"[Markers] Added {constraints_added} constraints in {total_time:.3f}s "
          f"(build_idx={build_idx_time:.3f}s, build_hass={build_hass_time:.3f}s)")

    return MarkerConstraintResult(
        constraints_added=constraints_added,
        warnings=warnings,
        errors=errors,
    )
