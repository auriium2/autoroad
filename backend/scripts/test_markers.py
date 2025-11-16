"""
Test marker constraint builder.

Verifies that user-defined markers (pin, banish, solo) are correctly
translated into optimization constraints.
"""

import pandas as pd
import requests
from ortools.sat.python import cp_model

from optimizer.marker_constraint_builder import (
    Marker,
    add_marker_constraints,
    parse_markers_from_dict,
)
from utils.utils import find_current_school_year, is_valid_class_semester


def fetch_all_courses():
    print("Fetching courses...")
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    data = response.json()
    courses = [c for c in data if not c.get('is_historical')]
    return pd.DataFrame(courses)


def create_take_vars(model, courses_df, planning_year_start):
    take_vars = {}
    for course_idx in courses_df.index:
        subject_id = courses_df.at[course_idx, 'subject_id']
        for semester in range(1, 13):
            if is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
                var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
                take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)
    return take_vars


def test_pin_marker():
    """Test that pin markers force courses to specific semesters."""
    print("\n" + "="*60)
    print("Test 1: Pin Marker")
    print("="*60)

    courses_df = fetch_all_courses()
    _, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])

    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, planning_year_start)

    # Pin 6.100A to semester 1
    markers = [Marker(course_id="6.100A", section=0, status="pin")]

    result = add_marker_constraints(model, take_vars, markers, courses_df, planning_year_start)

    print(f"Constraints added: {result.constraints_added}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Errors: {len(result.errors)}")

    if result.errors:
        for error in result.errors:
            print(f"  ERROR: {error}")

    # Try to solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        # Find 6.100A in courses_df
        course_6_100A = courses_df[courses_df['subject_id'] == '6.100A'].index[0]

        # Check if it's in semester 1
        if (course_6_100A, 1) in take_vars:
            is_taken_sem1 = solver.Value(take_vars[(course_6_100A, 1)])
            print(f"✓ 6.100A in semester 1: {is_taken_sem1 == 1}")

            # Check it's not in other semesters
            other_semesters = sum(
                solver.Value(take_vars[(course_6_100A, s)])
                for s in range(2, 13)
                if (course_6_100A, s) in take_vars
            )
            print(f"✓ 6.100A in other semesters: {other_semesters == 0}")
        else:
            print("✗ 6.100A not available in semester 1")
    else:
        print(f"✗ Could not solve: {solver.StatusName(status)}")


def test_banish_marker():
    """Test that banish markers prevent courses from being taken."""
    print("\n" + "="*60)
    print("Test 2: Banish Marker")
    print("="*60)

    courses_df = fetch_all_courses()
    _, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])

    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, planning_year_start)

    # Banish 6.100A entirely
    markers = [Marker(course_id="6.100A", section=-1, status="banish")]

    result = add_marker_constraints(model, take_vars, markers, courses_df, planning_year_start)

    print(f"Constraints added: {result.constraints_added}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Errors: {len(result.errors)}")

    # Try to solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        # Find 6.100A in courses_df
        course_6_100A = courses_df[courses_df['subject_id'] == '6.100A'].index[0]

        # Check it's not taken in any semester
        total_taken = sum(
            solver.Value(take_vars[(course_6_100A, s)])
            for s in range(1, 13)
            if (course_6_100A, s) in take_vars
        )
        print(f"✓ 6.100A not taken in any semester: {total_taken == 0}")
    else:
        print(f"✗ Could not solve: {solver.StatusName(status)}")


def test_solo_marker():
    """Test that solo markers force only one course in a semester."""
    print("\n" + "="*60)
    print("Test 3: Solo Marker")
    print("="*60)

    courses_df = fetch_all_courses()
    _, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])

    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, planning_year_start)

    # Mark 6.100A as solo in semester 1
    markers = [Marker(course_id="6.100A", section=0, status="solo")]

    result = add_marker_constraints(model, take_vars, markers, courses_df, planning_year_start)

    print(f"Constraints added: {result.constraints_added}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Errors: {len(result.errors)}")

    # Try to solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        # Find 6.100A in courses_df
        course_6_100A = courses_df[courses_df['subject_id'] == '6.100A'].index[0]

        # Check 6.100A is in semester 1
        if (course_6_100A, 1) in take_vars:
            is_taken_sem1 = solver.Value(take_vars[(course_6_100A, 1)])
            print(f"✓ 6.100A in semester 1: {is_taken_sem1 == 1}")

            # Check no other courses in semester 1
            other_courses_sem1 = sum(
                solver.Value(take_vars[(c, 1)])
                for c in courses_df.index
                if c != course_6_100A and (c, 1) in take_vars
            )
            print(f"✓ No other courses in semester 1: {other_courses_sem1 == 0}")
        else:
            print("✗ 6.100A not available in semester 1")
    else:
        print(f"✗ Could not solve: {solver.StatusName(status)}")


def test_parse_markers_from_dict():
    """Test parsing markers from frontend JSON format."""
    print("\n" + "="*60)
    print("Test 4: Parse Markers from Dict")
    print("="*60)

    markers_data = [
        {"uuid": "marker_1", "courseId": "6.120A", "section": 0, "status": "pin"},
        {"uuid": "marker_2", "courseId": "18.01", "section": -1, "status": "banish"},
        {"uuid": "marker_3", "courseId": "6.100A", "section": 2, "status": "solo"},
    ]

    markers = parse_markers_from_dict(markers_data)

    print(f"Parsed {len(markers)} markers:")
    for marker in markers:
        print(f"  {marker.course_id} @ section {marker.section} ({marker.status})")

    assert len(markers) == 3
    assert markers[0].course_id == "6.120A"
    assert markers[0].section == 0
    assert markers[0].status == "pin"

    assert markers[1].course_id == "18.01"
    assert markers[1].status == "banish"

    assert markers[2].course_id == "6.100A"
    assert markers[2].status == "solo"

    print("✓ All assertions passed")


if __name__ == "__main__":
    test_parse_markers_from_dict()
    test_pin_marker()
    test_banish_marker()
    test_solo_marker()

    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
