"""
Quick test to check if 6-3 requirements are feasible after the fix.
"""

import pandas as pd
import requests

from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune


def fetch_all_courses():
    """Fetch all courses from Fireroad API."""
    print("Fetching courses...")
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    data = response.json()

    # Filter out historical courses
    courses = [c for c in data if not c.get('is_historical')]
    return pd.DataFrame(courses)


def fetch_requirement(key):
    """Fetch a single requirement from Fireroad API."""
    print(f"Fetching requirement: {key}")
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return resp.json()


def main():
    # Fetch data
    courses_df = fetch_all_courses()
    print(f"Fetched {len(courses_df)} courses")

    # Fetch 6-3 requirements
    major_data = fetch_requirement('major6-3new')

    # Parse requirements
    print("\nParsing 6-3 requirements...")
    major_tree = parse_requirement({'reqs': major_data['reqs'], 'title': 'major6-3new'})

    # Validate and check feasibility
    print("\nValidating 6-3 requirements...")
    validation = validate_and_prune(major_tree, courses_df, remove_invalid=False)

    print(f"\n{'='*60}")
    print("VALIDATION RESULTS FOR COURSE 6-3")
    print(f"{'='*60}")
    print(f"Is Feasible: {validation.is_feasible}")
    print(f"Removed Courses: {len(validation.removed_courses)}")
    print(f"Warnings: {len(validation.warnings)}")

    if validation.warnings:
        print("\nSample warnings (first 5):")
        for warning in validation.warnings[:5]:
            print(f"  - {warning}")

    if validation.is_feasible:
        print("\n✓ Course 6-3 is FEASIBLE")
    else:
        print("\n✗ Course 6-3 is INFEASIBLE")
        print("\nThis is unexpected! Printing all warnings:")
        for warning in validation.warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()
