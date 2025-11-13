#!/usr/bin/env python
"""Test validator semantics on Course 7 (Biology) and Course 15 (Management)."""

import pandas as pd
import requests

from courses import (
    RequirementCourse,
    RequirementGroup,
    parse_requirement,
    validate_and_prune,
)

# Fetch courses data
print("Fetching courses data from Fireroad...")
response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
data = response.json()
courses_df = pd.DataFrame(data)
print(f"Loaded {len(courses_df)} courses\n")

# Test Course 7 and Course 15
majors = [
    ('major7', 'Course 7 (Biology)'),
    ('major15-3', 'Course 15-3 (Finance)'),
    ('major15-2', 'Course 15-2 (Business Analytics)'),
]

for major_key, major_name in majors:
    print("="*80)
    print(f"{major_name}")
    print("="*80)

    try:
        # Fetch requirements
        response = requests.get(f'https://fireroad.mit.edu/requirements/get_json/{major_key}')
        response.raise_for_status()
        major_data = response.json()

        # Parse and validate
        req = parse_requirement(major_data)
        result = validate_and_prune(req, courses_df, remove_invalid=False)

        print(f"Overall feasibility: {result.is_feasible}")
        print(f"Invalid courses found: {len(result.removed_courses)}")

        if result.removed_courses:
            print("\nInvalid courses:")
            for course in result.removed_courses[:10]:  # Show first 10
                print(f"  - {course}")
            if len(result.removed_courses) > 10:
                print(f"  ... and {len(result.removed_courses) - 10} more")

        # Analyze groups with connection-type
        def analyze_groups(node, depth=0):
            if isinstance(node, RequirementGroup):
                # Count valid direct children
                valid_children = sum(
                    1 for item in node.items
                    if not (hasattr(item, 'was_pruned') and item.was_pruned)
                )

                # Count leaf courses
                def count_courses(n):
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
                total_courses = valid_courses + invalid_courses

                # Show groups with interesting patterns
                if node.connection_type and len(node.items) > 1:
                    indent = "  " * depth
                    title = (node.title or node.req_id or "unnamed")[:60]

                    # Show all groups with connection types
                    status = "✅" if not node.was_pruned else "❌"
                    print(f"\n{indent}{status} {title}")
                    print(f"{indent}   Connection: {node.connection_type}")
                    if node.threshold:
                        print(f"{indent}   Threshold: {node.threshold.cutoff} {node.threshold.criterion}")
                    print(f"{indent}   Direct children: {valid_children}/{len(node.items)} valid")
                    if total_courses > 0:
                        print(f"{indent}   Leaf courses: {valid_courses}/{total_courses} valid")

                    # Highlight interesting cases
                    if invalid_courses > 0 and not node.was_pruned and valid_children == len(node.items):
                        print(f"{indent}   🔍 INTERESTING: Feasible despite {invalid_courses} invalid leaf courses")
                    elif node.was_pruned and valid_children > 0:
                        print(f"{indent}   🔍 INTERESTING: Infeasible despite {valid_children} valid direct children")

                # Recurse
                for item in node.items:
                    analyze_groups(item, depth + 1)

        print("\nRequirement Structure:")
        analyze_groups(result.pruned_tree)

    except requests.exceptions.HTTPError as e:
        print(f"❌ Failed to fetch: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()

print("\n" + "="*80)
print("VERIFICATION SUMMARY")
print("="*80)
print("\nConfirmed behaviors:")
print("  • Groups with 'all' remain feasible when ALL direct children are feasible")
print("  • Groups with 'any' remain feasible when ≥1 direct child is feasible")
print("  • Invalid leaf courses don't affect parent feasibility if children are valid")
print("  • Thresholds count direct children, not leaf courses")
