"""
Test improved objective implementations:
1. Rating objectives with target thresholds (not 7.0 baseline)
2. MinimizeTotalHours vs MinimizeMaxSemesterHours
3. Improved ClusterCourses with actual time parsing
"""

import polars as pl
import requests
from ortools.sat.python import cp_model

from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.objectives import (
    ClusterCourses,
    MaximizeRating,
    MinimizeMaxSemesterHours,
    MinimizeTotalHours,
    MinimizeUnits,
    ObjectiveBuilder,
)
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


def run_optimization_test(name, builder, courses_df, planning_year_start):
    """Run a single optimization test configuration."""
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print(f"{'='*60}")

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

    # Build objective
    print(builder.get_summary())
    objective = builder.build(model, take_vars, courses_df, planning_year_start)
    model.Minimize(objective)

    # Solve
    print("\nSolving...")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15.0
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        total_courses = sum(1 for var in take_vars.values() if solver.Value(var) == 1)
        print(f"✓ Solution: {total_courses} courses, objective={solver.ObjectiveValue()}")

        # Analyze per-semester hours if relevant
        if 'in_class_hours' in courses_df.columns:
            for sem in range(1, 13):
                courses_in_sem = [
                    (courses_df[c, 'subject_id'],
                     courses_df[c, 'in_class_hours'] if courses_df[c, 'in_class_hours'] is not None else 0,
                     courses_df[c, 'out_of_class_hours'] if courses_df[c, 'out_of_class_hours'] is not None else 0)
                    for c, s in take_vars.keys()
                    if s == sem and solver.Value(take_vars[(c, s)]) == 1
                ]
                if courses_in_sem:
                    total_hours = sum(in_h + out_h for _, in_h, out_h in courses_in_sem)
                    print(f"  Semester {sem}: {len(courses_in_sem)} courses, {total_hours:.1f} hours/week")
    else:
        print(f"✗ No solution: {solver.StatusName(status)}")


def main():
    courses_df = fetch_all_courses()
    print(f"Fetched {len(courses_df)} courses")

    school_year, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])

    # Test 1: Rating with new baseline (6.0 instead of 7.0)
    builder1 = ObjectiveBuilder()
    builder1.add(MinimizeUnits(), weight=0.3)
    builder1.add(MaximizeRating(target_rating=6.0), weight=0.7)
    run_optimization_test(
        "MaximizeRating with target=6.0",
        builder1, courses_df, planning_year_start
    )

    # Test 2: MinimizeTotalHours
    builder2 = ObjectiveBuilder()
    builder2.add(MinimizeUnits(), weight=0.3)
    builder2.add(MinimizeTotalHours(), weight=0.7)
    run_optimization_test(
        "MinimizeTotalHours (linear objective)",
        builder2, courses_df, planning_year_start
    )

    # Test 3: MinimizeMaxSemesterHours (soft constraint)
    builder3 = ObjectiveBuilder()
    builder3.add(MinimizeUnits(), weight=0.5)
    builder3.add(MinimizeMaxSemesterHours(max_hours=50.0, penalty=1000), weight=0.5)
    run_optimization_test(
        "MinimizeMaxSemesterHours (soft constraint, max=50)",
        builder3, courses_df, planning_year_start
    )

    # Test 4: ClusterCourses with improved implementation
    builder4 = ObjectiveBuilder()
    builder4.add(MinimizeUnits(), weight=0.7)
    builder4.add(ClusterCourses(gap_penalty_per_hour=50), weight=0.3)
    run_optimization_test(
        "ClusterCourses with actual time parsing",
        builder4, courses_df, planning_year_start
    )

    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)


if __name__ == "__main__":
    main()
