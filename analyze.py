# %%
import requests
import pulp
import pprint
import pandas as pd
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import CpModel
from datetime import datetime
import re
from pprint import pprint
from utils.utils import parse_prerequisites, find_current_school_year,is_valid_class_semester
import concurrent.futures
# %%
def fetch_requirement(key):
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return key, resp.json()

response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
data = response.json()

courses_df = pd.DataFrame(data)
response = requests.get('https://fireroad.mit.edu/requirements/list_reqs')
data = response.json()
with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = {executor.submit(fetch_requirement, key): key for key in data.keys()}
    result = {key: future.result()[1] for future, key in futures.items()}

# %%
school_year, planning_year = find_current_school_year()

requirements_df = pd.DataFrame([
    {"key": key, **(req if req is not None else {})}
    for key, req in result.items()
])

filtered_requirements = requirements_df[requirements_df['key'].str.contains('6', na=False)]
print("Requirements with '6' in their key:")
print(filtered_requirements['key'])

two = requirements_df.set_index("key").loc['major2'].reqs
twoa = requirements_df.set_index("key").loc['major2a'].reqs
sixthree = requirements_df.set_index("key").loc['major6-3new'].reqs
sixfive = requirements_df.set_index("key").loc['major6-2new'].reqs
girs = requirements_df.set_index("key").loc['girs'].reqs

pprint(twoa)

courses_df = courses_df[courses_df['is_historical'].isna()]
assert isinstance(courses_df, pd.DataFrame), "Why would it not be a dataframe"
classes = courses_df['subject_id'];
units = courses_df['total_units'];
hours = courses_df['in_class_hours'].fillna(0) + courses_df['out_of_class_hours'].fillna(0)
prereqs = courses_df['prerequisites']

assert isinstance(classes, pd.Series), "classes is a series"
assert isinstance(units, pd.Series), "units should be a series"
assert isinstance(hours, pd.Series), "hours should be a series"
assert isinstance(prereqs, pd.Series), "prereqs should be a series"

planning_year_start, planning_year_end = map(int, planning_year.split('-'))

# ccidx = courses_df[courses_df["subject_id"]=="4.648"].index[0]
# print(int(ccidx))
# print(planning_year_start)
# print(is_valid_class_semester(int(ccidx), 3, courses_df, planning_year_start))

# %%

model = cp_model.CpModel()

C = 60;
C_IAP = 12;
H = 60;
PLANNING_HORIZON = 12
MUSICIAN = False




take: dict[tuple[int, int], cp_model.IntVar] = {}
for c, el in classes.items():
    assert isinstance(c, int), "c must be an int"
    for s in range(1, 13):
        if not is_valid_class_semester(c,s,courses_df,planning_year_start):
            continue
        take[c, s] = model.NewBoolVar(f"take_{c}_{s}")


print(f"total number of base decision variables is {len(take)}")

semCred = {s: model.NewIntVar(0, 48 if s == 1 else (C_IAP if (s - 2) % 3 == 0 and s <= 11 else C), f"semCred_{s}") for s in range(1,PLANNING_HORIZON + 1)}
semHrs  = {s: model.NewIntVar(0, H, f"semHrs_{s}")  for s in range(1,13)}

def generic_satisfied(course_code: str, generic_attr: str, split: str, use_right: bool = True)-> cp_model.IntVar:
    def get_courses_for_hass(hass_code, courses_df):
        return courses_df.index[courses_df[generic_attr] == hass_code].tolist()

    right_code = course_code.split(split)[1]
    #print(f"generic code is {hass_code}")
    if use_right:
        generic = get_courses_for_hass(right_code, courses_df)
    else:
        generic = get_courses_for_hass(course_code, courses_df)

    req_satisfied = model.NewBoolVar(f"req_hass_{course_code}_satisfied")

    # Satisfied if any course with this generic attribute was taken
    # taken_vars = [take[c, s] for c in generic for s in range(1,13) if (c, s) in take]

    # if taken_vars:
    #     model.AddMaxEquality(req_satisfied, taken_vars)
    # else:
    #     model.Add(req_satisfied == 0)
    if not generic:
        print(f"WARNING WARNING WARNING nothing was located for generic attr: {generic_attr} code {right_code}")

    sum_taken = sum([take[c, s] for c in generic for s in range(1,13) if (c, s) in take])
    model.Add(sum_taken >= 1).OnlyEnforceIf(req_satisfied)
    model.Add(sum_taken < 1).OnlyEnforceIf(req_satisfied.Not())

    return req_satisfied

