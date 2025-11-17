"""
Example: Optimize course schedule with customizable objectives.

This demonstrates how to use the objective builder to create different
optimization profiles.
"""

import concurrent.futures

import polars as pl
import requests
from ortools.sat.python import cp_model

from courses.prerequisites.parser import parse_fireroad
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.objectives import (
    FrontloadCourses,
    MaximizeCohortOverlap,
    MaximizeRating,
    MaximizeWeightedRating,
    MinimizeFinalsLoad,
    MinimizeFridayClasses,
    MinimizeUnits,
    ObjectiveBuilder,
)
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints
from utils.utils import find_current_school_year, is_valid_class_semester


def fetch_all_courses():
    """Fetch all courses from Fireroad API."""
    print("Fetching courses...")
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    data = response.json()
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

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(fetch_requirement, key): key for key in keys}
        results = {key: future.result()[1] for future, key in futures.items()}

    return results


def create_take_vars(model, courses_df, planning_year_start):
    """Create decision variables for taking courses."""
    take_vars = {}

    for course_idx in courses_df.index:
        subject_id = courses_df[course_idx, 'subject_id']

        for semester in range(1, 13):
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
    """Parse prerequisites for all courses."""
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


def optimize_with_objectives(
    major_key: str,
    output_filename: str,
    objective_builder: ObjectiveBuilder
):
    """
    Run optimization for a specific major with custom objectives.

    Args:
        major_key: Key for the major requirement (e.g., 'major6-3new')
        output_filename: Name of the output .road file
        objective_builder: Configured ObjectiveBuilder with desired objectives
    """
    print(f"\n{'='*60}")
    print(f"Optimizing for major: {major_key}")
    print(f"{'='*60}\n")

    # Fetch data
    courses_df = fetch_all_courses()
    requirements_data = fetch_all_requirements()

    # Get planning year
    school_year, planning_year = find_current_school_year()
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
    girs_validation = validate_and_prune(girs_tree, courses_df, remove_invalid=False)
    add_requirement_constraints(
        model, take_vars, girs_validation.pruned_tree, courses_df, planning_year_start, enforce=True
    )

    # Parse and add major requirements
    print(f"\nAdding {major_key} requirements...")
    major_data = requirements_data.get(major_key, {}).get('reqs', [])
    if not major_data:
        print(f"  ERROR: No requirements found for {major_key}")
        return

    major_tree = parse_requirement({'reqs': major_data, 'title': major_key})
    major_validation = validate_and_prune(major_tree, courses_df, remove_invalid=False)
    add_requirement_constraints(
        model, take_vars, major_validation.pruned_tree, courses_df, planning_year_start, enforce=True
    )

    # Parse and add prerequisites
    print("\nAdding prerequisite constraints...")
    prereq_trees = parse_prerequisites_for_all_courses(courses_df)
    add_prerequisite_constraints(
        model, take_vars, courses_df, planning_year_start, prereq_trees
    )

    # Build and set objective
    print("\nBuilding objective function...")
    print(objective_builder.get_summary())
    objective = objective_builder.build(model, take_vars, courses_df, planning_year_start)
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

        # Count courses
        total_courses = sum(1 for var in take_vars.values() if solver.Value(var) == 1)
        print(f"  Total courses: {total_courses}")
    else:
        print(f"✗ No solution found (status: {solver.StatusName(status)})")


if __name__ == "__main__":
    # Example 1: Minimize units
    print("\n" + "="*60)
    print("EXAMPLE 1: Minimum Units")
    print("="*60)

    builder = ObjectiveBuilder()
    builder.add(MinimizeUnits(), weight=1.0)
    optimize_with_objectives("major6-3new", "output_6-3_min_units.road", builder)

    # Example 2: Quality focused
    print("\n" + "="*60)
    print("EXAMPLE 2: Quality Focused")
    print("="*60)

    builder = ObjectiveBuilder()
    builder.add(MinimizeUnits(), weight=0.3)  # Still want to minimize
    builder.add(MaximizeWeightedRating(), weight=0.5)
    builder.add(MaximizeCohortOverlap(), weight=0.2)
    optimize_with_objectives("major6-3new", "output_6-3_quality.road", builder)

    # Example 3: Frontload (graduate early)
    print("\n" + "="*60)
    print("EXAMPLE 3: Frontload (Early Graduation)")
    print("="*60)

    builder = ObjectiveBuilder()
    builder.add(MinimizeUnits(), weight=0.4)
    builder.add(FrontloadCourses(), weight=0.6)
    optimize_with_objectives("major6-3new", "output_6-3_frontload.road", builder)

    # Example 4: Balanced
    print("\n" + "="*60)
    print("EXAMPLE 4: Balanced Approach")
    print("="*60)

    builder = ObjectiveBuilder()
    builder.add(MinimizeUnits(), weight=0.2)
    builder.add(MaximizeRating(), weight=0.25)
    builder.add(FrontloadCourses(), weight=0.15)
    builder.add(MaximizeCohortOverlap(), weight=0.2)
    builder.add(MinimizeFridayClasses(), weight=0.1)
    builder.add(MinimizeFinalsLoad(max_finals=4), weight=0.1)
    optimize_with_objectives("major6-3new", "output_6-3_balanced.road", builder)
