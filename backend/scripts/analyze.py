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
from ..utils.utils import parse_prerequisites, find_current_school_year,is_valid_class_semester
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
sixmod = []
sixmod.append({'connection-type': 'all',
  'reqs': [{'connection-type': 'any',
            'reqs': [{'req': '6.100A'}, {'req': '6.100L'}],
            'threshold-desc': 'select either'},
           {'connection-type': 'any',
            'reqs': [{'req': '6.120A'}, {'req': '6.1200'}],
            'threshold-desc': 'select either'},
           {'req': '6.1210'},
           {'connection-type': 'any',
            'reqs': [{'req': '6.1903'}, {'req': '6.1904'}],
            'threshold-desc': 'select either'}],
  'threshold-desc': 'select all',
  'title': 'Fundamental'})
sixmod.append({'connection-type': 'all',
 'reqs': [{'connection-type': 'any',
           'reqs': [{'req': '6.S084'}, {'req': '18.C06'}, {'req': '18.06'}],
           'threshold-desc': 'select any'},
          {'connection-type': 'any',
           'reqs': [{'req': '6.3700'}, {'req': '6.3800'}, {'req': '18.05'}],
           'threshold-desc': 'select any'}],
 'threshold-desc': 'select all',
 'title': 'Math'})
sixmod.append({'connection-type': 'all',
 'reqs': [{'req': '6.1910'},
          {'req': '6.2000'},
          {'req': '6.3100'},
          {'req': '6.9000'}],
 'threshold-desc': 'select all',
 'title': 'System Design'})
sixmod.append({'connection-type': 'any',
 'reqs': [{'req': '6.1100'},
          {'req': '6.1820'},
          {'req': '6.2040'},
          {'req': '6.2050'},
          {'req': '6.2060'},
          {'req': '6.2220'},
          {'req': '6.2221'},
          {'req': '6.2370'},
          {'req': '6.2410'},
          {'req': '6.2600'},
          {'req': '6.4200'},
          {'req': '6.4420'},
          {'req': '6.4510'},
          {'req': '6.4550'},
          {'req': '6.4860'}],
 'threshold': {'criterion': 'subjects', 'cutoff': 1, 'type': 'GTE'},
 'threshold-desc': 'select any',
 'title': 'PLAB'})

# %%
pprint(sixthree)
# %%

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

