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


# Maps marker courseId -> (df_column, attr_value)
VIRTUAL_MARKER_ATTRS: dict[str, tuple[str, str]] = {
    "HASS-A": ("hass_attribute", "HASS-A"),
    "HASS-H": ("hass_attribute", "HASS-H"),
    "HASS-S": ("hass_attribute", "HASS-S"),
    "HASS-E": ("hass_attribute", "HASS-E"),
    "GIR:BIOL": ("gir_attribute", "BIOL"),
    "GIR:CAL1": ("gir_attribute", "CAL1"),
    "GIR:CAL2": ("gir_attribute", "CAL2"),
    "GIR:CHEM": ("gir_attribute", "CHEM"),
    "GIR:LAB":  ("gir_attribute", "LAB"),
    "GIR:LAB2": ("gir_attribute", "LAB2"),
    "GIR:PHY1": ("gir_attribute", "PHY1"),
    "GIR:PHY2": ("gir_attribute", "PHY2"),
    "GIR:REST": ("gir_attribute", "REST"),
}

VIRTUAL_COURSE_IDS = set(VIRTUAL_MARKER_ATTRS.keys())


def is_virtual_marker(course_id: str) -> bool:
    return course_id in VIRTUAL_COURSE_IDS


def get_virtual_marker_attr(course_id: str) -> tuple[str, str] | None:
    """Return (column_name, attr_value) for a virtual marker, or None if not virtual."""
    return VIRTUAL_MARKER_ATTRS.get(course_id)


class MarkerCache:
    _instance_id: int | None = None
    _course_id_to_idx: dict[str, int] = {}
    _virtual_id_to_indices: dict[str, list[int]] = {}

    @classmethod
    def get(cls, courses_df: pl.DataFrame) -> tuple[dict[str, int], dict[str, list[int]]]:
        df_id = id(courses_df)
        if cls._instance_id != df_id:
            course_id_to_idx = {}
            subject_ids = courses_df['subject_id'].to_list()
            for idx, subject_id in enumerate(subject_ids):
                course_id_to_idx[subject_id] = idx

            virtual_id_to_indices = {}
            for marker_id, (col, val) in VIRTUAL_MARKER_ATTRS.items():
                if col in courses_df.columns:
                    col_vals = courses_df[col].to_list()
                    indices = [idx for idx, v in enumerate(col_vals) if v == val]
                    virtual_id_to_indices[marker_id] = indices
                else:
                    virtual_id_to_indices[marker_id] = []

            cls._course_id_to_idx = course_id_to_idx
            cls._virtual_id_to_indices = virtual_id_to_indices
            cls._instance_id = df_id

        return cls._course_id_to_idx, cls._virtual_id_to_indices


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

    course_id_to_idx, virtual_id_to_indices = MarkerCache.get(courses_df)

    # Count virtual pin markers by (marker_id, section)
    virtual_pin_counts: Counter[tuple[str, int]] = Counter()
    virtual_banish_markers: list[tuple[str, int]] = []

    for marker in markers:
        if is_virtual_marker(marker.courseId):
            if marker.status == "pin":
                if marker.section == -2:
                    errors.append(f"{marker.courseId} markers cannot be placed in Must Take section")
                else:
                    virtual_pin_counts[(marker.courseId, marker.section)] += 1
            elif marker.status == "banish":
                virtual_banish_markers.append((marker.courseId, marker.section))
            elif marker.status == "override":
                errors.append(f"Override is not supported for generic {marker.courseId} markers")
            continue

    # Add constraints for virtual pin markers (grouped by marker_id and section)
    for (marker_id, section), count in virtual_pin_counts.items():
        matching_indices = virtual_id_to_indices.get(marker_id, [])

        if not matching_indices:
            errors.append(f"No courses found with {marker_id} attribute")
            continue

        if section == -1:
            semester_vars = [
                take_vars[(idx, -1)]
                for idx in matching_indices
                if (idx, -1) in take_vars
            ]
            if semester_vars:
                model.Add(sum(semester_vars) >= count)
                constraints_added += 1
            else:
                errors.append(f"No {marker_id} courses available in ASE semester")
        elif section >= 0:
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
                errors.append(f"No {marker_id} courses available in semester {semester}")

    # Add constraints for virtual banish markers
    for marker_id, section in virtual_banish_markers:
        matching_indices = virtual_id_to_indices.get(marker_id, [])

        if section < 0:
            errors.append(f"Cannot banish {marker_id} from special semesters")
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
    print(f"[Markers] Added {constraints_added} constraints in {total_time:.3f}s")

    return MarkerConstraintResult(
        constraints_added=constraints_added,
        warnings=warnings,
        errors=errors,
    )
