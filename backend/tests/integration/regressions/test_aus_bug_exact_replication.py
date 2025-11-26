"""
my poor choice in classes is forever memorialized in this pytest file. FUCK 6.1010. also 2.001.
"""

import polars as pl
from ortools.sat.python import cp_model

from shared.courses.requirements.parser import parse_fireroad_response
from shared.courses.requirements.types import (
    AllGroup,
    AnyGroup,
    Course,
    Node,
    SubjectThresholdGroup,
    UnitThresholdGroup,
)
from shared.courses.requirements.validator import validate_and_prune
from shared.optimizer.constraints.basic import add_basic_constraints, create_take_vars
from shared.optimizer.marker_constraint_builder import add_marker_constraints
from shared.optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from shared.optimizer.requirements.builder import add_requirement_constraints
from shared.models.requests import Marker
from shared.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements


def test_aus_bug_with_exact_solution():
    """
    Test with every course pinned to exact semesters from optimization_result.road.

    The result has:
    - 6.C01 in Junior Spring (section 8)
    - 18.404 in Senior Fall (section 9)
    - 6.C011 NOT taken

    According to Fireroad, this only satisfies 1/2 of the AUS requirement because
    the 6.C01/6.C011 group requires BOTH courses (connection-type='all').

    The optimizer should report INFEASIBLE or AUS aux var should be 0.
    """
    # Pin every course from the actual result to its exact semester
    markers = [
        Marker(courseId='10.07', status='pin', section=5),
        Marker(courseId='16.C20', status='pin', section=8),
        Marker(courseId='18.01', status='pin', section=-1),
        Marker(courseId='18.01L', status='pin', section=6),
        Marker(courseId='18.02', status='pin', section=0),
        Marker(courseId='18.03', status='pin', section=2),
        Marker(courseId='18.031', status='pin', section=1),
        Marker(courseId='18.404', status='pin', section=9),
        Marker(courseId='18.C06', status='override', section=0),
        Marker(courseId='2.001', status='pin', section=2),
        Marker(courseId='2.003', status='override', section=2),
        Marker(courseId='2.086', status='pin', section=2),
        Marker(courseId='21T.220', status='pin', section=3),
        Marker(courseId='21W.011', status='pin', section=2),
        Marker(courseId='24.900', status='pin', section=0),
        Marker(courseId='3.095', status='pin', section=5),
        Marker(courseId='3.983', status='pin', section=9),
        Marker(courseId='5.112', status='pin', section=9),
        Marker(courseId='6.100A', status='pin', section=-1),
        Marker(courseId='6.100L', status='pin', section=6),
        Marker(courseId='6.1010', status='override', section=3),
        Marker(courseId='6.1020', status='pin', section=8),
        Marker(courseId='6.1200', status='pin', section=5),
        Marker(courseId='6.1210', status='pin', section=6),
        Marker(courseId='6.1400', status='pin', section=11),
        Marker(courseId='6.1800', status='pin', section=11),
        Marker(courseId='6.1904', status='pin', section=5),
        Marker(courseId='6.1910', status='pin', section=8),
        Marker(courseId='6.3900', status='override', section=3),
        Marker(courseId='6.4590', status='pin', section=11),
        Marker(courseId='6.C01', status='pin', section=8),
        Marker(courseId='7.015', status='pin', section=3),
        Marker(courseId='8.01', status='pin', section=0),
        Marker(courseId='8.022', status='pin', section=6),
        Marker(courseId='STS.081', status='pin', section=9),
    ]

    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    requirements_data = get_requirements(('major6-3new',))
    prereq_trees = get_parsed_prerequisites(courses_df)

    # Get course indices
    course_id_to_idx = {}
    for idx in range(len(courses_df)):
        course_id = courses_df[idx, 'subject_id']
        course_id_to_idx[course_id] = idx

    c01_idx = course_id_to_idx.get('6.C01')
    c011_idx = course_id_to_idx.get('6.C011')
    c404_idx = course_id_to_idx.get('18.404')

    print(f"\n6.C01 index: {c01_idx}")
    print(f"6.C011 index: {c011_idx}")
    print(f"18.404 index: {c404_idx}")

    # Create model
    model = cp_model.CpModel()
    planning_year_start = 2024
    max_semesters = 12

    take_vars = create_take_vars(model, courses_df, planning_year_start, max_semesters, markers)
    add_basic_constraints(model, take_vars, courses_df, max_semesters)

    print(f"\nCreated {len(take_vars)} decision variables")

    # Add marker constraints
    marker_result = add_marker_constraints(model, take_vars, markers, courses_df, planning_year_start)
    print(f"Marker constraints: {marker_result.constraints_added}")

    # Add prerequisite constraints
    override_course_ids = {m.courseId for m in markers if m.status == 'override'}
    prereq_result, _ = add_prerequisite_constraints(
        model, take_vars, courses_df, planning_year_start, prereq_trees, override_course_ids
    )
    print(f"Prerequisite constraints: {prereq_result.constraints_added}")

    # Add requirement constraints
    req_data = requirements_data['major6-3new']
    assert isinstance(req_data, dict)
    req_tree = parse_fireroad_response(req_data)

    print("\n=== VALIDATION DEBUG ===")
    validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)

    print(f"\nValidation feasible: {validation.is_feasible}")
    print(f"Removed courses: {validation.removed_courses}")
    print(f"\nValidation warnings ({len(validation.warnings)}):")
    for warning in validation.warnings:
        print(f"  {warning}")

    # Check if AUS is in the pruned tree
    def find_requirement(node: Node, title_or_id: str) -> Node | None:
        """Recursively find a requirement by title or req_id"""
        if hasattr(node, 'title') and node.title == title_or_id:
            return node
        if hasattr(node, 'req_id') and node.req_id == title_or_id:
            return node

        if isinstance(node, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
            for item in node.children:
                found = find_requirement(item, title_or_id)
                if found:
                    return found
        return None

    def find_all_requirements(node: Node, title_or_id: str, path: str = "root") -> list[tuple[str, Node]]:
        """Recursively find ALL occurrences of a requirement by title or req_id"""
        results: list[tuple[str, Node]] = []

        if hasattr(node, 'title') and node.title == title_or_id:
            results.append((path, node))
        if hasattr(node, 'req_id') and node.req_id == title_or_id:
            results.append((path, node))

        if isinstance(node, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
            for idx, item in enumerate(node.children):
                child_path = f"{path}.{idx}"
                results.extend(find_all_requirements(item, title_or_id, child_path))
        return results

    if validation.pruned_tree:
        # Find ALL occurrences of AUS
        all_aus = find_all_requirements(validation.pruned_tree, 'AUS')
        print(f"\nFound {len(all_aus)} occurrence(s) of AUS:")
        for path, node in all_aus:
            print(f"  Path: {path}, was_pruned={node.was_pruned}")

        aus_node = find_requirement(validation.pruned_tree, 'AUS')
        if aus_node:
            print(f"\nFound AUS node: was_pruned={aus_node.was_pruned}")

            # Deep dive into AUS structure
            if isinstance(aus_node, SubjectThresholdGroup):
                print(f"  AUS connection_type: {aus_node.connection_type}")
                print(f"  AUS cutoff: {aus_node.cutoff}")
                print(f"  AUS has {len(aus_node.children)} direct children")

                # Count valid children
                valid_children = 0
                for i, child in enumerate(aus_node.children):
                    child_pruned = hasattr(child, 'was_pruned') and child.was_pruned
                    if not child_pruned:
                        valid_children += 1
                    title = getattr(child, 'title', 'no title')
                    print(f"    Child {i}: {title}, was_pruned={child_pruned}")

                print(f"  Valid children: {valid_children}/{len(aus_node.children)}")

                # Check child 40 specifically (the one being skipped)
                if len(aus_node.children) > 40:
                    child_40 = aus_node.children[40]
                    c40_pruned = hasattr(child_40, 'was_pruned') and child_40.was_pruned
                    c40_type = type(child_40).__name__
                    if isinstance(child_40, Course):
                        c40_title = child_40.subject_id
                    else:
                        c40_title = getattr(child_40, 'title', 'no title')
                    print(f"\n  ⚠️  Child 40 (the one being skipped): type={c40_type}, course_id={c40_title}, was_pruned={c40_pruned}")
                    print("     This is the unavailable course that was correctly marked as pruned.")

                # Check threshold requirements
                def count_valid_courses(n: Node) -> int:
                    if isinstance(n, Course):
                        return 0 if n.was_pruned else 1
                    elif isinstance(n, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
                        return sum(count_valid_courses(item) for item in n.children)
                    return 0

                available = count_valid_courses(aus_node)
                print(f"  Available subjects: {available}")
                print(f"  Required subjects: {aus_node.cutoff}")
                print(f"  AUS should be feasible: {available >= aus_node.cutoff}")

                if available < aus_node.cutoff:
                    print("  ⚠️  INFEASIBLE: not enough subjects!")
        else:
            print("\n⚠️  AUS node NOT FOUND in pruned tree!")

    print("=== END VALIDATION DEBUG ===\n")

    # Initialize vars that may be set inside conditional block
    aux_vars: dict[str, cp_model.IntVar] = {}
    aus_vars: dict[str, cp_model.IntVar] = {}

    if validation.pruned_tree is not None:
        # Before constraint building, check AUS one more time
        aus_node_before = find_requirement(validation.pruned_tree, 'AUS')
        if aus_node_before:
            print(f"\n🔍 Before constraint building: AUS.was_pruned={aus_node_before.was_pruned}")
            if isinstance(aus_node_before, SubjectThresholdGroup):
                print("  AUS structure:")
                print(f"    connection_type: {aus_node_before.connection_type}")
                print(f"    cutoff: {aus_node_before.cutoff}")
                print(f"    Total children: {len(aus_node_before.children)}")

                # Check for groups among children
                groups_count = sum(1 for item in aus_node_before.children if isinstance(item, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)))
                courses_count = sum(1 for item in aus_node_before.children if isinstance(item, Course))
                print(f"    Groups: {groups_count}, Courses: {courses_count}")

                # Find any groups (like 'all1')
                print("\n  AUS child groups:")
                for i, child in enumerate(aus_node_before.children):
                    if isinstance(child, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
                        child_pruned = hasattr(child, 'was_pruned') and child.was_pruned
                        child_title = getattr(child, 'title', 'no title')
                        child_reqid = getattr(child, 'req_id', 'no req_id')
                        print(f"    Group at index {i}:")
                        print(f"      title: {child_title}, req_id: {child_reqid}")
                        print(f"      type: {type(child).__name__}")
                        print(f"      was_pruned: {child_pruned}")
                        print(f"      children: {len(child.children)}")

                        # Show first few courses in this group
                        for j in range(min(3, len(child.children))):
                            gc = child.children[j]
                            if isinstance(gc, Course):
                                gc_pruned = hasattr(gc, 'was_pruned') and gc.was_pruned
                                print(f"        Course {j}: {gc.subject_id}, was_pruned={gc_pruned}")

        req_key = 'major6-3new'
        aux_vars_result, debug_names, mapping = add_requirement_constraints(
            model, take_vars, validation.pruned_tree,
            courses_df, req_key, enforce=True
        )
        aux_vars.update(aux_vars_result)
        print(f"\nCreated {len(aux_vars)} auxiliary variables")

        # Print ALL aux var keys to see what's there
        print("\nAll aux var keys:")
        for i, path in enumerate(sorted(aux_vars.keys())):
            print(f"  {i}: {path}")
            if i >= 20:
                print(f"  ... and {len(aux_vars) - 20} more")
                break

        # Find AUS aux var
        print("\nAux vars containing 'aus' (case-insensitive):")
        for path, var in aux_vars.items():
            if 'aus' in str(path).lower():
                print(f"  {path}")
                if path == 'major6-3new/aus':
                    aus_vars[path] = var

    # Minimal objective
    model.Minimize(sum(take_vars.values()))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    print("\nSolving...")
    status = solver.Solve(model)

    print(f"\nSolver status: {status}")
    if status == cp_model.OPTIMAL:
        print("Status: OPTIMAL")
    elif status == cp_model.FEASIBLE:
        print("Status: FEASIBLE")
    elif status == cp_model.INFEASIBLE:
        print("Status: INFEASIBLE")
    else:
        print(f"Status: {status}")

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        # Check which courses are taken
        from shared.optimizer.semesters import VALID_SEMESTERS
        c01_taken = any(solver.Value(take_vars[(c01_idx, s)]) == 1 for s in VALID_SEMESTERS if (c01_idx, s) in take_vars)
        c011_taken = any(solver.Value(take_vars[(c011_idx, s)]) == 1 for s in VALID_SEMESTERS if (c011_idx, s) in take_vars)
        c404_taken = any(solver.Value(take_vars[(c404_idx, s)]) == 1 for s in VALID_SEMESTERS if (c404_idx, s) in take_vars)

        print(f"\n6.C01 taken: {c01_taken}")
        print(f"6.C011 taken: {c011_taken}")
        print(f"18.404 taken: {c404_taken}")

        # Check AUS aux var value specifically
        print("\n🔍 Checking AUS requirement satisfaction:")
        if 'major6-3new/aus' in aus_vars:
            aus_var = aus_vars['major6-3new/aus']
            aus_value = solver.Value(aus_var)
            print(f"  major6-3new/aus value: {aus_value}")
            if aus_value == 1:
                print("    ✓ SATISFIED")
            else:
                print("    ✗ NOT SATISFIED")
        else:
            print("  ⚠️  AUS aux var not found!")

        # Check all AUS-related aux var values
        print("\nAll AUS-related aux var values:")
        for path, var in aux_vars.items():
            if 'aus' in str(path).lower():
                val = solver.Value(var)
                status_symbol = "✓" if val == 1 else "✗"
                print(f"  {status_symbol} {path}: {val}")

        # This is the bug - solver says feasible but AUS should not be satisfied
        print("\n⚠️  BUG: Solver reports FEASIBLE but AUS should only be 1/2 satisfied!")
        print("   6.C01/6.C011 group requires BOTH courses (connection='all')")
        print("   Only 6.C01 is taken, so the group should be 0")
    else:
        print("\n✓ Correctly reported as INFEASIBLE")


if __name__ == '__main__':
    test_aus_bug_with_exact_solution()
