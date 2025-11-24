"""Check if requirements are actually being enforced."""

import polars as pl
from ortools.sat.python import cp_model

from api.routes.optimize import add_basic_constraints, create_take_vars
from api.services.cache import get_courses_data, get_requirements
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.requirement_constraint_builder import add_requirement_constraints


def check_enforcement():
    """Check if requirements are enforced."""
    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    requirements_data = get_requirements(('major6-3new', 'girs'))

    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, 2024, max_semesters=8, markers=None)
    add_basic_constraints(model, take_vars, courses_df, max_semesters=8)

    print(f"\n[CHECK] Initial model has {model.Proto().constraints_size} constraints")

    for req_key in ['major6-3new', 'girs']:
        if req_key in requirements_data:
            req_data = requirements_data[req_key]
            if isinstance(req_data, dict):
                req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                
                print(f"\n[CHECK] Processing {req_key}:")
                print(f"  - Pruned tree exists: {validation.pruned_tree is not None}")
                
                if validation.pruned_tree is not None:
                    constraints_before = model.Proto().constraints_size
                    
                    aux_vars, debug_names, course_to_reqs = add_requirement_constraints(
                        model, take_vars, validation.pruned_tree,
                        courses_df, 2024, req_key, enforce=True
                    )
                    
                    constraints_after = model.Proto().constraints_size
                    added = constraints_after - constraints_before
                    
                    print(f"  - Aux vars created: {len(aux_vars)}")
                    print(f"  - Constraints added: {added}")
                    print(f"  - Courses mapped to requirements: {len(course_to_reqs)}")


if __name__ == "__main__":
    check_enforcement()