ccidx = courses_df[courses_df["subject_id"]=="6.2210"].index[0]
print(int(ccidx))
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
    # Dictionaries to track requirements
    infeasible_reqs = {}
    missing_courses = {}  # Track missing courses separately from infeasible requirements
    solution_status = {"is_feasible": True, "reasons": [], "flexible_requirements": {}}
    def process_requirement(req_item, counter=[0], parent_path="root"):
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

                #print(f"dummy mode failure for req item {req_item} with ps mode {'plain-string' in req_item}")
                #dummy_var = model.NewBoolVar(f"dummy_{course_code}")
                #aux_vars[f"dummy_{course_code}"] = dummy_var
                #model.Add(dummy_var == 0)
                req_code = req_item.get('req', 'unknown')
                path = f"{parent_path} -> {req_code}"
                # Store missing course info but don't report it as infeasible yet
                # The parent requirement with threshold or connection-type will determine
                # if this missing course actually causes infeasibility
                missing_courses[path] = {
                    'req_item': req_item,
                    'reason': f"Course code '{course_code}' not found in courses_df and not a recognized special requirement",
                    'type': 'missing_course',
                    'parent_path': parent_path
                }
                print(f"dummy mode failure for {req_item}, returning none")
                return None
        elif 'reqs' in req_item: #branch case
            sub_req_vars = []
            #print(f"branch for {req_item}")

            # Create a variable for this requirement group
            group_name = req_item.get('title', 'unnamed')
            if group_name == 'unnamed':
                counter[0] += 1
                group_name = f"unnamed_{counter[0]}"

            new_parent_path = f"{parent_path} -> {group_name}"

            # Process all sub-requirements
            none_count = 0

            for sub_req in req_item['reqs']:
                sub_var = process_requirement(sub_req, counter, new_parent_path)
                if sub_var is not None:
                    sub_req_vars.append(sub_var)
                    # Process the sub-requirement (specific handling moved to threshold section)
                    pass
                else:
                    none_count += 1

            # Check if the requirement is infeasible due to missing sub-requirements
            total_sub_reqs = len(req_item['reqs'])
            available_sub_reqs = len(sub_req_vars)

            placeholder = model.NewBoolVar(f"req_group_{group_name}")
            print(f"SETTING AUX VARS A {group_name} for reqitem {req_item}")
            aux_vars[group_name] = placeholder

            # Handle threshold if it exists (applies regardless of connection-type)
            if 'threshold' in req_item: #We don't really handle the LTE case very well, this assumes cutoff is GTE
                threshold = req_item['threshold']['cutoff']
                print(f"threshold mode with value {threshold}")

                # Log detailed information for debugging
                print(f"DEBUG - {group_name}: threshold={threshold}, total_sub_reqs={total_sub_reqs}, available_sub_reqs={available_sub_reqs}")

                # Determine whether to use leaf course counting or immediate sub-requirements
                # based on the threshold description and structure

                # First, define a helper function to count leaf courses recursively
                def count_leaf_courses(requirement):
                    if 'req' in requirement and not 'plain-string' in requirement:
                        # This is a leaf course requirement
                        course_code = requirement['req']
                        # Check if course exists in the database
                        if course_code in courses_df['subject_id'].values:
                            return 1
                        # Handle special requirements that are treated as available courses
                        elif course_code == "HASS" or course_code.startswith("GIR:") or \
                             course_code.startswith("HASS-") or course_code.startswith("CI-"):
                            return 1
                        # Missing course
                        return 0
                    elif 'reqs' in requirement:
                        # This is a group, recursively count all leaf courses
                        count = 0
                        for sub in requirement['reqs']:
                            count += count_leaf_courses(sub)
                        return count
                    return 0

                # Count all leaf courses and available leaf courses
                leaf_courses_count = 0
                available_leaf_courses = 0

                # Count all potential leaf courses first
                for i, sub_req in enumerate(req_item['reqs']):
                    sub_leaf_count = count_leaf_courses(sub_req)
                    leaf_courses_count += sub_leaf_count

                    # Check if this sub-requirement is available (not None)
                    # We need to look at the corresponding position in sub_req_vars
                    if i < len(sub_req_vars):
                        available_leaf_courses += sub_leaf_count

                # Determine how to interpret the threshold based on API documentation and structure:
                # 1. Check threshold.criterion - "subjects" or "units" indicates leaf course counting
                # 2. Check threshold-desc for hints (e.g., "select any 6 subjects" vs "select any 2 categories")
                # 3. Compare threshold against available counts at both levels as a fallback

                use_leaf_counting = False

                # 1. First check the criterion in the threshold definition
                if isinstance(req_item.get('threshold'), dict):
                    criterion = req_item['threshold'].get('criterion', '').lower()
                    if criterion == 'subjects' or criterion == 'units':
                        # "subjects" or "units" criterion indicates counting leaf courses
                        use_leaf_counting = True

                # 2. Check threshold-desc for hints if criterion didn't decide
                if not use_leaf_counting:
                    threshold_desc = req_item.get('threshold-desc', '').lower()
                    if threshold_desc:
                        if 'subject' in threshold_desc or 'course' in threshold_desc or 'unit' in threshold_desc:
                            use_leaf_counting = True
                        elif 'categor' in threshold_desc or 'track' in threshold_desc or 'group' in threshold_desc:
                            use_leaf_counting = False

                        # Special handling for EE Tracks requirement based on name
                        if group_name == "2 Subjects from each of 2 EE Tracks":
                            use_leaf_counting = True  # We want to count courses, not tracks

                # 3. If still undecided, use heuristics based on counts
                if not use_leaf_counting:
                    if threshold > total_sub_reqs and threshold <= leaf_courses_count:
                        use_leaf_counting = True
                    # Special case for Electives with threshold 6
                    if group_name == "Electives" and threshold == 6:
                        use_leaf_counting = True

                # 4. Check for distinct-threshold - this suggests we're counting distinct categories
                if req_item.get('distinct-threshold') is not None:
                    print(f"Found distinct-threshold in {group_name}, which indicates category-level counting")
                    use_leaf_counting = False

                if use_leaf_counting:
                    print(f"Using leaf course counting for {group_name}: {leaf_courses_count} total, {available_leaf_courses} available, threshold={threshold}")
                    check_total = leaf_courses_count
                    check_available = available_leaf_courses
                    using_leaf_counting = True
                else:
                    print(f"Using immediate sub-requirement counting for {group_name}: {total_sub_reqs} total, {available_sub_reqs} available, threshold={threshold}")
                    check_total = total_sub_reqs
                    check_available = available_sub_reqs
                    using_leaf_counting = False

                # Debug information about the decision
                # Get criterion for logging
                criterion = "unknown"
                if isinstance(req_item.get('threshold'), dict):
                    criterion = req_item['threshold'].get('criterion', 'unknown')

                print(f"Threshold interpretation for '{group_name}': {'LEAF COURSES' if use_leaf_counting else 'IMMEDIATE CHILDREN'}")
                print(f"Based on: threshold={threshold}, criterion='{criterion}', threshold_desc='{req_item.get('threshold-desc', '')}', immediate_children={total_sub_reqs}, leaf_courses={leaf_courses_count}")

                # Check if it's impossible to meet the threshold
                if check_total < threshold:
                    # Not even enough total options to meet threshold
                    additional_needed = threshold - check_total
                    infeasible_reqs[f"{parent_path} -> {group_name}"] = {
                        'req_item': req_item,
                        'reason': f"Threshold requirement needs {threshold} {req_item['threshold'].get('criterion', 'items') if using_leaf_counting else 'immediate sub-requirements'} but only {check_total} exist. Need {additional_needed} more.",
                        'type': 'threshold_impossible_not_enough_options',
                        'missing_reqs': none_count,
                        'additional_needed': additional_needed,
                        'using_leaf_counting': using_leaf_counting,
                        'check_total': check_total,
                        'check_available': check_available,
                        'type_detail': 'leaf_courses'
                    }
                    print(f"Marking {group_name} as infeasible: not enough total options ({check_total} < {threshold})")

                    # Don't force it to be unsatisfied if it's a flexible requirement that can be bypassed
                    if group_name in ["Electives", "Two Additional EECS"]:
                        # For flexible requirements, we'll try to satisfy as much as possible
                        print(f"FLEXIBLE REQUIREMENT: {group_name} marked as feasible despite threshold issues")
                    else:
                        model.Add(placeholder == 0)  # Force to be unsatisfied for non-flexible requirements

                    # For flexible requirements, let the solver try to optimize
                    if group_name in ["Electives", "Two Additional EECS"] and sub_req_vars:
                        if use_leaf_counting:
                            # Using the same approach as the feasible case but with reduced threshold
                            print(f"Creating flexible leaf course constraint for {group_name} with reduced threshold {min(threshold, check_total)}")

                            # Track which sub-requirements are satisfied
                            satisfied_subs = []
                            for i, sub_var in enumerate(sub_req_vars):
                                satisfied_sub = model.NewBoolVar(f"__internal_satisfied_sub_flex_{group_name}_{i}")
                                model.Add(sub_var == 1).OnlyEnforceIf(satisfied_sub)
                                model.Add(sub_var == 0).OnlyEnforceIf(satisfied_sub.Not())
                                satisfied_subs.append(satisfied_sub)

                            # Count leaf courses from satisfied sub-requirements
                            leaf_count_vars = []
                            for i, sub_req in enumerate(req_item['reqs']):
                                if i < len(satisfied_subs):
                                    leaf_count = count_leaf_courses(sub_req)
                                    if leaf_count > 0:
                                        leaf_var = model.NewIntVar(0, leaf_count, f"__internal_leaf_count_flex_{group_name}_{i}")
                                        model.Add(leaf_var == leaf_count).OnlyEnforceIf(satisfied_subs[i])
                                        model.Add(leaf_var == 0).OnlyEnforceIf(satisfied_subs[i].Not())
                                        leaf_count_vars.append(leaf_var)

                            # Sum up all leaf courses from satisfied sub-requirements
                            if leaf_count_vars:
                                leaf_sum = model.NewIntVar(0, leaf_courses_count, f"__internal_leaf_sum_flex_{group_name}")
                                model.Add(leaf_sum == sum(leaf_count_vars))

                                # Apply the reduced threshold constraint to the leaf course sum
                                model.Add(leaf_sum >= min(threshold, check_total)).OnlyEnforceIf(placeholder)
                                model.Add(leaf_sum < min(threshold, check_total)).OnlyEnforceIf(placeholder.Not())
                            else:
                                model.Add(placeholder == 0)
                        else:
                            # Original approach for immediate sub-requirements
                            sum_subs = sum(sub_req_vars)
                            model.Add(sum_subs >= min(threshold, check_total)).OnlyEnforceIf(placeholder)
                            model.Add(sum_subs < min(threshold, check_total)).OnlyEnforceIf(placeholder.Not())

                    # Special handling for "2 Subjects from each of 2 EE Tracks" - this needs custom constraints
                    elif group_name == "2 Subjects from each of 2 EE Tracks" and sub_req_vars:
                        print(f"Implementing custom constraints for {group_name}")

                        # We need to:
                        # 1. Count how many tracks have at least 2 courses
                        # 2. Check if at least 2 tracks have enough courses

                        # First, for each track, create a variable indicating if it has at least 2 courses
                        track_has_enough = []
                        for i, sub_req in enumerate(req_item['reqs']):
                            if i >= len(sub_req_vars):
                                continue

                            # Each sub_req here should be a track
                            track_name = sub_req.get('title', f'track_{i}')

                            # Create a variable for this track having enough courses
                            track_satisfied = model.NewBoolVar(f"track_{track_name}_has_2_courses")

                            # Count courses in this track if it has sub-requirements
                            if 'reqs' in sub_req:
                                # Count leaf courses in this track
                                leaf_count = count_leaf_courses(sub_req)

                                if leaf_count >= 2:
                                    # Check if the track is selected and has at least 2 courses
                                    # The track is considered to have enough courses if it's selected
                                    model.Add(track_satisfied == sub_req_vars[i])
                                else:
                                    # Not enough potential courses in this track
                                    model.Add(track_satisfied == 0)
                            else:
                                # Not a proper track structure
                                model.Add(track_satisfied == 0)

                            track_has_enough.append(track_satisfied)

                        # Now check if at least 2 tracks have enough courses
                        if len(track_has_enough) >= 2:
                            track_sum = model.NewIntVar(0, len(track_has_enough), f"sum_tracks_with_2_courses")
                            model.Add(track_sum == sum(track_has_enough))

                            # The requirement is satisfied if at least 2 tracks have enough courses
                            model.Add(track_sum >= 2).OnlyEnforceIf(placeholder)
                            model.Add(track_sum < 2).OnlyEnforceIf(placeholder.Not())
                        else:
                            # Not enough tracks to satisfy the requirement
                            model.Add(placeholder == 0)

                    print(f"CRITICAL INFEASIBILITY: {group_name} cannot satisfy threshold {threshold} with only {check_total} {'leaf courses' if using_leaf_counting else 'immediate sub-requirements'}")
                    solution_status["is_feasible"] = False
                    solution_status["reasons"].append(f"Requirement '{group_name}' needs {threshold} {'leaf courses' if using_leaf_counting else 'immediate sub-requirements'} but only {check_total} exist")
                elif check_available < threshold:
                    # Enough total options but too many are None
                    additional_needed = threshold - check_available
                    infeasible_reqs[f"{parent_path} -> {group_name}"] = {
                        'req_item': req_item,
                        'reason': f"Threshold requirement needs {threshold} {req_item['threshold'].get('criterion', 'items') if using_leaf_counting else 'immediate sub-requirements'} but only {check_available}/{check_total} are available. Need {additional_needed} more.",
                        'type': 'threshold_impossible_due_to_nones',
                        'missing_reqs': none_count,
                        'additional_needed': additional_needed,
                        'using_leaf_counting': using_leaf_counting,
                        'check_total': check_total,
                        'check_available': check_available,
                        'type_detail': 'leaf_courses'
                    }
                    print(f"Marking {group_name} as infeasible: not enough available options ({check_available} < {threshold})")
                    # All requirements must be satisfied - no more flexible exceptions
                    model.Add(placeholder == 0)  # Force to be unsatisfied
                    print(f"REQUIREMENT CANNOT BE MET: {group_name} threshold cannot be met")
                    # Keep the logic for computing leaf courses, but don't make it flexible
                    if sub_req_vars:
                        if use_leaf_counting:
                            # Using the same approach as the feasible case but with reduced threshold
                            print(f"Creating flexible leaf course constraint for {group_name} with reduced threshold {min(threshold, check_available)}")

                            # Track which sub-requirements are satisfied
                            satisfied_subs = []
                            for i, sub_var in enumerate(sub_req_vars):
                                satisfied_sub = model.NewBoolVar(f"__internal_satisfied_sub_flex2_{group_name}_{i}")
                                model.Add(sub_var == 1).OnlyEnforceIf(satisfied_sub)
                                model.Add(sub_var == 0).OnlyEnforceIf(satisfied_sub.Not())
                                satisfied_subs.append(satisfied_sub)

                            # Count leaf courses from satisfied sub-requirements
                            leaf_count_vars = []
                            for i, sub_req in enumerate(req_item['reqs']):
                                if i < len(satisfied_subs):
                                    leaf_count = count_leaf_courses(sub_req)
                                    if leaf_count > 0:
                                        leaf_var = model.NewIntVar(0, leaf_count, f"__internal_leaf_count_flex2_{group_name}_{i}")
                                        model.Add(leaf_var == leaf_count).OnlyEnforceIf(satisfied_subs[i])
                                        model.Add(leaf_var == 0).OnlyEnforceIf(satisfied_subs[i].Not())
                                        leaf_count_vars.append(leaf_var)

                            # Sum up all leaf courses from satisfied sub-requirements
                            if leaf_count_vars:
                                leaf_sum = model.NewIntVar(0, leaf_courses_count, f"__internal_leaf_sum_flex2_{group_name}")
                                model.Add(leaf_sum == sum(leaf_count_vars))

                                # Apply the reduced threshold constraint to the leaf course sum
                                model.Add(leaf_sum >= min(threshold, check_available)).OnlyEnforceIf(placeholder)
                                model.Add(leaf_sum < min(threshold, check_available)).OnlyEnforceIf(placeholder.Not())
                            else:
                                model.Add(placeholder == 0)
                        else:
                            # Original approach for immediate sub-requirements
                            sum_subs = sum(sub_req_vars)
                            model.Add(sum_subs >= min(threshold, check_available)).OnlyEnforceIf(placeholder)
                            model.Add(sum_subs < min(threshold, check_available)).OnlyEnforceIf(placeholder.Not())


                    print(f"CRITICAL INFEASIBILITY: {group_name} cannot satisfy threshold {threshold} with only {check_available} available {'leaf courses' if using_leaf_counting else 'immediate sub-requirements'}")
                    solution_status["is_feasible"] = False
                    solution_status["reasons"].append(f"Requirement '{group_name}' needs {threshold} {'leaf courses' if using_leaf_counting else 'immediate sub-requirements'} but only {check_available} are available")
                else:
                    print(f"Requirement {group_name} is feasible: threshold={threshold}, available={check_available}")

                    # For feasible requirements, we need to create appropriate constraints based on
                    # whether we're counting leaf courses or immediate sub-requirements
                    if use_leaf_counting:
                        # For leaf course counting, we need to ensure the threshold applies to actual leaf courses
                        print(f"Creating leaf course constraint for {group_name} with threshold {threshold}")

                        # Count how many leaf courses would be satisfied for each direct sub-requirement
                        # This is a more complex constraint that ensures leaf courses are properly counted
                        # First, track which sub-requirements are satisfied
                        satisfied_subs = []
                        for i, sub_var in enumerate(sub_req_vars):
                            satisfied_sub = model.NewBoolVar(f"__internal_satisfied_sub_{group_name}_{i}")
                            model.Add(sub_var == 1).OnlyEnforceIf(satisfied_sub)
                            model.Add(sub_var == 0).OnlyEnforceIf(satisfied_sub.Not())
                            satisfied_subs.append(satisfied_sub)

                        # Then count leaf courses from satisfied sub-requirements
                        leaf_count_vars = []
                        for i, sub_req in enumerate(req_item['reqs']):
                            if i < len(satisfied_subs):  # Only count available sub-requirements
                                leaf_count = count_leaf_courses(sub_req)
                                if leaf_count > 0:
                                    leaf_var = model.NewIntVar(0, leaf_count, f"__internal_leaf_count_{group_name}_{i}")
                                    model.Add(leaf_var == leaf_count).OnlyEnforceIf(satisfied_subs[i])
                                    model.Add(leaf_var == 0).OnlyEnforceIf(satisfied_subs[i].Not())
                                    leaf_count_vars.append(leaf_var)

                        # Sum up all leaf courses from satisfied sub-requirements
                        if leaf_count_vars:
                            leaf_sum = model.NewIntVar(0, leaf_courses_count, f"__internal_leaf_sum_{group_name}")
                            model.Add(leaf_sum == sum(leaf_count_vars))

                            # Now apply the threshold constraint to the leaf course sum
                            model.Add(leaf_sum >= threshold).OnlyEnforceIf(placeholder)
                            model.Add(leaf_sum < threshold).OnlyEnforceIf(placeholder.Not())
                        else:
                            # No leaf courses available, requirement can't be satisfied
                            model.Add(placeholder == 0)
                    else:
                        # For immediate sub-requirement counting, we can use the original approach
                        sum_subs = sum(sub_req_vars)
                        model.Add(sum_subs >= threshold).OnlyEnforceIf(placeholder)
                        model.Add(sum_subs < threshold).OnlyEnforceIf(placeholder.Not())

                    # All requirements are now hard constraints
                    print(f"Setting {group_name} as hard constraint")
            # If no threshold, use connection-type to determine constraint
            elif 'connection-type' in req_item:
                if req_item['connection-type'] == 'all':
                    print("all mode (no threshold)")
                    if none_count > 0:
                        # All-of is infeasible if any sub-requirement is None
                        infeasible_reqs[f"{parent_path} -> {group_name}"] = {
                            'req_item': req_item,
                            'reason': f"All-of requirement missing {none_count}/{total_sub_reqs} sub-requirements",
                            'type': 'all_missing_reqs',
                            'missing_reqs': none_count
                        }
                        print(f"CRITICAL INFEASIBILITY: All-of requirement {group_name} missing {none_count} sub-requirements")
                        solution_status["is_feasible"] = False
                        solution_status["reasons"].append(f"All-of requirement '{group_name}' missing {none_count} required sub-requirements")

                    if not sub_req_vars:
                        model.Add(placeholder == 1)  # Empty case, technically satisfied
                    else:
                        model.AddMinEquality(placeholder, sub_req_vars)
                elif req_item['connection-type'] == 'any':
                    print("any mode (no threshold)")
                    # Any-of is infeasible only if all sub-requirements are None
                    if available_sub_reqs == 0:
                        infeasible_reqs[f"{parent_path} -> {group_name}"] = {
                            'req_item': req_item,
                            'reason': f"Any-of requirement has all {total_sub_reqs} sub-requirements missing",
                            'type': 'any_all_missing',
                            'missing_reqs': none_count
                        }
                        model.Add(placeholder == 0)  # Cannot be satisfied
                        print(f"CRITICAL INFEASIBILITY: Any-of requirement {group_name} has all {total_sub_reqs} sub-requirements missing")
                        solution_status["is_feasible"] = False
                        solution_status["reasons"].append(f"Any-of requirement '{group_name}' has all {total_sub_reqs} sub-requirements missing")
                    elif sub_req_vars:
                        model.AddMaxEquality(placeholder, sub_req_vars)
                    else:
                        model.Add(placeholder == 0)  # Empty 'any' cannot be satisfied
            # Default behavior (no threshold or connection-type specified)
            else:
                print("default mode (all)")
                if none_count > 0:
                    # Behaves like 'all', so infeasible if any sub-requirement is None
                    infeasible_reqs[f"{parent_path} -> {group_name}"] = {
                        'req_item': req_item,
                        'reason': f"Default all-of requirement missing {none_count}/{total_sub_reqs} sub-requirements",
                        'type': 'default_missing_reqs',
                        'missing_reqs': none_count
                    }
                    print(f"CRITICAL INFEASIBILITY: Default all-of requirement {group_name} missing {none_count} sub-requirements")
                    solution_status["is_feasible"] = False
                    solution_status["reasons"].append(f"Default all-of requirement '{group_name}' missing {none_count} sub-requirements")

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

        # Ensure all top-ldevel requirements are satisfied
        for var in req_vars:
            model.Add(var == 1)
    else:
        print("doing type b")
        req_var = process_requirement(req_val)
        if req_var is not None:
            model.Add(req_var == 1)

    # Find critical missing courses - those that make a requirement infeasible
    critical_missing_courses = {}
    for path, details in missing_courses.items():
        parent_path = details.get('parent_path')
        # If the parent requirement is in infeasible_reqs, this is a critical missing course
        if any(parent_path in infeas_path for infeas_path in infeasible_reqs):
            critical_missing_courses[path] = details

    # At this point we know if the solution is theoretically feasible
    # Set the fallback solution status
    solution_status["relaxed_mode"] = False
    if solution_status["is_feasible"]:
        print("\n===== SOLUTION STATUS: FEASIBLE =====")
        print("All requirements can be satisfied with available courses")
    else:
        print("\n===== SOLUTION STATUS: POTENTIALLY INFEASIBLE =====")
        print("Some requirements might not be fully satisfiable, but we'll try to find the best solution:")
        for reason in solution_status["reasons"]:
            print(f"- {reason}")
        # Set a global flag to inform other parts of the code that some requirements are relaxed
        solution_status["relaxed_requirements"] = True
    print("======================================\n")

    # Report on infeasible requirements and critical missing courses if any were found
    if infeasible_reqs or critical_missing_courses:
        print("\n===== INFEASIBLE REQUIREMENTS REPORT =====")
        all_infeasible = len(infeasible_reqs) + len(critical_missing_courses)
        print(f"Found {all_infeasible} potentially infeasible requirements:")

        # Group by type for better reporting
        by_type = {}
        # First add critical missing courses
        for path, details in critical_missing_courses.items():
            req_type = details.get('type', 'unknown')
            if req_type not in by_type:
                by_type[req_type] = []
            by_type[req_type].append((path, details))

        # Then add infeasible requirements
        for path, details in infeasible_reqs.items():
            req_type = details.get('type', 'unknown')
            if req_type not in by_type:
                by_type[req_type] = []
            by_type[req_type].append((path, details))

        # Print by type
        for req_type, items in by_type.items():
            print(f"\n== {req_type.upper().replace('_', ' ')} ({len(items)} issues) ==")
            for path, details in items:
                print(f"\nPath: {path}")
                req_title = details['req_item'].get('title', 'Unnamed')
                print(f"Requirement: {req_title}")
                print(f"Reason: {details['reason']}")
                if 'missing_reqs' in details and details['missing_reqs'] > 0:
                    print(f"Missing (None'd): {details['missing_reqs']} sub-requirements")
                if 'additional_needed' in details:
                    print(f"Additional needed: {details['additional_needed']} more sub-requirements")
                if details.get('using_leaf_counting', False):
                    print(f"Note: Threshold applies to all leaf course requirements ({details.get('check_total', '?')} total, {details.get('check_available', '?')} available)")
                else:
                    print(f"Note: Threshold applies to immediate sub-requirements ({details.get('check_total', '?')} total, {details.get('check_available', '?')} available)")

        print("=========================================\n")

    # Print information about non-critical missing courses if debug mode is enabled
    if missing_courses and len(missing_courses) > len(critical_missing_courses):
        non_critical = len(missing_courses) - len(critical_missing_courses)
        print(f"\nNote: {non_critical} missing courses were found but don't affect solution feasibility")
        print("(These courses are in requirements with thresholds that can still be satisfied with other courses)")
        print("To see details, enable debug mode\n")

    # Debug info for requirements
    print("\n===== REQUIREMENT FEASIBILITY SUMMARY =====")
    if infeasible_reqs:
        print(f"Found {len(infeasible_reqs)} infeasible requirements that prevent a solution")
        for path in infeasible_reqs.keys():
            print(f"- {path}")
    else:
        print("No infeasible requirements detected in our tracking system")
    print("===========================================\n")

    # Don't add solution_status to aux_vars since it's a dictionary, not a CP-SAT variable
    # Store it separately for later use
    global_solution_status = solution_status

    # Initialize tracking for flexible requirements
    if "flexible_requirements" not in solution_status:
        solution_status["flexible_requirements"] = {}

    # If we have some infeasible requirements but they're flexible, we should still continue
    # This flag helps the solver know that we're operating in a relaxed mode
    if not solution_status["is_feasible"]:
        print("Operating in relaxed constraint mode - will try to find best partial solution")
        solution_status["relaxed_mode"] = True

    aux_vars["solution_status"] = solution_status

    return aux_vars