def hass_any_satisfied()-> cp_model.IntVar:
    def get_courses_for_hass(courses_df):
        return courses_df.index[courses_df["hass_attribute"].isin(["HASS-A", "HASS-E", "HASS-H", "HASS-S"])].tolist()

    generic = get_courses_for_hass(courses_df)
    req_satisfied = model.NewBoolVar(f"req_hass_root_satisfied")

    sum_taken = sum([take[c, s] for c in generic for s in range(1,13) if (c, s) in take])
    model.Add(sum_taken >= 8).OnlyEnforceIf(req_satisfied)
    model.Add(sum_taken < 8).OnlyEnforceIf(req_satisfied.Not())

    # if taken_vars:
    #     model.AddMaxEquality(req_satisfied, taken_vars)
    # else:
    #     model.Add(req_satisfied == 0)

    return req_satisfied

def add_requirement_constraints(model: CpModel, take: dict[tuple[int, int], cp_model.IntVar], req_val, courses_df, planning_year_start: int, aux_vars):
    if aux_vars is None:
        aux_vars = {}
    counter = [0]
    def process_requirement(req_item, counter = [0]):
        if ('req' in req_item and not 'plain-string' in req_item): #leaf case
            #print(f"leaf for {req_item}")
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
                    model.Add(req_satisfied == 0)  # Cannot be satisfied if no valid semesters

                return req_satisfied
            elif course_code == "HASS":
                return hass_any_satisfied()
            elif course_code.startswith("GIR:"):
                return generic_satisfied(course_code, "gir_attribute",":")
            elif course_code.startswith("HASS-"):
                print(f"course code is: {course_code}")
                #print("HASS FLAGGED")
                return generic_satisfied(course_code, "hass_attribute","-", False)
            elif course_code.startswith("CI-"):
                return generic_satisfied(course_code, "communication_requirement","-", False)
            else:
                print(f"dummy mode failure for req item {req_item} with ps mode {'plain-string' in req_item}")
                dummy_var = model.NewBoolVar(f"dummy_{course_code}")
                aux_vars[f"dummy_{course_code}"] = dummy_var
                model.Add(dummy_var == 0)
                return dummy_var
        elif 'reqs' in req_item: #branch case
            sub_req_vars = []
            #print(f"branch for {req_item}")


            # Process all sub-requirements
            for sub_req in req_item['reqs']:
                sub_var = process_requirement(sub_req, counter)
                if sub_var is not None:
                    sub_req_vars.append(sub_var)

            # Create a variable for this requirement group
            group_name = req_item.get('title', 'unnamed')
            if group_name == 'unnamed':
                counter[0] += 1
                group_name = f"unnamed_{counter[0]}"

            placeholder = model.NewBoolVar(f"req_group_{group_name}")
            print(f"SETTING AUX VARS A {group_name} for reqitem {req_item}")
            aux_vars[group_name] = placeholder

            if 'threshold' in req_item: #We don't really handle the LTE case very well, this assumes cutoff is GTE
                print("threshold mode")
                threshold = req_item['threshold']['cutoff']
                sum_subs = sum(sub_req_vars)
                model.Add(sum_subs >= threshold).OnlyEnforceIf(placeholder)
                model.Add(sum_subs < threshold).OnlyEnforceIf(placeholder.Not())
            elif 'connection-type' in req_item and req_item['connection-type'] == 'all':
                print("all mode")
                if not sub_req_vars:
                    model.Add(placeholder == 1)
                else:
                    model.AddMinEquality(placeholder, sub_req_vars)
            elif 'connection-type' in req_item and req_item['connection-type'] == 'any':
                print("any mode")
                # Any one of the sub-requirements must be satisfied
                #print(f"anyof for {req_item}")
                if sub_req_vars:
                    model.AddMaxEquality(placeholder, sub_req_vars)
                else:
                    model.Add(placeholder == 0)  # Empty 'any' cannot be satisfied
            else:
                print("default any mode")
                if sub_req_vars:
                    model.AddMinEquality(placeholder, sub_req_vars)
                else:
                    model.Add(placeholder == 1)

            return placeholder

        # For plain string requirements (descriptive), we can't directly enforce them
        # But we can create a placeholder variable for tracking
        elif 'req' in req_item and 'plain-string' in req_item and req_item['plain-string']:
            print(f"Found a placeholder {req_item}")

            group_name = req_item.get('title', 'unnamed')
            print("SETTING AUX VARS B")
            print(f"placehodler group name b: {group_name} with reqitem {req_item}")
            placeholder = model.NewBoolVar(f"req_placeholder_{group_name}")
            aux_vars[group_name] = placeholder

            model.Add(placeholder == 1)
            return placeholder

        print("Something really bad happened")
        return None

    # Start processing from the top level of the requirements
    if isinstance(req_val, list):
        print("doing type a")
        req_vars = []
        for req in req_val:
            print(req)
            req_var = process_requirement(req)
            if req_var is not None:
                req_vars.append(req_var)

        # Ensure all top-level requirements are satisfied
        for var in req_vars:
            model.Add(var == 1)
    else:
        print("doing type b")
        req_var = process_requirement(req_val)
        if req_var is not None:
            model.Add(req_var == 1)
    return aux_vars

