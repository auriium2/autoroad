"""
Example usage of the RequirementConstraintBuilder.

This demonstrates how to use the new constraint builder instead of the
monolithic add_requirement_constraints function from analyze.py.
"""

import pandas as pd
from ortools.sat.python import cp_model

from .constraint_builder import add_requirement_constraints
from .types import RequirementCourse, RequirementGroup, RequirementThreshold


def example_simple_requirement():
    """Example: A simple course requirement."""
    # Create a model and decision variables
    model = cp_model.CpModel()
    courses_df = pd.DataFrame({
        'subject_id': ['6.100A', '6.1200', '18.01'],
        'total_units': [12, 12, 12],
    })
    
    # Create take variables for each course and semester
    take_vars = {}
    for course_idx in courses_df.index:
        for semester in range(1, 13):
            var_name = f"take_{courses_df.loc[course_idx, 'subject_id']}_{semester}"
            take_vars[course_idx, semester] = model.NewBoolVar(var_name)
    
    # Create a simple requirement: must take 6.100A
    requirement = RequirementCourse(course_id="6.100A", title="Introduction to Programming")
    
    # Add constraints
    aux_vars = add_requirement_constraints(
        model=model,
        take_vars=take_vars,
        requirement=requirement,
        courses_df=courses_df,
        planning_year_start=2024,
        enforce=True  # Require this course to be taken
    )
    
    print("Simple requirement constraints added successfully")
    return model, aux_vars


def example_choice_requirement():
    """Example: A requirement with choices (any of several courses)."""
    model = cp_model.CpModel()
    courses_df = pd.DataFrame({
        'subject_id': ['6.100A', '6.100L', '6.1200', '6.120A'],
        'total_units': [12, 12, 12, 12],
    })
    
    take_vars = {}
    for course_idx in courses_df.index:
        for semester in range(1, 13):
            var_name = f"take_{courses_df.loc[course_idx, 'subject_id']}_{semester}"
            take_vars[course_idx, semester] = model.NewBoolVar(var_name)
    
    # Create a choice requirement: take either 6.100A or 6.100L
    requirement = RequirementGroup(
        items=(
            RequirementCourse(course_id="6.100A", title="Intro to CS (Python)"),
            RequirementCourse(course_id="6.100L", title="Intro to CS (Lab)"),
        ),
        connection_type="any",
        title="Intro Programming"
    )
    
    aux_vars = add_requirement_constraints(
        model=model,
        take_vars=take_vars,
        requirement=requirement,
        courses_df=courses_df,
        planning_year_start=2024,
        enforce=True
    )
    
    print("Choice requirement constraints added successfully")
    print(f"Auxiliary variables: {list(aux_vars.keys())}")
    return model, aux_vars


def example_threshold_requirement():
    """Example: A requirement with a threshold (choose N of M courses)."""
    model = cp_model.CpModel()
    courses_df = pd.DataFrame({
        'subject_id': ['6.3100', '6.3200', '6.3300', '6.3400', '6.3500'],
        'total_units': [12, 12, 12, 12, 12],
    })
    
    take_vars = {}
    for course_idx in courses_df.index:
        for semester in range(1, 13):
            var_name = f"take_{courses_df.loc[course_idx, 'subject_id']}_{semester}"
            take_vars[course_idx, semester] = model.NewBoolVar(var_name)
    
    # Create a threshold requirement: take at least 2 of these 5 courses
    requirement = RequirementGroup(
        items=(
            RequirementCourse(course_id="6.3100"),
            RequirementCourse(course_id="6.3200"),
            RequirementCourse(course_id="6.3300"),
            RequirementCourse(course_id="6.3400"),
            RequirementCourse(course_id="6.3500"),
        ),
        connection_type="any",
        threshold=RequirementThreshold(cutoff=2, criterion="subjects", type="GTE"),
        title="Advanced Electives"
    )
    
    aux_vars = add_requirement_constraints(
        model=model,
        take_vars=take_vars,
        requirement=requirement,
        courses_df=courses_df,
        planning_year_start=2024,
        enforce=True
    )
    
    print("Threshold requirement constraints added successfully")
    return model, aux_vars


