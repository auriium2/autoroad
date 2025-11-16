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

MarkerStatus = Literal["pin", "banish", "solo"]


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
            - "solo": Force course to be taken alone (no other courses in that semester)
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
            if marker.section < 0:
                # section = -1 means "any semester" - no constraint needed
                warnings.append(
                    f"Pin marker for {marker.course_id} has section=-1 (any semester), skipping"
                )
                continue

            # Convert section (0-based) to semester (1-based)
            semester = marker.section + 1

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
            # Banish: Prevent course from being taken at all
            # Find all semesters where this course could be taken
            course_vars = [
                take_vars[(c, s)]
                for (c, s) in take_vars.keys()
                if c == course_idx
            ]

            if not course_vars:
                warnings.append(
                    f"Course {marker.course_id} has no available semesters to banish from"
                )
                continue

            # Add constraint: sum of all take_vars for this course must be 0
            model.Add(sum(course_vars) == 0)
            constraints_added += 1

        elif marker.status == "solo":
            # Solo: Force course to be taken, and no other courses in that semester
            if marker.section < 0:
                errors.append(
                    f"Solo marker for {marker.course_id} has section=-1 (any semester), "
                    f"cannot enforce solo constraint without specific semester"
                )
                continue

            semester = marker.section + 1

            # Check if take_var exists for this (course, semester)
            if (course_idx, semester) not in take_vars:
                errors.append(
                    f"Cannot solo {marker.course_id} to semester {semester}: "
                    f"course not offered in that semester"
                )
                continue

            # Constraint 1: Must take this course in this semester
            model.Add(take_vars[(course_idx, semester)] == 1)
            constraints_added += 1

            # Constraint 2: No other courses in this semester
            other_courses_in_semester = [
                take_vars[(c, s)]
                for (c, s) in take_vars.keys()
                if s == semester and c != course_idx
            ]

            if other_courses_in_semester:
                # All other courses in this semester must be 0
                model.Add(sum(other_courses_in_semester) == 0)
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
        if status not in ["pin", "banish", "solo"]:
            status = "pin"

        markers.append(Marker(
            course_id=course_id,
            section=section,
            status=status,
        ))

    return markers