group_vars = {}
add_requirement_constraints(model, take, twoa, courses_df, planning_year_start, group_vars)
add_requirement_constraints(model, take, girs, courses_df, planning_year_start, group_vars)


# HANDLE PREREQUISITES HERE

def add_prerequisite_constraints(model, take, courses_df, planning_year_start):
    for course_idx, prereq_str in courses_df['prerequisites'].items():
        if pd.isna(prereq_str) or not prereq_str:
            continue  # Skip courses without prerequisites

        parsed_prereqs = parse_prerequisites(prereq_str)
        if not parsed_prereqs:  # Empty prerequisites
            continue

        for semester in range(1, 13):
            if (course_idx, semester) not in take:
                continue

            # If we take this course, its prerequisites must be satisfied
            prereq_satisfied = process_prereq_condition(
                model, parsed_prereqs, take, courses_df, course_idx, semester, planning_year_start
            )

            # Only allow taking the course if prerequisites are satisfied
            model.Add(prereq_satisfied >= take[course_idx, semester])

def process_prereq_condition(model, condition, take, courses_df, course_idx, semester, planning_year_start):
    # Base case: single course requirement (string)
    if isinstance(condition, str):
        if condition.startswith('GIR:'):
            def get_courses_for_gir(gir_code, courses_df):
                return courses_df.index[courses_df['gir_attribute'] == gir_code].tolist()

            gir_code = condition.split(':')[1]
            gir_courses = get_courses_for_gir(gir_code, courses_df)
            prereq_var = model.NewBoolVar(f"prereq_GIR_{gir_code}_for_{courses_df.at[course_idx, 'subject_id']}_{semester}")

            # Satisfied if any course with this GIR attribute was taken in an earlier semester
            earlier_semesters = range(1, semester)
            taken_vars = [take[c, s] for c in gir_courses for s in earlier_semesters if (c, s) in take]

            if taken_vars:
                model.AddMaxEquality(prereq_var, taken_vars)
            else:
                model.Add(prereq_var == 0)  # Can't be satisfied if no such courses exist

            return prereq_var #return model.NewConstant(1)

        # Find the course in the dataframe
        prereq_indices = courses_df.index[courses_df['subject_id'] == condition].tolist()
        if not prereq_indices:
            # Course not found, assume satisfied
            #print(f"course of {condition} is not present in the database! Something went wrong")
            #
            return model.NewConstant(0)

        prereq_idx = prereq_indices[0]
        prereq_var = model.NewBoolVar(f"prereq_{condition}_for_{courses_df.at[course_idx, 'subject_id']}_{semester}")

        # Prerequisite is satisfied if taken in any earlier semester
        earlier_semesters = [s for s in range(1, semester)
                             if (prereq_idx, s) in take and
                             is_valid_class_semester(prereq_idx, s, courses_df, planning_year_start)]

        if earlier_semesters:
            sum_taken = sum(take[prereq_idx, s] for s in earlier_semesters)
            model.Add(sum_taken >= 1).OnlyEnforceIf(prereq_var)
            model.Add(sum_taken < 1).OnlyEnforceIf(prereq_var.Not())
        else:
            model.Add(prereq_var == 0)  # Cannot be satisfied if no valid earlier semesters

        return prereq_var

    # AND condition (dictionary with 'and' key)
    elif isinstance(condition, dict) and 'and' in condition:
        and_vars = [process_prereq_condition(model, c, take, courses_df, course_idx, semester, planning_year_start)
                   for c in condition['and']]
        #print(f"or for {condition}")

        if not and_vars:
            return model.NewConstant(1)  # Empty AND is trivially satisfied

        and_var = model.NewBoolVar(f"prereq_and_{course_idx}_{semester}_{id(condition)}")
        model.AddMinEquality(and_var, and_vars)
        return and_var

    # OR condition (dictionary with 'or' key)
    elif isinstance(condition, dict) and 'or' in condition:
        or_vars = [process_prereq_condition(model, c, take, courses_df, course_idx, semester, planning_year_start)
                  for c in condition['or']]

        if not or_vars:
            return model.NewConstant(0)  # Empty OR cannot be satisfied

        or_var = model.NewBoolVar(f"prereq_or_{course_idx}_{semester}_{id(condition)}")
        model.AddMaxEquality(or_var, or_vars)
        return or_var

    # Default case (unknown structure)
    return model.NewConstant(1)

