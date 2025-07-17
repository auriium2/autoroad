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
from utils.utils import parse_prerequisites, is_valid_class_semester, find_current_school_year
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

#print(requirements_df[['key','reqs']].set_index('key').head(5))
#pprint(requirements_df["key"].head(10))
# print("DS")
# pprint(requirements_df["reqs"].head(1).item())
#print(requirements_df[~requirements_df['reqs'].apply(lambda a: isinstance(a, list))])
twoa = requirements_df.set_index("key").loc['major2a'].reqs

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

#print(courses_df["not_offered_year"].head(10))
#print(prereqs.head(1).item())

#eightidx = classes[classes == "6.1020"].index[0]
#print(units[eightidx])

requirements = {}

# %%
model = cp_model.CpModel()

C = 48;
H = 60;
planning_year_start, planning_year_end = map(int, planning_year.split('-'))

take: dict[tuple[int, int], cp_model.IntVar] = {}
for c, el in classes.items():
    assert isinstance(c, int), "c must be an int"
    for s in range(1, 13):
        if not is_valid_class_semester(c,s,courses_df,planning_year_start):
            continue
        take[c, s] = model.NewBoolVar(f"take_{c}_{s}")
print(f"total number of base decision variables is {len(take)}")

semCred = {s: model.NewIntVar(0, C, f"semCred_{s}") for s in range(1,13)}
semHrs  = {s: model.NewIntVar(0, H, f"semHrs_{s}")  for s in range(1,13)}

def add_requirement_constraints(model: CpModel, take: dict[tuple[int, int], cp_model.IntVar], req_val, courses_df, planning_year_start: int, group_vars):
    if group_vars is None:
        group_vars = {}
    def process_requirement(req_item):
        if 'req' in req_item and not 'plain-string' in req_item: #leaf case
            #print(f"leaf node of {req_item}")
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
            else:
                dummy_var = model.NewBoolVar(f"dummy_{course_code}")
                model.Add(dummy_var == 0)
                return dummy_var
        elif 'reqs' in req_item: #branch case
            sub_req_vars = []

            # Process all sub-requirements
            for sub_req in req_item['reqs']:
                sub_var = process_requirement(sub_req)
                if sub_var is not None:
                    sub_req_vars.append(sub_var)

            # Create a variable for this requirement group
            group_name = req_item.get('title', 'unnamed')
            group_var = model.NewBoolVar(f"req_group_{group_name}")
            group_vars[group_name] = group_var

            if 'threshold' in req_item: #We don't really handle the LTE case very well, this assumes cutoff is GTE
                threshold = req_item['threshold']['cutoff']
                sum_subs = sum(sub_req_vars)
                model.Add(sum_subs >= threshold).OnlyEnforceIf(group_var)
                model.Add(sum_subs < threshold).OnlyEnforceIf(group_var.Not())
            elif 'connection-type' in req_item and req_item['connection-type'] == 'all':
                if not sub_req_vars:
                    model.Add(group_var == 1)
                else:
                    model.AddMinEquality(group_var, sub_req_vars)
            elif 'connection-type' in req_item and req_item['connection-type'] == 'any':
                # Any one of the sub-requirements must be satisfied
                #print(f"anyof for {req_item}")
                if sub_req_vars:
                    model.AddMaxEquality(group_var, sub_req_vars)
                else:
                    model.Add(group_var == 0)  # Empty 'any' cannot be satisfied
            else:
                # Default to 'all' if not specified
                #print(f"anyof for {req_item}")
                if sub_req_vars:
                    model.AddMinEquality(group_var, sub_req_vars)
                else:
                    model.Add(group_var == 1)

            return group_var

        # For plain string requirements (descriptive), we can't directly enforce them
        # But we can create a placeholder variable for tracking
        elif 'req' in req_item and 'plain-string' in req_item and req_item['plain-string']:
            #print(f"Found a placeholder {req_item}")
            placeholder = model.NewBoolVar(f"placeholder_{req_item['req'][:20]}")
            model.Add(placeholder == 1)
            return placeholder

        print("Something really bad happened")
        return None

    # Start processing from the top level of the requirements
    if isinstance(req_val, list):
        req_vars = []
        for req in req_val:
            req_var = process_requirement(req)
            if req_var is not None:
                req_vars.append(req_var)

        # Ensure all top-level requirements are satisfied
        for var in req_vars:
            model.Add(var == 1)
    else:
        req_var = process_requirement(req_val)
        if req_var is not None:
            model.Add(req_var == 1)
    return group_vars

group_vars = {}
add_requirement_constraints(model, take, twoa, courses_df, planning_year_start, group_vars)

# HANDLE PREREQUISITES HERE

