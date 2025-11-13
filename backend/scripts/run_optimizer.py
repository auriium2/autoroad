#!/usr/bin/env python3
"""
Course Optimization Script
Mimics analyze.py behavior but designed for AI/automated execution.
"""

import argparse
import concurrent.futures
import json
import sys

import pandas as pd
import requests
from ortools.sat.python import cp_model

from ..utils.utils import find_current_school_year, is_valid_class_semester, parse_prerequisites


def fetch_requirement(key):
    """Fetch a single requirement from Fireroad API."""
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return key, resp.json()


def fetch_all_data():
    """Fetch courses and requirements data from Fireroad API."""
    print("Fetching courses data...")
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    courses_data = response.json()
    courses_df = pd.DataFrame(courses_data)

    print("Fetching requirements data...")
    response = requests.get('https://fireroad.mit.edu/requirements/list_reqs')
    requirements_keys = response.json()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(fetch_requirement, key): key for key in requirements_keys.keys()}
        requirements = {key: future.result()[1] for future, key in futures.items()}

    requirements_df = pd.DataFrame([
        {"key": key, **(req if req is not None else {})}
        for key, req in requirements.items()
    ])
    requirements_df = requirements_df.set_index("key")

    return courses_df, requirements_df


def get_sixmod_requirements():
    """Define custom 6-Mod requirements."""
    sixmod = []

    sixmod.append({
        'connection-type': 'all',
        'reqs': [
            {'connection-type': 'any', 'reqs': [{'req': '6.100A'}, {'req': '6.100L'}], 'threshold-desc': 'select either'},
            {'connection-type': 'any', 'reqs': [{'req': '6.120A'}, {'req': '6.1200'}], 'threshold-desc': 'select either'},
            {'req': '6.1210'},
            {'connection-type': 'any', 'reqs': [{'req': '6.1903'}, {'req': '6.1904'}], 'threshold-desc': 'select either'}
        ],
        'threshold-desc': 'select all',
        'title': 'Fundamental'
    })

    sixmod.append({
        'connection-type': 'all',
        'reqs': [
            {'connection-type': 'any', 'reqs': [{'req': '6.S084'}, {'req': '18.C06'}, {'req': '18.06'}], 'threshold-desc': 'select any'},
            {'connection-type': 'any', 'reqs': [{'req': '6.3700'}, {'req': '6.3800'}, {'req': '18.05'}], 'threshold-desc': 'select any'}
        ],
        'threshold-desc': 'select all',
        'title': 'Math'
    })

    sixmod.append({
        'connection-type': 'all',
        'reqs': [{'req': '6.1910'}, {'req': '6.2000'}, {'req': '6.3100'}, {'req': '6.9000'}],
        'threshold-desc': 'select all',
        'title': 'System Design'
    })

    sixmod.append({
        'connection-type': 'any',
        'reqs': [
            {'req': '6.1100'}, {'req': '6.1820'}, {'req': '6.2040'}, {'req': '6.2050'},
            {'req': '6.2060'}, {'req': '6.2220'}, {'req': '6.2221'}, {'req': '6.2370'},
            {'req': '6.2410'}, {'req': '6.2600'}, {'req': '6.4200'}, {'req': '6.4420'},
            {'req': '6.4510'}, {'req': '6.4550'}, {'req': '6.4860'}
        ],
        'threshold': {'criterion': 'subjects', 'cutoff': 1, 'type': 'GTE'},
        'threshold-desc': 'select any',
        'title': 'PLAB'
    })

    return sixmod


def generic_satisfied(model, take, course_code, generic_attr, split, courses_df, use_right=True):
    """Handle generic course attributes (HASS, GIR, CI)."""
    def get_courses_for_generic(code, courses_df, attr):
        return courses_df.index[courses_df[attr] == code].tolist()

    right_code = course_code.split(split)[1] if use_right else course_code
    generic = get_courses_for_generic(right_code, courses_df, generic_attr) if use_right else get_courses_for_generic(course_code, courses_df, generic_attr)

    req_satisfied = model.NewBoolVar(f"req_{generic_attr}_{course_code}_satisfied")

    if not generic:
        print(f"WARNING: No courses found for {generic_attr}: {right_code}")

    sum_taken = sum([take[c, s] for c in generic for s in range(1, 13) if (c, s) in take])
    model.Add(sum_taken >= 1).OnlyEnforceIf(req_satisfied)
    model.Add(sum_taken < 1).OnlyEnforceIf(req_satisfied.Not())

    return req_satisfied


