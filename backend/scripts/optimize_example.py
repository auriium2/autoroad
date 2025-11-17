"""
Example script demonstrating the new optimizer modules.

This replaces the old analyze.py script with a cleaner implementation using:
- optimizer/requirement_constraint_builder.py for degree requirements
- optimizer/prerequisite_constraint_builder.py for prerequisites
- courses/requirements/parser.py for parsing requirements
- courses/prerequisites/parser.py for parsing prerequisites
"""

import concurrent.futures
import json
from pathlib import Path

import polars as pl
import requests
from ortools.sat.python import cp_model

from courses.prerequisites.parser import parse_fireroad
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints
from utils.utils import find_current_school_year, is_valid_class_semester


def fetch_all_courses():
    """Fetch all courses from Fireroad API."""
    print("Fetching courses...")
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    data = response.json()

    # Filter out historical courses
    courses = [c for c in data if not c.get('is_historical')]
    return pl.DataFrame(courses, infer_schema_length=None)


def fetch_requirement(key):
    """Fetch a single requirement from Fireroad API."""
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return key, resp.json()


def fetch_all_requirements():
    """Fetch all requirements from Fireroad API."""
    print("Fetching requirements...")
    response = requests.get('https://fireroad.mit.edu/requirements/list_reqs')
    response.raise_for_status()
    keys = response.json().keys()

    # Fetch in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(fetch_requirement, key): key for key in keys}
        results = {key: future.result()[1] for future, key in futures.items()}

    return results


def create_take_vars(model, courses_df, planning_year_start):
    """
    Create decision variables for taking courses.

    Returns:
        dict mapping (course_idx, semester) -> BoolVar
    """
    take_vars = {}

    for course_idx in courses_df.index:
        subject_id = courses_df[course_idx, 'subject_id']

        for semester in range(1, 13):
            # Only create variable if course is offered in this semester
            if is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
                var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
                take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)

    return take_vars


def add_basic_constraints(model, take_vars, courses_df):
    """Add basic constraints like max units per semester, taking course once, etc."""

    # Constraint: Take each course at most once
    for course_idx in courses_df.index:
        course_takes = [
            take_vars[(course_idx, s)]
            for s in range(1, 13)
            if (course_idx, s) in take_vars
        ]
        if course_takes:
            model.Add(sum(course_takes) <= 1)

    # Constraint: Max units per semester (48 units)
    for semester in range(1, 13):
        semester_takes = [
            take_vars[(c, semester)] * courses_df[c, 'total_units']
            for c in courses_df.index
            if (c, semester) in take_vars and 'total_units' in courses_df.columns
        ]
        if semester_takes:
            model.Add(sum(semester_takes) <= 48)


def parse_prerequisites_for_all_courses(courses_df):
    """
    Parse prerequisites for all courses.

    Returns:
        dict mapping course_idx -> PrereqNode
    """
    prereq_trees = {}

    for course_idx in courses_df.index:
        prereq_str = courses_df[course_idx, 'prerequisites']

        if prereq_str is not None and prereq_str:
            try:
                prereq_tree = parse_fireroad(prereq_str)
                if prereq_tree is not None:
                    prereq_trees[course_idx] = prereq_tree
            except Exception as e:
                print(f"Warning: Failed to parse prerequisites for {courses_df[course_idx, 'subject_id']}: {e}")

    return prereq_trees


def export_to_road_file(solver, take_vars, courses_df, output_path):
    """Export the solution to a .road file."""
    selected_subjects = []

    for (c, s), v in take_vars.items():
        if solver.Value(v) == 1:
            # Convert numpy types to Python native types for JSON serialization
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

    # Ensure directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(road_data, f, indent=2)

    print(f"Exported solution to {output_path}")
    print(f"Total courses: {len(selected_subjects)}")

    # Print summary by semester
    for sem in range(1, 13):
        sem_courses = [s for s in selected_subjects if s['semester'] == sem]
        if sem_courses:
            total_units = sum(s['units'] for s in sem_courses)
            print(f"  Semester {sem}: {len(sem_courses)} courses, {total_units} units")


