"""
Test script for objective functions.

Demonstrates how to use the objective builder with various objectives.
"""

import pandas as pd
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
    return pd.DataFrame(courses)


def fetch_requirement(key):
    """Fetch a single requirement from Fireroad API."""
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return resp.json()


def create_take_vars(model, courses_df, planning_year_start):
    """Create decision variables for taking courses."""
    take_vars = {}

    for course_idx in courses_df.index:
        subject_id = courses_df.at[course_idx, 'subject_id']

        for semester in range(1, 13):
            if is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
                var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
                take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)

    return take_vars


def test_objective_composition():
    """Test composing multiple objectives."""
    print("\n" + "="*60)
    print("Testing Objective Composition")
    print("="*60)

    # Create builder
    builder = ObjectiveBuilder()

    # Add various objectives
    builder.add(MinimizeUnits(), weight=0.2)
    builder.add(MaximizeRating(), weight=0.3)
    builder.add(FrontloadCourses(), weight=0.15)
    builder.add(MaximizeCohortOverlap(), weight=0.2)
    builder.add(MinimizeFridayClasses(penalty=100), weight=0.15)

    # Print summary
    print("\n" + builder.get_summary())
    print("\n✓ Objective composition successful")


def test_optimization_with_objectives():
    """Test running optimization with composed objectives."""
    print("\n" + "="*60)
    print("Testing Optimization with Objectives")
    print("="*60)

    # Fetch data
    courses_df = fetch_all_courses()
    print(f"Fetched {len(courses_df)} courses")

    # Get planning year
    school_year, planning_year = find_current_school_year()
    planning_year_start = int(planning_year.split('-')[0])
    print(f"Planning year: {planning_year}")

    # Create model
    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, planning_year_start)
    print(f"Created {len(take_vars)} decision variables")

    # Add basic constraints (max units, take once)
    for course_idx in courses_df.index:
        course_takes = [
            take_vars[(course_idx, s)]
            for s in range(1, 13)
            if (course_idx, s) in take_vars
        ]
        if course_takes:
            model.Add(sum(course_takes) <= 1)

    for semester in range(1, 13):
        semester_takes = [
            take_vars[(c, semester)] * courses_df.at[c, 'total_units']
            for c in courses_df.index
            if (c, semester) in take_vars and 'total_units' in courses_df.columns
        ]
        if semester_takes:
            model.Add(sum(semester_takes) <= 48)

    print("Added basic constraints")

    # Fetch and add GIR requirements
    print("\nAdding GIR requirements...")
    girs_data = fetch_requirement('girs')
    girs_tree = parse_requirement({'reqs': girs_data['reqs'], 'title': 'GIRs'})
    girs_validation = validate_and_prune(girs_tree, courses_df, remove_invalid=False)

    add_requirement_constraints(
        model, take_vars, girs_validation.pruned_tree, courses_df, planning_year_start, enforce=True
    )

    # Add prerequisites
    print("Adding prerequisite constraints...")
    prereq_trees = {}
    for course_idx in courses_df.index:
        prereq_str = courses_df.at[course_idx, 'prerequisites']
        if pd.notna(prereq_str) and prereq_str:
            try:
                prereq_tree = parse_fireroad(prereq_str)
                if prereq_tree is not None:
                    prereq_trees[course_idx] = prereq_tree
            except Exception:
                pass

    add_prerequisite_constraints(
        model, take_vars, courses_df, planning_year_start, prereq_trees
    )

    # Build objective with different weight configurations
    test_configs = [
        {
            'name': 'Minimize Units Only',
            'weights': [(MinimizeUnits(), 1.0)]
        },
        {
            'name': 'Maximize Quality (Rating + Cohort)',
            'weights': [
                (MaximizeRating(), 0.6),
                (MaximizeCohortOverlap(), 0.4)
            ]
        },
        {
            'name': 'Balanced Approach',
            'weights': [
                (MinimizeUnits(), 0.2),
                (MaximizeWeightedRating(), 0.3),
                (FrontloadCourses(), 0.2),
                (MaximizeCohortOverlap(), 0.2),
                (MinimizeFridayClasses(), 0.1)
            ]
        }
    ]

    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"Configuration: {config['name']}")
        print(f"{'='*60}")

        # Build objective
        builder = ObjectiveBuilder()
        for component, weight in config['weights']:
            builder.add(component, weight=weight)

        print(builder.get_summary())

        # Build and set objective
        objective = builder.build(model, take_vars, courses_df, planning_year_start)
        model.Minimize(objective)

        # Solve (with short timeout since we're just testing)
        print("\nSolving...")
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0

        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print(f"✓ Solution found (status: {solver.StatusName(status)})")
            print(f"  Solve time: {solver.WallTime():.2f}s")
            print(f"  Objective value: {solver.ObjectiveValue()}")

            # Count courses
            total_courses = sum(1 for var in take_vars.values() if solver.Value(var) == 1)
            print(f"  Total courses: {total_courses}")
        else:
            print(f"✗ No solution found (status: {solver.StatusName(status)})")

        print()


if __name__ == "__main__":
    test_objective_composition()
    test_optimization_with_objectives()

    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