def hass_any_satisfied(model, take, courses_df):
    """Check if 8 HASS requirements are satisfied."""
    def get_courses_for_hass():
        return courses_df.index[courses_df["hass_attribute"].isin(["HASS-A", "HASS-E", "HASS-H", "HASS-S"])].tolist()

    generic = get_courses_for_hass()
    req_satisfied = model.NewBoolVar("req_hass_root_satisfied")

    sum_taken = sum([take[c, s] for c in generic for s in range(1, 13) if (c, s) in take])
    model.Add(sum_taken >= 8).OnlyEnforceIf(req_satisfied)
    model.Add(sum_taken < 8).OnlyEnforceIf(req_satisfied.Not())

    return req_satisfied


def add_requirement_constraints(model, take, req_val, courses_df, planning_year_start, aux_vars):
    """Add requirement constraints to the model. This is a simplified version of the original."""
    if aux_vars is None:
        aux_vars = {}

    counter = [0]
    infeasible_reqs = {}
    missing_courses = {}
    solution_status = {"is_feasible": True, "reasons": [], "flexible_requirements": {}}

    def count_leaf_courses(requirement):
        """Count leaf courses in a requirement tree."""
        if 'req' in requirement and 'plain-string' not in requirement:
            course_code = requirement['req']
            if course_code in courses_df['subject_id'].values:
                return 1
            elif course_code == "HASS" or course_code.startswith("GIR:") or \
                 course_code.startswith("HASS-") or course_code.startswith("CI-"):
                return 1
            return 0
        elif 'reqs' in requirement:
            count = 0
            for sub in requirement['reqs']:
                count += count_leaf_courses(sub)
            return count
        return 0

    def process_requirement(req_item, counter=[0], parent_path="root"):
        """Process a single requirement recursively."""
        # Leaf case: single course
        if 'req' in req_item and 'plain-string' not in req_item:
            course_code = req_item['req']

            if course_code in courses_df['subject_id'].values:
                course_id = courses_df[courses_df['subject_id'] == course_code].index[0]
                req_satisfied = model.NewBoolVar(f"req_course_{course_code}_satisfied")

                valid_semesters = [s for s in range(1, 13)
                                   if (course_id, s) in take and
                                   is_valid_class_semester(course_id, s, courses_df, planning_year_start)]

                if valid_semesters:
                    sum_taken = sum(take[course_id, s] for s in valid_semesters)
                    model.Add(sum_taken >= 1).OnlyEnforceIf(req_satisfied)
                    model.Add(sum_taken < 1).OnlyEnforceIf(req_satisfied.Not())
                else:
                    model.Add(req_satisfied == 0)

                return req_satisfied

            elif course_code == "HASS":
                return hass_any_satisfied(model, take, courses_df)
            elif course_code.startswith("GIR:"):
                return generic_satisfied(model, take, course_code, "gir_attribute", ":", courses_df)
            elif course_code.startswith("HASS-"):
                return generic_satisfied(model, take, course_code, "hass_attribute", "-", courses_df, False)
            elif course_code.startswith("CI-"):
                return generic_satisfied(model, take, course_code, "communication_requirement", "-", courses_df, False)
            else:
                print(f"WARNING: Course '{course_code}' not found")
                return None

        # Branch case: group of requirements
        elif 'reqs' in req_item:
            sub_req_vars = []
            group_name = req_item.get('title', 'unnamed')
            if group_name == 'unnamed':
                counter[0] += 1
                group_name = f"unnamed_{counter[0]}"

            new_parent_path = f"{parent_path} -> {group_name}"

            for sub_req in req_item['reqs']:
                sub_var = process_requirement(sub_req, counter, new_parent_path)
                if sub_var is not None:
                    sub_req_vars.append(sub_var)

            placeholder = model.NewBoolVar(f"req_group_{group_name}")
            aux_vars[group_name] = placeholder

            # Handle threshold
            if 'threshold' in req_item:
                threshold = req_item['threshold']['cutoff']
                sum_subs = sum(sub_req_vars) if sub_req_vars else 0
                model.Add(sum_subs >= threshold).OnlyEnforceIf(placeholder)
                model.Add(sum_subs < threshold).OnlyEnforceIf(placeholder.Not())
            # Handle connection-type
            elif 'connection-type' in req_item:
                if req_item['connection-type'] == 'all':
                    if sub_req_vars:
                        model.AddMinEquality(placeholder, sub_req_vars)
                    else:
                        model.Add(placeholder == 1)
                elif req_item['connection-type'] == 'any':
                    if sub_req_vars:
                        model.AddMaxEquality(placeholder, sub_req_vars)
                    else:
                        model.Add(placeholder == 0)
            else:
                # Default to 'all'
                if sub_req_vars:
                    model.AddMinEquality(placeholder, sub_req_vars)
                else:
                    model.Add(placeholder == 1)

            return placeholder

        # Plain string (descriptive)
        elif 'req' in req_item and 'plain-string' in req_item and req_item['plain-string']:
            group_name = req_item.get('title', 'unnamed')
            placeholder = model.NewBoolVar(f"req_placeholder_{group_name}")
            aux_vars[group_name] = placeholder
            model.Add(placeholder == 1)
            return placeholder

        return None

    # Process requirements
    if isinstance(req_val, list):
        req_vars = []
        for req in req_val:
            req_var = process_requirement(req)
            if req_var is not None:
                req_vars.append(req_var)
        for var in req_vars:
            model.Add(var == 1)
    else:
        req_var = process_requirement(req_val)
        if req_var is not None:
            model.Add(req_var == 1)

    aux_vars["solution_status"] = solution_status
    return aux_vars


