"""
Marker constraint builder: converts user-defined markers into optimization constraints.

Markers allow users to manually place courses in specific semesters or exclude them entirely.
This module translates those user intentions into hard constraints for the optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
from ortools.sat.python import cp_model

MarkerStatus = Literal["pin", "banish", "override"]


@dataclass
class Marker:
    """
    User-defined course placement constraint.
    
    Attributes:
        course_id: Course subject ID (e.g., "6.120A")
        section: Semester index (0-based, or -1 for "any semester")
        status: Type of constraint:
            - "pin": Force course to be taken in this semester
            - "banish": Prevent course from being taken at all
            - "override": Force course to be taken in specific semester, skipping prerequisite checks
    """
    course_id: str
    section: int
    status: MarkerStatus = "pin"


@dataclass
class MarkerConstraintResult:
    """Result of applying marker constraints."""
    constraints_added: int
    warnings: list[str]
    errors: list[str]


def add_marker_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    markers: list[Marker],
    courses_df: pd.DataFrame,
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
    for idx in courses_df.index:
        subject_id = courses_df.at[idx, 'subject_id']
        course_id_to_idx[subject_id] = idx

    for marker in markers:
        course_idx = course_id_to_idx.get(marker.course_id)

        if course_idx is None:
            warnings.append(f"Course {marker.course_id} not found in course catalog")
            continue

        if marker.status == "pin":
            # Pin: Force course to be taken in specified semester
            # Special handling for Must Take (section -2): require course in ANY semester
            # ASE (section -1): pin to ASE semester
            # Regular sections (0-11): pin to specific semester (converted to 1-12)
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
                        f"Cannot fulfill Must Take marker for {marker.course_id}: "
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
                    f"Pin marker for {marker.course_id} has invalid section {marker.section}, skipping"
                )
                continue

            # Check if take_var exists for this (course, semester)
            if (course_idx, semester) not in take_vars:
                errors.append(
                    f"Cannot pin {marker.course_id} to semester {semester}: "
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
                    f"Banish marker for {marker.course_id} has section={marker.section}, "
                    f"cannot banish from special semesters (Must Take/ASE)"
                )
                continue

            semester = marker.section + 1  # Regular semesters only

            # Check if take_var exists for this (course, semester)
            if (course_idx, semester) not in take_vars:
                warnings.append(
                    f"Course {marker.course_id} is not offered in semester {semester}, "
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
                    f"Override marker for {marker.course_id} cannot be in Must Take column. "
                    f"Please move to a specific semester to use override mode."
                )
                continue
            elif marker.section == -1:
                semester = -1  # ASE
            elif marker.section >= 0:
                semester = marker.section + 1  # Regular semesters
            else:
                errors.append(
                    f"Override marker for {marker.course_id} has invalid section {marker.section}"
                )
                continue

            # Check if take_var exists for this (course, semester)
            if (course_idx, semester) not in take_vars:
                errors.append(
                    f"Cannot override {marker.course_id} to semester {semester}: "
                    f"course not offered in that semester"
                )
                continue

            # Must take this course in this semester (prerequisite checking skipped elsewhere)
            model.Add(take_vars[(course_idx, semester)] == 1)
            constraints_added += 1
        else:
            warnings.append(f"Unknown marker status: {marker.status}")

    return MarkerConstraintResult(
        constraints_added=constraints_added,
        warnings=warnings,
        errors=errors,
    )


def parse_markers_from_dict(markers_data: list[dict]) -> list[Marker]:
    """
    Parse markers from frontend JSON format.
    
    Expected format:
    [
        {
            "uuid": "marker_1",
            "courseId": "6.120A",
            "section": 1,
            "status": "pin"
        },
        ...
    ]
    
    Args:
        markers_data: List of marker dictionaries from frontend
        
    Returns:
        List of Marker objects
    """
    markers = []

    for data in markers_data:
        # Extract fields, with defaults
        course_id = data.get("courseId")
        section = data.get("section", -1)
        status = data.get("status", "pin")

        if not course_id:
            continue

        # Validate status
        if status not in ["pin", "banish", "override"]:
            status = "pin"

        markers.append(Marker(
            course_id=course_id,
            section=section,
            status=status,
        ))

    return markers
