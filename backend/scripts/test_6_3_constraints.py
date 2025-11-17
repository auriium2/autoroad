"""
Test that 6-3 constraint building works without errors.
"""

import polars as pl
import requests
from ortools.sat.python import cp_model

from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
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
    print(f"Fetching requirement: {key}")
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return resp.json()


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


def main():
    # Fetch data
    courses_df = fetch_all_courses()
    print(f"Fetched {len(courses_df)} courses")

    # Get planning year
    school_year, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])
    print(f"Planning year: {planning_year}")

    # Create model and variables
    print("\nCreating CP-SAT model...")
    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, planning_year_start)
    print(f"Created {len(take_vars)} decision variables")

    # Fetch and parse 6-3 requirements
    print("\nFetching 6-3 requirements...")
    major_data = fetch_requirement('major6-3new')
    major_tree = parse_requirement({'reqs': major_data['reqs'], 'title': 'major6-3new'})

    # Validate
    print("Validating requirements...")
    major_validation = validate_and_prune(major_tree, courses_df, remove_invalid=False)
    print(f"  Is feasible: {major_validation.is_feasible}")
    print(f"  Removed courses: {len(major_validation.removed_courses)}")

    # Build constraints
    print("\nBuilding constraints (this is where the bug was)...")
    try:
        aux_vars, var_map = add_requirement_constraints(
            model, take_vars, major_validation.pruned_tree, courses_df, planning_year_start, enforce=False
        )
        print(f"✓ Successfully built {len(aux_vars)} constraint variables")
        print("✓ No errors during constraint building!")

        # Try to enforce them
        print("\nTrying to enforce constraints...")
        aux_vars2, var_map2 = add_requirement_constraints(
            model, take_vars, major_validation.pruned_tree, courses_df, planning_year_start, enforce=True
        )
        print("✓ Successfully enforced constraints!")

    except ValueError as e:
        print(f"✗ ERROR during constraint building: {e}")
        return 1

    print("\n" + "="*60)
    print("SUCCESS: 6-3 constraints can be built and enforced!")
    print("="*60)
    return 0


if __name__ == "__main__":
    exit(main())