group_vars = {}
add_requirement_constraints(model, take, girs, courses_df, planning_year_start, group_vars)
add_requirement_constraints(model, take, sixthree, courses_df, planning_year_start, group_vars)


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
   # print(f"root is {condition}")
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
        self.flexible_reqs_status = {}

    def on_solution_callback(self) -> None:
        self.__solution_count += 1
        print(f"Step {self.__solution_count}:")

        # Define flexible requirements to track
        flexible_reqs = ["Electives", "Two Additional EECS"]

        # Record the status of flexible requirements
        for req in flexible_reqs:
            if req in self.group_vars:
                try:
                    self.flexible_reqs_status[req] = self.Value(self.group_vars[req]) == 1
                    if not self.flexible_reqs_status[req]:
                        print(f"NOTE: Flexible requirement '{req}' is NOT satisfied (value = 0)")
                except:
                    print(f"Could not check status of {req}")
                    self.flexible_reqs_status[req] = False

        semester_units = [0] * 12
        for (c, s), v in self.take.items():
            if self.Value(v) != 0:
                print(f"take[{classes.loc[c]}, {s}] = {self.Value(v)}")
                semester_units[s - 1] += self.units.loc[c] * self.Value(v)
        print("Units per semester:", semester_units)
        if self.group_vars:
            print("Group Vars:")
            for name, var in self.group_vars.items():
                try:
                    # Use a safe approach - don't check types directly
                    # Just try to get the value and handle exceptions
                    value = self.Value(var)
                    print(f"group_var[{name}] = {value}")
                except Exception as e:
                    print(f"group_var[{name}] = [Error: {str(e)}]")
        print()

    @property
    def solution_count(self) -> int:
        return self.__solution_count

