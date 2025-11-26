"""
Marker constraint builder: converts user-defined markers into optimization constraints.

Markers allow users to manually place courses in specific semesters or exclude them entirely.
This module translates those user intentions into hard constraints for the optimizer.
"""

from __future__ import annotations

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
    constraints_added = 0
    warnings = []
    errors = []

    # Build course_id -> course_idx mapping
    course_id_to_idx = {}
    for idx in range(len(courses_df)):
        subject_id = courses_df[idx, 'subject_id']
        course_id_to_idx[subject_id] = idx

    for marker in markers:
        course_idx = course_id_to_idx.get(marker.courseId)

        if course_idx is None:
            warnings.append(f"Course {marker.courseId} not found in course catalog")
            continue

        if marker.status == "pin": #force course to be taken in specified semester. if section is -2, force to be taken in any semester. if section is -1, force to be taken in ASE semester
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
            # Banish: Prevent course from being taken in this specific semester
            # Special sections not allowed for banish
            if marker.section < 0:
                errors.append(
                    f"Banish marker for {marker.courseId} has section={marker.section}, "
                    f"cannot banish from special semesters (Must Take/ASE)"
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
            _ = model.Add(take_vars[(course_idx, semester)] == 1)
            constraints_added += 1
        else:
            warnings.append(f"Unknown marker status: {marker.status}")

    return MarkerConstraintResult(
        constraints_added=constraints_added,
        warnings=warnings,
        errors=errors,
    )