def optimize_for_major(major_key, output_filename):
    """
    Run optimization for a specific major.

    Args:
        major_key: Key for the major requirement (e.g., 'major6-3new', 'major2', 'major15')
        output_filename: Name of the output .road file
    """
    print(f"\n{'='*60}")
    print(f"Optimizing for major: {major_key}")
    print(f"{'='*60}\n")

    # Fetch data
    courses_df = fetch_all_courses()
    requirements_data = fetch_all_requirements()

    # Get planning year
    school_year, planning_year = find_current_school_year()
    # Extract the starting year as an integer (e.g., "2026-2027" -> 2026)
    planning_year_start = int(planning_year.split('-')[0])
    print(f"Planning year: {planning_year} (start: {planning_year_start})")

    # Create model
    model = cp_model.CpModel()

    # Create decision variables
    take_vars = create_take_vars(model, courses_df, planning_year_start)
    print(f"Created {len(take_vars)} decision variables")

    # Add basic constraints
    add_basic_constraints(model, take_vars, courses_df)
    print("Added basic constraints (max units, take once)")

    # Parse and add GIR requirements
    print("\nAdding GIR requirements...")
    girs_data = requirements_data.get('girs', {}).get('reqs', [])
    girs_tree = parse_requirement({'reqs': girs_data, 'title': 'GIRs'})

    # Validate and prune invalid courses
    girs_validation = validate_and_prune(girs_tree, courses_df, remove_invalid=False)
    if girs_validation.warnings:
        print(f"  Validation warnings: {len(girs_validation.warnings)}")
    if girs_validation.removed_courses:
        print(f"  Pruned courses: {len(girs_validation.removed_courses)}")

    aux_vars_girs, var_map_girs = add_requirement_constraints(
        model, take_vars, girs_validation.pruned_tree, courses_df, planning_year_start, enforce=True
    )
    print(f"  Added {len(aux_vars_girs)} GIR requirement variables")

    # Parse and add major requirements
    print(f"\nAdding {major_key} requirements...")
    major_data = requirements_data.get(major_key, {}).get('reqs', [])
    if not major_data:
        print(f"  ERROR: No requirements found for {major_key}")
        return

    major_tree = parse_requirement({'reqs': major_data, 'title': major_key})

    # Validate and prune invalid courses
    major_validation = validate_and_prune(major_tree, courses_df, remove_invalid=False)
    if major_validation.warnings:
        print(f"  Validation warnings: {len(major_validation.warnings)}")
    if major_validation.removed_courses:
        print(f"  Pruned courses: {len(major_validation.removed_courses)}")

    aux_vars_major, var_map_major = add_requirement_constraints(
        model, take_vars, major_validation.pruned_tree, courses_df, planning_year_start, enforce=True
    )
    print(f"  Added {len(aux_vars_major)} major requirement variables")

    # Parse and add prerequisites
    print("\nAdding prerequisite constraints...")
    prereq_trees = parse_prerequisites_for_all_courses(courses_df)
    prereq_result = add_prerequisite_constraints(
        model, take_vars, courses_df, planning_year_start, prereq_trees
    )
    print(f"  Added {prereq_result.constraints_added} prerequisite constraints")
    if prereq_result.warnings:
        print(f"  Warnings: {len(prereq_result.warnings)}")
    if prereq_result.errors:
        print(f"  Errors: {len(prereq_result.errors)}")

    # Solve
    print("\nSolving...")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0

    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"✓ Solution found (status: {solver.StatusName(status)})")
        print(f"  Solve time: {solver.WallTime():.2f}s")

        # Export to .road file
        export_to_road_file(solver, take_vars, courses_df, output_filename)
    else:
        print(f"✗ No solution found (status: {solver.StatusName(status)})")
        if status == cp_model.INFEASIBLE:
            print("  The problem is infeasible - requirements cannot be satisfied")
        elif status == cp_model.MODEL_INVALID:
            print("  The model is invalid")


if __name__ == "__main__":
    # Optimize for course 6-3
    optimize_for_major("major6-3new", "output_6-3.road")

    # Optimize for course 2
    optimize_for_major("major2", "output_2.road")

    # Optimize for course 15
    optimize_for_major("major15", "output_15.road")
