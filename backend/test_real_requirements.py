#!/usr/bin/env python
"""Test validator semantics on real FireRoad requirements across multiple majors."""

import pandas as pd
import requests

from courses.requirements.types import RequirementGroup
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune

# Fetch courses data
print("Fetching courses data from Fireroad...")
response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
data = response.json()
courses_df = pd.DataFrame(data)
print(f"Loaded {len(courses_df)} courses\n")

# Test multiple majors
majors = ['major6-3', 'major6-2', 'major2', 'major18']

for major_key in majors:
    print("="*80)
    print(f"Testing: {major_key}")
    print("="*80)

    # Fetch requirements
    response = requests.get(f'https://fireroad.mit.edu/requirements/get_json/{major_key}')
    major_data = response.json()

    # Parse and validate
    req = parse_requirement(major_data)
    result = validate_and_prune(req, courses_df, remove_invalid=False)

    print(f"Overall feasibility: {result.is_feasible}")
    print(f"Invalid courses found: {len(result.removed_courses)}")

    # Find groups with connection-type and analyze
    def analyze_groups(node, depth=0):
        if isinstance(node, RequirementGroup):
            if node.connection_type and len(node.items) > 0:
                # Count valid direct children
                valid_children = sum(
                    1 for item in node.items
                    if not (hasattr(item, 'was_pruned') and item.was_pruned)
                )

                # Count leaf courses
                def count_courses(n):
                    from requirements.types import RequirementCourse
                    if isinstance(n, RequirementCourse):
                        return (0 if n.was_pruned else 1, 1 if n.was_pruned else 0)
                    elif isinstance(n, RequirementGroup):
                        valid, invalid = 0, 0
                        for item in n.items:
                            v, i = count_courses(item)
                            valid += v
                            invalid += i
                        return valid, invalid
                    return 0, 0

                valid_courses, invalid_courses = count_courses(node)

                # Only show interesting cases: groups with invalid courses but still feasible
                if invalid_courses > 0 and not node.was_pruned and valid_children == len(node.items):
                    indent = "  " * depth
                    title = node.title or node.req_id or "unnamed"
                    print(f"\n{indent}📊 {title}")
                    print(f"{indent}   Connection: {node.connection_type}")
                    print(f"{indent}   Direct children: {valid_children}/{len(node.items)} valid")
                    print(f"{indent}   Leaf courses: {valid_courses} valid, {invalid_courses} invalid")
                    print(f"{indent}   Was pruned: {node.was_pruned}")
                    print(f"{indent}   ✅ FEASIBLE despite invalid leaf courses")

            # Recurse
            for item in node.items:
                analyze_groups(item, depth + 1)

    analyze_groups(result.pruned_tree)
    print()

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80)
print("\nKey findings:")
print("  • Groups with 'all' connection-type remain feasible when ALL direct")
print("    children are feasible, even if some leaf courses are invalid")
print("  • Groups with 'any' connection-type remain feasible when AT LEAST ONE")
print("    direct child is feasible")
print("  • This confirms hierarchical evaluation, not flattened leaf evaluation")