def add_prerequisite_constraints(model, take, courses_df, planning_year_start):

    for course_idx, prereq_str in courses_df['prerequisites'].items():
        if pd.isna(prereq_str) or not prereq_str:
            continue  # Skip courses without prerequisites

        # Parse the prerequisite expression
        parsed_prereqs = parse_prerequisites(prereq_str)
        if not parsed_prereqs:  # Empty prerequisites
            continue

        # For each valid semester the course might be taken
        for semester in range(1, 13):
            if (course_idx, semester) not in take:
                continue

            if not is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
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
            # Handle GIRs - assuming they are satisfied externally
            print(f"ignoring gir for {condition}")
            return model.NewConstant(1)

        # Find the course in the dataframe
        prereq_indices = courses_df.index[courses_df['subject_id'] == condition].tolist()
        if not prereq_indices:
            # Course not found, assume satisfied
            print(f"course of {condition} is not present in the database! Something went wrong")
            return model.NewConstant(1)

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



# for course_idx, prereq_str in courses_df['prerequisites'].items():
#     if pd.isna(prereq_str) or not prereq_str:
#         continue  # Skip courses without prerequisites

#     # Parse the prerequisite expression
#     parsed_prereqs = parse_prerequisites(prereq_str)

#     # For each valid semester the course might be taken
#     for semester in range(1, 13):
#         if not is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
#             continue

#         # If we take this course, its prerequisites must be satisfied
#         prereq_satisfied = process_prereq_condition(
#             model, parsed_prereqs, take, courses_df, course_idx, semester, planning_year_start
#         )

#         # Only allow taking the course if prerequisites are satisfied
#         model.Add(prereq_satisfied >= take[course_idx, semester])

# slack variables
# overCred = {s: model.NewIntVar(0, 18, f"softCreditOverload_{s}") for s in range(1,13)}
# overHrs  = {s: model.NewIntVar(0, 40, f"softHourOverload_{s}")  for s in range(1,13)}
# for c, name in classes.items():
#     if c in major | gen_ed | hum_spec: #
#         model.Add(sum(take[c,s] for s in range(1,9)) == 1) #define required classes
#     else:
#         model.Add(sum(take[c,s] for s in range(1,9)) <= 1) #define optional fillters


#fixed classes go here



# for c, prereq_list in prereqs.items():
#     for s in range(1, 13):
#         if not is_valid_class_semester(c, s, courses_df, planning_year_start):
#             continue  # Skip invalid pairs


# #Semester credit handling
for s in range(1,13):
     creditsum = sum(units[c]*take[c,s] for c in classes.index if is_valid_class_semester(c, s, courses_df, planning_year_start))
     model.Add(semCred[s] == creditsum)
#     # model.Add(semHrs[s]  == sum(int(hours[c])*take[c,s] for c in classes.index if is_valid_class_semester(c, s, courses_df, planning_year_start)))



# # 4. Humanities totals & specifics
# model.Add(sum(take[c,s] for c in humanities for s in range(1,9) if is_valid_class_semester(c, s, courses_df, planning_year_start)) >= 8)
# model.Add(sum(take[c,s] for c in hum_type1 for s in range(1,9) if is_valid_class_semester(c, s, courses_df, planning_year_start)) >= 2)
# for letter_set in [hum_a, hum_b, hum_c, hum_d]:
#     model.Add(sum(take[c,s] for c in letter_set for s in range(1,9) if is_valid_class_semester(c, s, courses_df, planning_year_start)) >= 1)
# for c in hum_spec:
#     model.Add(sum(take[c,s] for s in range(1,9) if is_valid_class_semester(c, s, courses_df, planning_year_start)) == 1)

class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions, showing all nonzero variables in take and all group_vars.
    Also prints total units taken in each semester at every solution step.
    """

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
        # if self.group_vars:
        #     print("Group Vars:")
        #     for name, var in self.group_vars.items():
        #         print(f"group_var[{name}] = {self.Value(var)}")
        print()

    @property
    def solution_count(self) -> int:
        return self.__solution_count

# Objective
printer = VarArraySolutionPrinter(take, group_vars, units)
finish_time = sum(s * take[idx, s] for idx in classes.index for s in range(1, 13) if is_valid_class_semester(idx, s, courses_df, planning_year_start))
# overload_pen = PenCred * sum(overCred[s] for s in range(1,9)) \
#              + PenHrs  * sum(overHrs[s]  for s in range(1,9))
model.Minimize(finish_time) #  + overload_pen

# Solve
solver = cp_model.CpSolver()
solver.parameters.enumerate_all_solutions = True
solver.parameters.max_time_in_seconds = 150
res = solver.Solve(model, printer)

if res == cp_model.OPTIMAL:
    print('optimal solution found!')
if res == cp_model.FEASIBLE:
    print('feasible solution found!')
if res == cp_model.INFEASIBLE:
    print('feasible solution found!')
if res == cp_model.MODEL_INVALID:
    print('constraint failure!')

# print(f"Solution:")
# for (c, s), v in take.items():
#     if solver.Value(v) != 0:
#         print(f"take[{classes.loc[c]}, {s}] = {solver.Value(v)}")

# print("Group Vars:")
# for name, var in group_vars.items():
#     print(f"group_var[{name}] = {solver.Value(var)}")
