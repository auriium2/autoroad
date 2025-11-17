"""
Test that the tiebreaker prevents taking too many courses.
"""

import polars as pl
import requests
from ortools.sat.python import cp_model

from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.objectives import MaximizeCohortOverlap, MaximizeRating, ObjectiveBuilder
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


def test_with_tiebreaker():
    print("\n" + "="*60)
    print("Testing WITH tiebreaker (default)")
    print("="*60)

    courses_df = fetch_all_courses()
    school_year, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])

    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, planning_year_start)

    # Basic constraints
    for course_idx in courses_df.index:
        course_takes = [take_vars[(course_idx, s)] for s in range(1, 13) if (course_idx, s) in take_vars]
        if course_takes:
            model.Add(sum(course_takes) <= 1)

    for semester in range(1, 13):
        semester_takes = [
            take_vars[(c, semester)] * courses_df[c, 'total_units']
            for c in courses_df.index
            if (c, semester) in take_vars and 'total_units' in courses_df.columns
        ]
        if semester_takes:
            model.Add(sum(semester_takes) <= 48)

    # Add GIRs
    girs_data = fetch_requirement('girs')
    girs_tree = parse_requirement({'reqs': girs_data['reqs'], 'title': 'GIRs'})
    girs_validation = validate_and_prune(girs_tree, courses_df, remove_invalid=False)
    add_requirement_constraints(model, take_vars, girs_validation.pruned_tree, courses_df, planning_year_start, enforce=True)

    # Objective: maximize quality WITHOUT explicit MinimizeUnits
    builder = ObjectiveBuilder()  # Has default tiebreaker=0.001
    builder.add(MaximizeRating(), weight=0.6)
    builder.add(MaximizeCohortOverlap(), weight=0.4)

    print(builder.get_summary())
    objective = builder.build(model, take_vars, courses_df, planning_year_start)
    model.Minimize(objective)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        total_courses = sum(1 for var in take_vars.values() if solver.Value(var) == 1)
        print(f"✓ Solution found: {total_courses} courses")
        return total_courses
    else:
        print("✗ No solution")
        return 0


def test_without_tiebreaker():
    print("\n" + "="*60)
    print("Testing WITHOUT tiebreaker")
    print("="*60)

    courses_df = fetch_all_courses()
    school_year, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])

    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, planning_year_start)

    # Basic constraints
    for course_idx in courses_df.index:
        course_takes = [take_vars[(course_idx, s)] for s in range(1, 13) if (course_idx, s) in take_vars]
        if course_takes:
            model.Add(sum(course_takes) <= 1)

    for semester in range(1, 13):
        semester_takes = [
            take_vars[(c, semester)] * courses_df[c, 'total_units']
            for c in courses_df.index
            if (c, semester) in take_vars and 'total_units' in courses_df.columns
        ]
        if semester_takes:
            model.Add(sum(semester_takes) <= 48)

    # Add GIRs
    girs_data = fetch_requirement('girs')
    girs_tree = parse_requirement({'reqs': girs_data['reqs'], 'title': 'GIRs'})
    girs_validation = validate_and_prune(girs_tree, courses_df, remove_invalid=False)
    add_requirement_constraints(model, take_vars, girs_validation.pruned_tree, courses_df, planning_year_start, enforce=True)

    # Objective: maximize quality WITHOUT tiebreaker
    builder = ObjectiveBuilder(min_units_tiebreaker=0.0)  # Disable tiebreaker
    builder.add(MaximizeRating(), weight=0.6)
    builder.add(MaximizeCohortOverlap(), weight=0.4)

    print(builder.get_summary())
    objective = builder.build(model, take_vars, courses_df, planning_year_start)
    model.Minimize(objective)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        total_courses = sum(1 for var in take_vars.values() if solver.Value(var) == 1)
        print(f"✓ Solution found: {total_courses} courses")
        return total_courses
    else:
        print("✗ No solution")
        return 0


if __name__ == "__main__":
    courses_with = test_with_tiebreaker()
    courses_without = test_without_tiebreaker()

    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"With tiebreaker (default):    {courses_with} courses")
    print(f"Without tiebreaker:           {courses_without} courses")
    print()

    if courses_with < courses_without:
        print("✓ Tiebreaker working correctly - prevents excessive courses")
    else:
        print("✗ Tiebreaker may not be working as expected")
