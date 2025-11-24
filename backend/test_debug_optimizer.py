"""Debug script to see what the optimizer is actually selecting."""

import polars as pl
from ortools.sat.python import cp_model

from api.routes.optimize import add_basic_constraints, create_take_vars
from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints


def debug_optimizer():
    """Debug what courses the optimizer is selecting."""
    # Fetch real data
    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)

    requirements_data = get_requirements(('major6-3new', 'girs'))
    prereq_trees = get_parsed_prerequisites(courses_df)

    # Create model
    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
    add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

    print(f"\n[DEBUG] Created {len(take_vars)} take variables")

    # Add prerequisites
    prereq_result = add_prerequisite_constraints(
        model, take_vars, courses_df, 2024, prereq_trees, set()
    )
    print(f"[DEBUG] Prerequisite constraints: {prereq_result.constraints_added}")

    # Add requirements
    for req_key in ['major6-3new', 'girs']:
        if req_key in requirements_data:
            req_data = requirements_data[req_key]
            if isinstance(req_data, dict):
                req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                if validation.pruned_tree is not None:
                    aux_vars, debug_names, course_to_reqs = add_requirement_constraints(
                        model, take_vars, validation.pruned_tree,
                        courses_df, 2024, req_key, enforce=True
                    )
                    print(f"[DEBUG] {req_key} added (aux_vars: {len(aux_vars)})")

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    print("[DEBUG] Starting solve...")
    status = solver.Solve(model)
    print(f"[DEBUG] Solver status: {status}")

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        # Extract selected courses
        selected_courses = []
        subject_ids = courses_df['subject_id'].to_list()
        
        for (course_idx, semester), var in take_vars.items():
            if solver.Value(var) == 1:
                course_id = subject_ids[course_idx]
                selected_courses.append((course_id, semester))
        
        selected_courses.sort(key=lambda x: x[1])  # Sort by semester
        
        print(f"\n[DEBUG] Selected {len(selected_courses)} courses:")
        for course_id, semester in selected_courses:
            print(f"  Semester {semester}: {course_id}")
        
        # Count courses by semester
        from collections import Counter
        semester_counts = Counter(s for _, s in selected_courses)
        print(f"\n[DEBUG] Courses per semester:")
        for sem in sorted(semester_counts.keys()):
            print(f"  Semester {sem}: {semester_counts[sem]} courses")
        
        print(f"\n[DEBUG] Total unique courses: {len(set(c for c, _ in selected_courses))}")
    else:
        print("[DEBUG] No solution found!")


if __name__ == "__main__":
    debug_optimizer()
