#!/usr/bin/env python3
"""
analyze_api.py - API integration script for Autoroad

This script serves as a bridge between the frontend and the analyzer backend.
It accepts input from the frontend through JSON files, runs the optimization,
and returns the results in a format the frontend can use.
"""

import argparse
import json
import sys
import os
import requests
import pandas as pd
from ortools.sat.python import cp_model
from datetime import datetime
import traceback

# Import analyzer functions
from analyze import (
    fetch_requirement,
    add_requirement_constraints,
    add_prerequisite_constraints,
    process_prereq_condition,
    VarArraySolutionPrinter,
    export_take_blocks_to_road
)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Course road optimizer API integration')
    parser.add_argument('--input', type=str, required=True, help='Input JSON file with sections and constraints')
    parser.add_argument('--output', type=str, required=True, help='Output JSON file for optimized road')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    return parser.parse_args()

def load_courses_data():
    """Load courses data from FireRoad API"""
    try:
        response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching course data: {e}", file=sys.stderr)
        raise

def load_requirements_data():
    """Load requirements data from FireRoad API"""
    try:
        response = requests.get('https://fireroad.mit.edu/requirements/list_reqs')
        response.raise_for_status()
        reqs_list = response.json()
        
        # Fetch individual requirement details
        results = {}
        for key in reqs_list.keys():
            req_key, req_data = fetch_requirement(key)
            results[req_key] = req_data
            
        return results
    except Exception as e:
        print(f"Error fetching requirements data: {e}", file=sys.stderr)
        raise

def generate_sections_from_solution(solver, take, courses_df, input_sections):
    """Generate section data from the optimization solution"""
    sections = []
    
    # Create a mapping of course IDs to semester assignments
    course_assignments = {}
    for (course_id, semester), var in take.items():
        if solver.Value(var) != 0:
            course_assignments[course_id] = semester
    
    # Create sections based on input structure but with optimized courses
    semester_to_courses = {}
    for (course_id, semester), var in take.items():
        if solver.Value(var) != 0:
            if semester not in semester_to_courses:
                semester_to_courses[semester] = []
            
            # Get course details from the DataFrame
            subject_id = courses_df.loc[course_id, "subject_id"]
            title = courses_df.loc[course_id, "title"] if "title" in courses_df.columns else f"Course {subject_id}"
            
            semester_to_courses[semester].append({
                "id": subject_id,
                "label": subject_id,
                "section": semester,
                "title": title
            })
    
    # Map input sections to output sections
    for section in input_sections:
        section_id = section.get('id')
        if section_id in semester_to_courses:
            sections.append({
                "id": section_id,
                "title": section.get('title', f"Semester {section_id}"),
                "nodes": semester_to_courses[section_id]
            })
        else:
            # Include empty sections
            sections.append({
                "id": section_id,
                "title": section.get('title', f"Semester {section_id}"),
                "nodes": []
            })
    
    return sections

def generate_edges_from_solution(solver, take, courses_df):
    """Generate edge data from the optimization solution"""
    edges = []
    
    # Get all courses that are part of the solution
    selected_courses = set()
    for (course_id, semester), var in take.items():
        if solver.Value(var) != 0:
            selected_courses.add(course_id)
    
    # For each selected course, check its prerequisites
    for course_id in selected_courses:
        if "prerequisites_str" in courses_df.columns and not pd.isna(courses_df.loc[course_id, "prerequisites_str"]):
            prereq_str = courses_df.loc[course_id, "prerequisites_str"]
            
            # Simple parsing of prerequisites (this should be improved for complex cases)
            prereqs = prereq_str.split(",")
            for prereq in prereqs:
                prereq = prereq.strip()
                if prereq in selected_courses:
                    edges.append({
                        "from": prereq,
                        "to": course_id
                    })
    
    return edges

def run_optimization(input_data, courses_df, requirements_data):
    """Run the optimization based on input data"""
    # Create the CP-SAT model
    model = cp_model.CpModel()
    
    # Variables for course assignments
    take = {}
    
    # Extract locked courses from input
    locked_courses = []
    for section in input_data.get('semesters', []):
        section_id = section.get('id')
        for course in section.get('courses', []):
            course_id = course.get('subject_id')
            if course.get('locked', False):
                # Add as a hard constraint
                locked_courses.append((course_id, section_id))
    
    # Add requirement constraints
    add_requirement_constraints(model, take, courses_df, requirements_data)
    
    # Add prerequisite constraints
    add_prerequisite_constraints(model, take, courses_df)
    
    # Add locked course constraints
    for course_id, semester in locked_courses:
        if (course_id, semester) in take:
            model.Add(take[(course_id, semester)] == 1)
    
    # Add constraints from input
    constraints = input_data.get('constraints', {})
    max_units_per_semester = constraints.get('maxUnitsPerSemester', 60)
    min_units_per_semester = constraints.get('minUnitsPerSemester', 36)
    
    # Units per semester constraints
    if 'units' in courses_df.columns:
        for semester in range(8):  # Assuming 8 semesters
            semester_units = []
            for course_id in courses_df.index:
                if (course_id, semester) in take:
                    units = courses_df.loc[course_id, 'units']
                    if not pd.isna(units):
                        semester_units.append(take[(course_id, semester)] * int(units))
            
            if semester_units:
                semester_total = sum(semester_units)
                model.Add(semester_total <= max_units_per_semester)
                model.Add(semester_total >= min_units_per_semester)
    
    # Solve the model
    solver = cp_model.CpSolver()
    solution_printer = VarArraySolutionPrinter(take)
    status = solver.Solve(model, solution_printer)
    
    # Check if a solution was found
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Generate sections from the solution
        sections = generate_sections_from_solution(
            solver, take, courses_df, input_data.get('semesters', [])
        )
        
        # Generate edges from the solution
        edges = generate_edges_from_solution(solver, take, courses_df)
        
        # Prepare the result
        result = {
            "success": True,
            "sections": sections,
            "edges": edges,
            "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
            "message": "Successfully optimized the course road."
        }
        
        return result
    else:
        status_message = "unknown"
        if status == cp_model.INFEASIBLE:
            status_message = "infeasible"
        elif status == cp_model.MODEL_INVALID:
            status_message = "model_invalid"
        
        return {
            "success": False,
            "status": status_message,
            "message": "Could not find a feasible solution with the given constraints."
        }

def main():
    """Main function to handle API integration"""
    args = parse_args()
    
    try:
        # Read the input file
        with open(args.input, 'r') as f:
            input_data = json.load(f)
        
        # Load course data
        courses_data = load_courses_data()
        courses_df = pd.DataFrame(courses_data)
        courses_df.set_index('subject_id', inplace=True)
        
        # Load requirements data
        requirements_data = load_requirements_data()
        
        # Run optimization
        result = run_optimization(input_data, courses_df, requirements_data)
        
        # Write the result to the output file
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Optimization completed. Results written to {args.output}")
        
    except Exception as e:
        error_message = {
            "success": False,
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc() if args.debug else None
        }
        
        # Write the error to the output file
        with open(args.output, 'w') as f:
            json.dump(error_message, f, indent=2)
        
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        
        sys.exit(1)

if __name__ == "__main__":
    main()