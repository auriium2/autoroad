"""
my poor decision of courses will be forever memorialized in this pytest. FUCK 6.1010.
"""
import json
import tempfile

import polars as pl
import pytest
import requests
from ortools.sat.python import cp_model

from api.models.requests import Marker
from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
from courses.requirements.parser import parse_fireroad_response
from courses.requirements.validator import validate_and_prune
from optimizer.constraints.basic import add_basic_constraints, create_take_vars
from optimizer.objectives.builder import ObjectiveBuilder
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirements.builder import add_requirement_constraints


@pytest.mark.e2e
@pytest.mark.slow
def test_feasibility_bug_major_6_3_with_markers():
    """
    Reproduce bug where optimizer says FEASIBLE but Fireroad says INFEASIBLE.

    Setup:
    - Class of 2028 (planning_year_start = 2024)
    - Freeze past semesters mode enabled
    - Requirements: major6-3new + girs
    - Markers: ASE (18.01, 6.100A) + specific courses pinned/overridden in semesters

    Expected: Either solver should say INFEASIBLE, OR the generated solution should
    validate successfully against Fireroad API.

    Actual Bug: Solver says FEASIBLE, but Fireroad validation fails.
    """
    # Setup markers exactly as in the bug report
    markers = [
        # ASE (section -1)
        Marker(courseId='18.01', status='pin', section=-1),
        Marker(courseId='6.100A', status='pin', section=-1),

        # Freshman Fall (section 0)
        Marker(courseId='18.02', status='pin', section=0),
        Marker(courseId='18.C06', status='override', section=0),
        Marker(courseId='24.900', status='pin', section=0),
        Marker(courseId='8.01', status='pin', section=0),

        # Freshman IAP (section 1)
        Marker(courseId='18.031', status='pin', section=1),

        # Freshman Spring (section 2)
        Marker(courseId='2.001', status='pin', section=2),
        Marker(courseId='2.003', status='override', section=2),
        Marker(courseId='2.086', status='pin', section=2),
        Marker(courseId='21W.011', status='pin', section=2),
        Marker(courseId='18.03', status='pin', section=2),

        # Sophomore Fall (section 3)
        Marker(courseId='6.3900', status='override', section=3),
        Marker(courseId='6.1010', status='override', section=3),
        Marker(courseId='21T.220', status='pin', section=3),
        Marker(courseId='7.015', status='pin', section=3),
    ]

    # Get data
    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

    requirements_data = get_requirements(('major6-3new', 'girs'))
    prereq_trees = get_parsed_prerequisites(courses_df)

    # Create model
    model = cp_model.CpModel()
    planning_year_start = 2024
    max_semesters = 12

    take_vars = create_take_vars(model, courses_df, planning_year_start, max_semesters, markers)
    add_basic_constraints(model, take_vars, courses_df, max_semesters)

    # Add past semester constraints (freeze past semesters mode enabled)
    from optimizer.constraints.basic import add_past_semester_constraints
    past_constraints = add_past_semester_constraints(model, take_vars, courses_df, planning_year_start, markers)

    print(f"\n[TEST] Created {len(take_vars)} decision variables")
    print(f"[TEST] Past semester constraints (freeze mode): {past_constraints}")

    # Add marker constraints
    from optimizer.marker_constraint_builder import add_marker_constraints
    marker_result = add_marker_constraints(model, take_vars, markers, courses_df, planning_year_start)
    print(f"[TEST] Marker constraints: {marker_result.constraints_added}")

    # Add prerequisite constraints (with override courses skipping prereqs)
    override_course_ids = {m.courseId for m in markers if m.status == 'override'}
    prereq_result, _ = add_prerequisite_constraints(
        model, take_vars, courses_df, planning_year_start, prereq_trees, override_course_ids
    )
    print(f"[TEST] Prerequisite constraints: {prereq_result.constraints_added}")

    # Add requirement constraints
    course_to_requirements = {}
    for req_key in ['major6-3new', 'girs']:
        if req_key in requirements_data:
            req_data = requirements_data[req_key]
            if isinstance(req_data, dict):
                req_tree = parse_fireroad_response(req_data)
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                if validation.pruned_tree is not None:
                    aux_vars, debug_names, mapping = add_requirement_constraints(
                        model, take_vars, validation.pruned_tree,
                        courses_df, req_key, enforce=True
                    )
                    # Merge mappings
                    for course_idx, req_paths in mapping.items():
                        if course_idx not in course_to_requirements:
                            course_to_requirements[course_idx] = set()
                        course_to_requirements[course_idx].update(req_paths)
                    print(f"[TEST] Added requirements for {req_key}")

    # Add objectives using the default objectives (same as the actual optimizer)
    from optimizer.objectives.registry import get_default_objectives, instantiate_objective
    builder = ObjectiveBuilder()

    for key, params in get_default_objectives():
        objective_instance = instantiate_objective(key, params)
        builder.add(objective_instance, key=key)

    objective = builder.build(
        model, take_vars, courses_df, planning_year_start,
        course_to_requirements=course_to_requirements
    )
    model.Minimize(objective)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    print("[TEST] Starting solve...")
    status = solver.Solve(model)

    print(f"[TEST] Solver status: {status}")
    print(f"[TEST] Objective value: {solver.ObjectiveValue() if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else 'N/A'}")

    # THIS IS THE BUG: Solver says FEASIBLE
    assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
        "Solver should report feasible (this is the bug - it reports feasible when it shouldn't)"

    # Extract the solution
    solution_courses = []
    for (course_idx, semester_internal), var in take_vars.items():
        if solver.Value(var) == 1:
            course_id = courses_df[course_idx, 'subject_id']
            title = courses_df[course_idx, 'title'] if 'title' in courses_df.columns else course_id
            units = courses_df[course_idx, 'total_units'] if 'total_units' in courses_df.columns else 12

            # semester_internal is 1-indexed for regular (1-12), or -1 for ASE
            # For Fireroad API, we need semester (0 for ASE, 1-12 for regular)
            if semester_internal == -1:
                semester_fireroad = 0  # ASE
            else:
                semester_fireroad = semester_internal  # Already 1-indexed

            solution_courses.append({
                'subject_id': course_id,
                'title': title,
                'units': int(units) if units else 12,
                'semester': semester_fireroad
            })

    print(f"[TEST] Solution has {len(solution_courses)} courses")

    # Save the solution to a .road file
    road_output = {
        'coursesOfStudy': ['major6-3new', 'girs'],
        'selectedSubjects': solution_courses
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='_bug_reproduction_result.road', delete=False) as f:
        json.dump(road_output, f, indent=2)
        print(f"[TEST] Saved solution to {f.name}")

    # Now validate against Fireroad API
    # This is what the frontend does to check if requirements are satisfied
    print("[TEST] Validating solution against Fireroad API...")

    # Convert to Fireroad "road" format (what the frontend sends)
    road_payload = {
        'coursesOfStudy': ['major6-3new', 'girs'],
        'selectedSubjects': solution_courses,
        'progressOverrides': {},
        'progressAssertions': {}
    }

    print(f"[TEST] Sending {len(solution_courses)} courses to Fireroad API")

    # Helper to check if requirement node is fulfilled (Fireroad uses 'fulfilled' not 'satisfied')
    def check_requirement_fulfilled(req_node, path="", indent=0):
        """
        Check if the top-level requirement node is fulfilled.
        Only checks the 'fulfilled' field at this level - does not recursively check children.
        """
        if isinstance(req_node, dict):
            title = req_node.get('title', 'Unknown')
            fulfilled = req_node.get('fulfilled', False)

            prefix = "  " * indent

            # Check if this node is not fulfilled
            if not fulfilled:
                sat_courses = req_node.get('sat_courses', [])
                progress = req_node.get('progress', 0)
                max_needed = req_node.get('max', '?')

                print(f"{prefix}[TEST] ❌ NOT fulfilled: {path}/{title}")
                print(f"{prefix}       Progress: {progress}/{max_needed}")
                print(f"{prefix}       Satisfied courses: {sat_courses if sat_courses else '(none)'}")

                # Show first few sub-requirements if present
                if 'reqs' in req_node and isinstance(req_node['reqs'], list) and len(req_node['reqs']) > 0:
                    print(f"{prefix}       Sub-requirements:")
                    for i, sub in enumerate(req_node['reqs'][:5]):  # Show first 5
                        if isinstance(sub, dict):
                            sub_title = sub.get('title', sub.get('req', 'Unknown'))
                            sub_fulfilled = sub.get('fulfilled', False)
                            sub_progress = sub.get('progress', 0)
                            sub_max = sub.get('max', '?')
                            status = '✓' if sub_fulfilled else '✗'
                            print(f"{prefix}         [{i}] {status} {sub_title} ({sub_progress}/{sub_max})")

                return False

            return True

        return True

    # Call Fireroad API for each requirement separately
    all_satisfied = True
    for req_key in ['major6-3new', 'girs']:
        # Create payload exactly like frontend does
        req_payload = {
            'coursesOfStudy': [req_key],
            'selectedSubjects': solution_courses,
            'progressAssertions': {}
        }

        # IMPORTANT: Fireroad API requires trailing slash!
        response = requests.post(
            f'https://fireroad.mit.edu/requirements/progress/{req_key}/',  # Note trailing slash
            json=req_payload,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=30
        )

        print(f"[TEST] Fireroad API status for {req_key}: {response.status_code}")

        if response.status_code != 200:
            print(f"[TEST] Fireroad API error for {req_key}: {response.text}")
            pytest.fail(f"Fireroad API returned error {response.status_code} for {req_key}: {response.text}")

        fireroad_result = response.json()

        # Save the full Fireroad response for debugging
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'_fireroad_response_{req_key}.json', delete=False) as f:
            json.dump(fireroad_result, f, indent=2)
            print(f"[TEST] Saved Fireroad response for {req_key} to {f.name}")

        # Check if this requirement is fulfilled
        req_fulfilled = check_requirement_fulfilled(fireroad_result, req_key)
        if req_fulfilled:
            print(f"[TEST] ✓ Requirement {req_key} FULFILLED according to Fireroad")
        else:
            all_satisfied = False
            print(f"[TEST] ❌ Requirement {req_key} NOT fulfilled according to Fireroad")

    # Check if bug is reproduced
    if not all_satisfied:
        pytest.fail(
            "BUG REPRODUCED: Optimizer reported FEASIBLE but Fireroad validation "
            "shows requirements are NOT satisfied. This means our requirement "
            "constraint builder has a bug and is not correctly enforcing requirements."
        )
    else:
        print("\n[TEST] ✓✓✓ All requirements FULFILLED according to Fireroad!")
        print("[TEST] The optimizer correctly generated a valid solution.")


if __name__ == '__main__':
    pytest.main([__file__, '-xvs'])