def example_nested_requirement():
    """Example: A nested requirement structure (groups within groups)."""
    model = cp_model.CpModel()
    courses_df = pd.DataFrame({
        'subject_id': ['6.100A', '6.100L', '6.1200', '6.120A', '6.1210', '18.01', '18.02'],
        'total_units': [12, 12, 12, 12, 12, 12, 12],
    })
    
    take_vars = {}
    for course_idx in courses_df.index:
        for semester in range(1, 13):
            var_name = f"take_{courses_df.loc[course_idx, 'subject_id']}_{semester}"
            take_vars[course_idx, semester] = model.NewBoolVar(var_name)
    
    # Create a nested requirement structure
    requirement = RequirementGroup(
        items=(
            # First: Choose one intro programming course
            RequirementGroup(
                items=(
                    RequirementCourse(course_id="6.100A"),
                    RequirementCourse(course_id="6.100L"),
                ),
                connection_type="any",
                title="Intro Programming"
            ),
            # Second: Choose one discrete math course
            RequirementGroup(
                items=(
                    RequirementCourse(course_id="6.1200"),
                    RequirementCourse(course_id="6.120A"),
                ),
                connection_type="any",
                title="Discrete Math"
            ),
            # Third: Must take this specific course
            RequirementCourse(course_id="6.1210", title="Computation Structures"),
            # Fourth: Must take both math courses
            RequirementGroup(
                items=(
                    RequirementCourse(course_id="18.01"),
                    RequirementCourse(course_id="18.02"),
                ),
                connection_type="all",
                title="Calculus"
            ),
        ),
        connection_type="all",
        title="Foundation Courses"
    )
    
    aux_vars = add_requirement_constraints(
        model=model,
        take_vars=take_vars,
        requirement=requirement,
        courses_df=courses_df,
        planning_year_start=2024,
        enforce=True
    )
    
    print("Nested requirement constraints added successfully")
    print(f"Created {len(aux_vars)} auxiliary variables")
    return model, aux_vars


def example_with_special_requirements():
    """Example: Using special requirements (GIRs, HASS, etc)."""
    model = cp_model.CpModel()
    courses_df = pd.DataFrame({
        'subject_id': ['8.01', '8.02', '5.111', '18.01'],
        'total_units': [12, 12, 12, 12],
        'gir_attribute': ['PHY1', 'PHY2', 'CHEM', 'CAL1'],
    })
    
    take_vars = {}
    for course_idx in courses_df.index:
        for semester in range(1, 13):
            var_name = f"take_{courses_df.loc[course_idx, 'subject_id']}_{semester}"
            take_vars[course_idx, semester] = model.NewBoolVar(var_name)
    
    # Create requirements using GIR codes
    requirement = RequirementGroup(
        items=(
            RequirementCourse(course_id="GIR:PHY1", title="Physics I"),
            RequirementCourse(course_id="GIR:PHY2", title="Physics II"),
            RequirementCourse(course_id="GIR:CHEM", title="Chemistry"),
            RequirementCourse(course_id="GIR:CAL1", title="Calculus I"),
        ),
        connection_type="all",
        title="General Institute Requirements"
    )
    
    aux_vars = add_requirement_constraints(
        model=model,
        take_vars=take_vars,
        requirement=requirement,
        courses_df=courses_df,
        planning_year_start=2024,
        enforce=True
    )
    
    print("Special requirements constraints added successfully")
    return model, aux_vars


if __name__ == "__main__":
    print("=== Example 1: Simple Requirement ===")
    example_simple_requirement()
    print()
    
    print("=== Example 2: Choice Requirement ===")
    example_choice_requirement()
    print()
    
    print("=== Example 3: Threshold Requirement ===")
    example_threshold_requirement()
    print()
    
    print("=== Example 4: Nested Requirement ===")
    example_nested_requirement()
    print()
    
    print("=== Example 5: Special Requirements ===")
    example_with_special_requirements()
    print()
    
    print("All examples completed successfully!")
