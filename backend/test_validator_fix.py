#!/usr/bin/env python
"""Test the validator fix to verify Electives is no longer incorrectly marked as pruned."""

import pandas as pd
import requests

from courses import RequirementGroup, parse_requirement, validate_and_prune

# Fetch courses data
print("Fetching courses data from Fireroad...")
response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
data = response.json()
courses_df = pd.DataFrame(data)
print(f"Loaded {len(courses_df)} courses")

# Fetch 6-3 requirements
print("\nFetching 6-3 major requirements...")
response = requests.get('https://fireroad.mit.edu/requirements/get_json/major6-3')
major_data = response.json()

# Parse requirements
print("Parsing requirements...")
req = parse_requirement(major_data)

# Validate with mark mode (don't remove)
print("Validating requirements...")
result = validate_and_prune(req, courses_df, remove_invalid=False)

print("\nValidation complete:")
print(f"  Removed courses: {len(result.removed_courses)}")
print(f"  Is feasible: {result.is_feasible}")
print(f"  Warnings: {len(result.warnings)}")

# Find Electives
def find_electives(node):
    if isinstance(node, RequirementGroup):
        if node.title and 'Elective' in node.title:
            return node
        for item in node.items:
            found = find_electives(item)
            if found:
                return found
    return None

electives = find_electives(result.pruned_tree)
if electives:
    # Count valid vs invalid children recursively
    def count_valid_invalid(node, valid=0, invalid=0):
        if isinstance(node, RequirementGroup):
            for item in node.items:
                valid, invalid = count_valid_invalid(item, valid, invalid)
        elif hasattr(node, 'was_pruned'):
            if node.was_pruned:
                invalid += 1
            else:
                valid += 1
        return valid, invalid

    valid_count, invalid_count = count_valid_invalid(electives)

    # Count valid direct children
    valid_direct_children = sum(
        1 for item in electives.items
        if not (hasattr(item, 'was_pruned') and item.was_pruned)
    )

    print("\n" + "="*80)
    print("ELECTIVES ANALYSIS")
    print("="*80)
    print(f"Title: {electives.title}")
    print(f"ID: {electives.req_id}")
    print(f"Connection type: {electives.connection_type}")
    print(f"Threshold: {electives.threshold}")
    print(f"\nDirect children: {len(electives.items)}")
    print(f"Valid direct children: {valid_direct_children}/{len(electives.items)}")
    print("\nAll leaf courses (recursive):")
    print(f"  Valid: {valid_count}")
    print(f"  Invalid: {invalid_count}")
    print(f"  Total: {valid_count + invalid_count}")
    print(f"\n⚠️  Was pruned (infeasible): {electives.was_pruned}")

    if electives.was_pruned:
        print("\n❌ PROBLEM: Electives marked as infeasible")
        print("This is incorrect - with 'all' connection type, only direct children matter,")
        print("and not all direct children are invalid.")
    else:
        print("\n✅ SUCCESS: Electives correctly marked as feasible")
        print("Even though some leaf courses are invalid, the direct children are valid,")
        print("so the 'all' connection type is satisfied.")
else:
    print("\n⚠️  Electives requirement not found")
