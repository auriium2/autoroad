"""
Example script demonstrating optimization with user-defined markers.

This shows how to combine:
- Degree requirements (GIRs + major)
- Prerequisites
- User markers (pin, banish, override)
- Objective functions
"""

import json

import polars as pl
import requests
from ortools.sat.python import cp_model

from courses.prerequisites.parser import parse_fireroad
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.marker_constraint_builder import Marker, add_marker_constraints
from optimizer.objectives import (
    FrontloadCourses,
    MaximizeRating,
    MinimizeUnits,
    ObjectiveBuilder,
)
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints
from utils.utils import find_current_school_year, is_valid_class_semester


def fetch_all_courses():
    print("Fetching courses...")
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    data = response.json()
    courses = [c for c in data if not c.get('is_historical')]
    return pl.DataFrame(courses, infer_schema_length=None)


def fetch_requirement(key):
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return resp.json()


def create_take_vars(model, courses_df, planning_year_start):
    take_vars = {}
    for course_idx in courses_df.index:
        subject_id = courses_df[course_idx, 'subject_id']
        for semester in range(1, 13):
            if is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
                var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
                take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)
    return take_vars


def add_basic_constraints(model, take_vars, courses_df):
    # Take each course at most once
    for course_idx in courses_df.index:
        course_takes = [
            take_vars[(course_idx, s)]
            for s in range(1, 13)
            if (course_idx, s) in take_vars
        ]
        if course_takes:
            model.Add(sum(course_takes) <= 1)

    # Max units per semester (48 units)
    for semester in range(1, 13):
        semester_takes = [
            take_vars[(c, semester)] * courses_df[c, 'total_units']
            for c in courses_df.index
            if (c, semester) in take_vars and 'total_units' in courses_df.columns
        ]
        if semester_takes:
            model.Add(sum(semester_takes) <= 48)


def parse_prerequisites_for_all_courses(courses_df):
    prereq_trees = {}
    for course_idx in courses_df.index:
        prereq_str = courses_df[course_idx, 'prerequisites']
        if prereq_str is not None and prereq_str:
            try:
                prereq_tree = parse_fireroad(prereq_str)
                if prereq_tree is not None:
                    prereq_trees[course_idx] = prereq_tree
            except Exception:
                pass
    return prereq_trees


def export_to_road_file(solver, take_vars, courses_df, output_path):
    selected_subjects = []

    for (c, s), v in take_vars.items():
        if solver.Value(v) == 1:
            units = courses_df[c, "total_units"] if "total_units" in courses_df.columns else 12
            units = int(units) if units is not None else 12

            selected_subjects.append({
                "subject_id": str(courses_df[c, "subject_id"]),
                "semester": int(s),
                "title": str(courses_df[c, "title"]) if "title" in courses_df.columns else "",
                "units": units,
                "overrideWarnings": False
            })

    road_data = {
        "coursesOfStudy": [],
        "progressAssertions": {},
        "selectedSubjects": selected_subjects
    }

    with open(output_path, "w") as f:
        json.dump(road_data, f, indent=2)

    print(f"\n✓ Exported solution to {output_path}")
    print(f"Total courses: {len(selected_subjects)}")

    for sem in range(1, 13):
        sem_courses = [s for s in selected_subjects if s['semester'] == sem]
        if sem_courses:
            total_units = sum(s['units'] for s in sem_courses)
            print(f"  Semester {sem}: {len(sem_courses)} courses, {total_units} units")
            for course in sem_courses:
                print(f"    - {course['subject_id']}: {course['title']}")


def optimize_with_markers(major_key: str, markers: list[Marker], output_filename: str):
    """
    Run optimization with user-defined markers.

    Args:
        major_key: Key for the major requirement (e.g., 'major6-3new')
        markers: List of user-defined markers (pin, banish, override)
        output_filename: Name of the output .road file
    """
    print(f"\n{'='*60}")
    print(f"Optimizing for major: {major_key}")
    print(f"Markers: {len(markers)}")
    for marker in markers:
        print(f"  - {marker.course_id} @ section {marker.section} ({marker.status})")
    print(f"{'='*60}\n")

    # Fetch data
    courses_df = fetch_all_courses()
    girs_data = fetch_requirement('girs')
    major_data = fetch_requirement(major_key)

    # Get planning year
    school_year, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])
    print(f"Planning year: {planning_year} (start: {planning_year_start})")

    # Create model
    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, planning_year_start)
    print(f"Created {len(take_vars)} decision variables")

    # Add basic constraints
    add_basic_constraints(model, take_vars, courses_df)
    print("✓ Added basic constraints")

    # Add GIR requirements
    girs_tree = parse_requirement({'reqs': girs_data['reqs'], 'title': 'GIRs'})
    girs_validation = validate_and_prune(girs_tree, courses_df, remove_invalid=False)
    add_requirement_constraints(
        model, take_vars, girs_validation.pruned_tree, courses_df, planning_year_start, enforce=True
    )
    print("✓ Added GIR requirements")

    # Add major requirements
    major_tree = parse_requirement({'reqs': major_data['reqs'], 'title': major_key})
    major_validation = validate_and_prune(major_tree, courses_df, remove_invalid=False)
    add_requirement_constraints(
        model, take_vars, major_validation.pruned_tree, courses_df, planning_year_start, enforce=True
    )
    print("✓ Added major requirements")

    # Add prerequisites
    prereq_trees = parse_prerequisites_for_all_courses(courses_df)
    prereq_result = add_prerequisite_constraints(
        model, take_vars, courses_df, planning_year_start, prereq_trees
    )
    print(f"✓ Added {prereq_result.constraints_added} prerequisite constraints")

    # Add marker constraints
    marker_result = add_marker_constraints(
        model, take_vars, markers, courses_df, planning_year_start
    )
    print(f"✓ Added {marker_result.constraints_added} marker constraints")
    if marker_result.warnings:
        print(f"  Warnings: {len(marker_result.warnings)}")
        for warning in marker_result.warnings[:5]:
            print(f"    - {warning}")
    if marker_result.errors:
        print(f"  Errors: {len(marker_result.errors)}")
        for error in marker_result.errors[:5]:
            print(f"    - {error}")

    # Build objective
    print("\nBuilding objective function...")
    builder = ObjectiveBuilder()
    builder.add(MinimizeUnits(), weight=0.5)
    builder.add(MaximizeRating(target_rating=6.0), weight=0.3)
    builder.add(FrontloadCourses(), weight=0.2)

    print(builder.get_summary())

    objective = builder.build(model, take_vars, courses_df, planning_year_start)
    model.Minimize(objective)

    # Solve
    print("\nSolving...")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0

    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"✓ Solution found (status: {solver.StatusName(status)})")
        print(f"  Solve time: {solver.WallTime():.2f}s")
        print(f"  Objective value: {solver.ObjectiveValue()}")

        # Export to .road file
        export_to_road_file(solver, take_vars, courses_df, output_filename)
    else:
        print(f"✗ No solution found (status: {solver.StatusName(status)})")


if __name__ == "__main__":
    # Example 1: Pin 6.100A to semester 1, banish 18.01
    markers_1 = [
        Marker(course_id="6.100A", section=0, status="pin"),
        Marker(course_id="18.01", section=-1, status="banish"),
    ]
    optimize_with_markers("major6-3new", markers_1, "output_6-3_with_markers.road")

    # Example 2: Override marker for thesis semester
    markers_2 = [
        Marker(course_id="6.UAT", section=11, status="override"),  # Senior spring
    ]
    optimize_with_markers("major6-3new", markers_2, "output_6-3_override_thesis.road")