add_prerequisite_constraints(model, take, courses_df, planning_year_start)

# #Semester credit handling
for s in range(1,13):
     creditsum = sum(units[c]*take[c,s] for c in classes.index if is_valid_class_semester(c, s, courses_df, planning_year_start))
     model.Add(semCred[s] == creditsum)
#     # model.Add(semHrs[s]  == sum(int(hours[c])*take[c,s] for c in classes.index if is_valid_class_semester(c, s, courses_df, planning_year_start)))

class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    def __init__(self, take: dict[tuple[int, int], cp_model.IntVar], group_vars: dict, units):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.take = take
        self.group_vars = group_vars if group_vars is not None else {}
        self.units = units
        self.__solution_count = 0

    def on_solution_callback(self) -> None:
        self.__solution_count += 1
        print(f"Step {self.__solution_count}:")

        semester_units = [0] * 12
        for (c, s), v in self.take.items():
            if self.Value(v) != 0:
                print(f"take[{classes.loc[c]}, {s}] = {self.Value(v)}")
                semester_units[s - 1] += self.units.loc[c] * self.Value(v)
        print("Units per semester:", semester_units)
        if self.group_vars:
            print("Group Vars:")
            for name, var in self.group_vars.items():
                print(f"group_var[{name}] = {self.Value(var)}")
        print()

    @property
    def solution_count(self) -> int:
        return self.__solution_count

# Objective
printer = VarArraySolutionPrinter(take, group_vars, units)
finish_time = sum((s // 3) * take[idx, s] for idx in classes.index for s in range(1, 13) if is_valid_class_semester(idx, s, courses_df, planning_year_start))
model.Minimize(finish_time) #  + overload_pen

#Solve
solver = cp_model.CpSolver()
solver.parameters.enumerate_all_solutions = True
solver.parameters.max_time_in_seconds = 20
res = solver.Solve(model, printer)

if res == cp_model.OPTIMAL:
    print('optimal solution found!')
if res == cp_model.FEASIBLE:
    print('feasible solution found!')
if res == cp_model.INFEASIBLE:
    print('infeasible solution found!')
if res == cp_model.MODEL_INVALID:
    print('constraint failure!')




# print(f"Solution:")
# for (c, s), v in take.items():
#     if solver.Value(v) != 0:
#         print(f"take[{classes.loc[c]}, {s}] = {solver.Value(v)}")

# print("Group Vars:")
# for name, var in group_vars.items():
#     print(f"group_var[{name}] = {solver.Value(var)}")
# %%

def export_take_blocks_to_road(solver, take, courses_df, output_file):
    import json
    import os

    selected_subjects = []
    for (c, s), v in take.items():
        if solver.Value(v) != 0:

            if "hass_attribute" in courses_df.columns and not pd.isna(courses_df.loc[c, "hass_attribute"]):
                print(f"HASS Subject: {courses_df.loc[c, 'subject_id']} - {courses_df.loc[c, 'title']}")
                print(f"HASS Attribute: {courses_df.loc[c, 'hass_attribute']}")
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

        if os.path.exists(output_file):
            os.remove(output_file)

            import time
            time.sleep(0.2)
        with open(output_file, "w") as f:
            json.dump(road_data, f, indent=4)

export_take_blocks_to_road(solver, take, courses_df, "poop.road")