def add_prerequisite_constraints(model, take, courses_df, planning_year_start):
    """Add prerequisite constraints to the model."""

    def process_prereq_condition(condition, course_idx, semester):
        """Process prerequisite conditions recursively."""
        if isinstance(condition, str):
            if condition.startswith('GIR:'):
                gir_code = condition.split(':')[1]
                gir_courses = courses_df.index[courses_df['gir_attribute'] == gir_code].tolist()
                prereq_var = model.NewBoolVar(f"prereq_GIR_{gir_code}_for_{courses_df.at[course_idx, 'subject_id']}_{semester}")

                earlier_semesters = range(1, semester)
                taken_vars = [take[c, s] for c in gir_courses for s in earlier_semesters if (c, s) in take]

                if taken_vars:
                    model.AddMaxEquality(prereq_var, taken_vars)
                else:
                    model.Add(prereq_var == 0)

                return prereq_var

            prereq_indices = courses_df.index[courses_df['subject_id'] == condition].tolist()
            if not prereq_indices:
                return model.NewConstant(0)

            prereq_idx = prereq_indices[0]
            prereq_var = model.NewBoolVar(f"prereq_{condition}_for_{courses_df.at[course_idx, 'subject_id']}_{semester}")

            earlier_semesters = [s for s in range(1, semester)
                                 if (prereq_idx, s) in take and
                                 is_valid_class_semester(prereq_idx, s, courses_df, planning_year_start)]

            if earlier_semesters:
                sum_taken = sum(take[prereq_idx, s] for s in earlier_semesters)
                model.Add(sum_taken >= 1).OnlyEnforceIf(prereq_var)
                model.Add(sum_taken < 1).OnlyEnforceIf(prereq_var.Not())
            else:
                model.Add(prereq_var == 0)

            return prereq_var

        elif isinstance(condition, dict) and 'and' in condition:
            and_vars = [process_prereq_condition(c, course_idx, semester) for c in condition['and']]
            if not and_vars:
                return model.NewConstant(1)
            and_var = model.NewBoolVar(f"prereq_and_{course_idx}_{semester}_{id(condition)}")
            model.AddMinEquality(and_var, and_vars)
            return and_var

        elif isinstance(condition, dict) and 'or' in condition:
            or_vars = [process_prereq_condition(c, course_idx, semester) for c in condition['or']]
            if not or_vars:
                return model.NewConstant(0)
            or_var = model.NewBoolVar(f"prereq_or_{course_idx}_{semester}_{id(condition)}")
            model.AddMaxEquality(or_var, or_vars)
            return or_var

        return model.NewConstant(1)

    for course_idx, prereq_str in courses_df['prerequisites'].items():
        if pd.isna(prereq_str) or not prereq_str:
            continue

        parsed_prereqs = parse_prerequisites(prereq_str)
        if not parsed_prereqs:
            continue

        for semester in range(1, 13):
            if (course_idx, semester) not in take:
                continue

            prereq_satisfied = process_prereq_condition(parsed_prereqs, course_idx, semester)
            model.Add(prereq_satisfied >= take[course_idx, semester])


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Callback to print solutions."""

    def __init__(self, take, classes, units, group_vars):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.take = take
        self.classes = classes
        self.units = units
        self.group_vars = group_vars if group_vars is not None else {}
        self.__solution_count = 0

    def on_solution_callback(self):
        self.__solution_count += 1
        print(f"\n{'='*60}")
        print(f"Solution #{self.__solution_count}")
        print(f"{'='*60}")

        semester_units = [0] * 12
        courses_by_semester = {s: [] for s in range(1, 13)}

        for (c, s), v in self.take.items():
            if self.Value(v) != 0:
                course_id = self.classes.loc[c]
                courses_by_semester[s].append(course_id)
                semester_units[s - 1] += self.units.loc[c] * self.Value(v)

        # Print courses by semester
        for s in range(1, 13):
            if courses_by_semester[s]:
                print(f"\nSemester {s} ({semester_units[s-1]} units):")
                for course in courses_by_semester[s]:
                    print(f"  - {course}")

        print(f"\n{'='*60}\n")

    @property
    def solution_count(self):
        return self.__solution_count


def export_to_road(solver, take, courses_df, output_file):
    """Export solution to .road file format."""
    selected_subjects = []

    for (c, s), v in take.items():
        if solver.Value(v) != 0:
            selected_subjects.append({
                "subject_id": courses_df.loc[c, "subject_id"],
                "semester": s,
                "title": courses_df.loc[c, "title"] if "title" in courses_df.columns else f"Course {courses_df.loc[c, 'subject_id']}",
                "units": courses_df.loc[c, "units"] if "units" in courses_df.columns else 12,
                "overrideWarnings": False
            })

    road_data = {
        "coursesOfStudy": [],
        "progressAssertions": {},
        "selectedSubjects": selected_subjects
    }

    with open(output_file, "w") as f:
        json.dump(road_data, f, indent=4)

    print(f"Exported solution to {output_file}")


def main():
    """Main function to run optimization."""
    parser = argparse.ArgumentParser(description='Optimize MIT course schedule')
    parser.add_argument('--major', type=str, default='major6-2new', help='Major requirement key')
    parser.add_argument('--output', type=str, default='solution.road', help='Output .road file')
    parser.add_argument('--max-time', type=int, default=20, help='Max solver time in seconds')
    parser.add_argument('--max-credits', type=int, default=60, help='Max credits per semester')
    parser.add_argument('--max-credits-iap', type=int, default=12, help='Max credits for IAP')
    args = parser.parse_args()

    # Fetch data
    courses_df, requirements_df = fetch_all_data()

    # Filter historical courses
    courses_df = courses_df[courses_df['is_historical'].isna()]

    # Get planning year
    school_year, planning_year = find_current_school_year()
    planning_year_start, planning_year_end = map(int, planning_year.split('-'))

    print(f"\nPlanning for academic year: {planning_year}")
    print(f"Major: {args.major}")

    # Get requirements
    try:
        major_reqs = requirements_df.loc[args.major].reqs
    except KeyError:
        print(f"Error: Major '{args.major}' not found")
        print("Available majors:")
        for key in requirements_df.index:
            if key.startswith('major'):
                print(f"  - {key}")
        return 1

    gir_reqs = requirements_df.loc['girs'].reqs

    # Create model
    print("\nBuilding optimization model...")
    model = cp_model.CpModel()

    # Decision variables
    take = {}
    classes = courses_df['subject_id']
    units = courses_df['total_units']

    for c, el in classes.items():
        for s in range(1, 13):
            if not is_valid_class_semester(c, s, courses_df, planning_year_start):
                continue
            take[c, s] = model.NewBoolVar(f"take_{c}_{s}")

    print(f"Created {len(take)} decision variables")

    # Credit constraints
    semCred = {s: model.NewIntVar(0, 48 if s == 1 else (args.max_credits_iap if (s - 2) % 3 == 0 and s <= 11 else args.max_credits),
                                   f"semCred_{s}") for s in range(1, 13)}

    for s in range(1, 13):
        creditsum = sum(units[c] * take[c, s] for c in classes.index
                        if is_valid_class_semester(c, s, courses_df, planning_year_start))
        model.Add(semCred[s] == creditsum)

    # Add requirements
    print("Adding requirement constraints...")
    group_vars = {}
    add_requirement_constraints(model, take, gir_reqs, courses_df, planning_year_start, group_vars)
    add_requirement_constraints(model, take, major_reqs, courses_df, planning_year_start, group_vars)

    # Add prerequisites
    print("Adding prerequisite constraints...")
    add_prerequisite_constraints(model, take, courses_df, planning_year_start)

    # Objective: minimize total courses taken
    print("Setting objective...")
    finish_time = sum(take[idx, s] for idx in classes.index for s in range(1, 13)
                      if is_valid_class_semester(idx, s, courses_df, planning_year_start))
    model.Minimize(finish_time)

    # Solve
    print(f"\nSolving (max {args.max_time}s)...")
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.max_time_in_seconds = args.max_time

    printer = SolutionPrinter(take, classes, units, group_vars)
    res = solver.Solve(model, printer)

    # Report results
    print("\n" + "="*60)
    if res == cp_model.OPTIMAL:
        print("RESULT: Optimal solution found!")
        export_to_road(solver, take, courses_df, args.output)
        return 0
    elif res == cp_model.FEASIBLE:
        print("RESULT: Feasible solution found!")
        export_to_road(solver, take, courses_df, args.output)
        return 0
    elif res == cp_model.INFEASIBLE:
        print("RESULT: Problem is infeasible - no solution exists")
        return 1
    elif res == cp_model.MODEL_INVALID:
        print("RESULT: Model is invalid - constraint failure")
        return 1
    else:
        print(f"RESULT: Unknown status ({res})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