# Objective
printer = VarArraySolutionPrinter(take, group_vars, units)
finish_time = sum(take[idx, s] for idx in classes.index for s in range(1, 13) if is_valid_class_semester(idx, s, courses_df, planning_year_start))
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

    # Check and report on flexible requirements that weren't satisfied
    unsatisfied_flex_reqs = [req for req, satisfied in printer.flexible_reqs_status.items()
                           if not satisfied]

    # Check the specific "2 Subjects from each of 2 EE Tracks" requirement
    ee_tracks_var_name = "2 Subjects from each of 2 EE Tracks"
    if ee_tracks_var_name in printer.group_vars and printer.Value(printer.group_vars[ee_tracks_var_name]) == 0:
        unsatisfied_flex_reqs.append(ee_tracks_var_name)

    if unsatisfied_flex_reqs:
        print("\n⚠️ WARNING: Some flexible requirements could not be satisfied:")
        for req in unsatisfied_flex_reqs:
            print(f"  - {req}")
        print("\nThe solution is still considered feasible because these are flexible requirements.")

    # Remove duplicate warning - this was already handled above
    # Check for unsatisfied flexible requirements
    solution_status = {}
    unsatisfied_global = []
    if 'global_solution_status' in globals():
        solution_status = globals()['global_solution_status']
        if 'flexible_requirements' in solution_status:
            unsatisfied_global = [name for name, satisfied in solution_status["flexible_requirements"].items()
                                if satisfied is False]
            if unsatisfied_global:
                print("\nWARNING: The following flexible requirements could not be satisfied:")
                for req in unsatisfied_global:
                    print(f"  - {req}")
                print("\nThe solution is still considered feasible because these are flexible requirements.")

    # Remove duplicate warnings - we've already handled this above
if res == cp_model.INFEASIBLE:
    print('The solver found the problem to be infeasible.')
    # Create a new solution_status for infeasible case
    infeasible_status = {"relaxed_mode": False}
    if 'global_solution_status' in globals():
        infeasible_status = globals()['global_solution_status']
    if infeasible_status.get('relaxed_mode', False):
        print('However, we\'re in relaxed mode, so this may be acceptable for certain requirements.')
        print('Review the requirement feasibility summary above for details.')

        # Check if we have information about which flexible requirements failed
        if solution_status.get('flexible_requirements'):
            unsatisfied = [name for name, satisfied in solution_status['flexible_requirements'].items()
                          if not satisfied]
            if unsatisfied:
                print("\nThe following flexible requirements could not be satisfied:")
                for req in unsatisfied:
                    print(f"  - {req}")
                print("\nThe solution is still considered feasible because these are flexible requirements.")
    else:
        print('This means some hard constraint cannot be satisfied.')
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
