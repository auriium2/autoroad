#!/usr/bin/env python
"""Debug the Course 15-3 threshold issue."""

import pandas as pd
import requests
from courses import (
    parse_requirement,
    validate_and_prune,
    mark_invalid_requirements,
    RequirementGroup,
)

# Fetch courses data
print("Fetching courses data from Fireroad...")
response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
data = response.json()
courses_df = pd.DataFrame(data)

# Fetch 15-3 requirements
response = requests.get('https://fireroad.mit.edu/requirements/get_json/major15-3')
major_data = response.json()

# Parse and validate
req = parse_requirement(major_data)
result = validate_and_prune(req, courses_df, remove_invalid=False)

# Find "Restricted Electives"
def find_node_by_title(node, title_substr):
    if isinstance(node, RequirementGroup):
        if node.title and title_substr in node.title:
            return node
        for item in node.items:
            found = find_node_by_title(item, title_substr)
            if found:
                return found
    return None

restricted = find_node_by_title(result.pruned_tree, "Restricted Electives")
if restricted:
    print("\n" + "="*80)
    print("RESTRICTED ELECTIVES ANALYSIS")
    print("="*80)
    print(f"Title: {restricted.title}")
    print(f"Connection type: {restricted.connection_type}")
    print(f"Threshold: {restricted.threshold}")
    print(f"Was pruned: {restricted.was_pruned}")
    print(f"\nDirect children ({len(restricted.items)}):")
    
    for i, child in enumerate(restricted.items, 1):
        if isinstance(child, RequirementGroup):
            print(f"\n  Child {i}: {child.title or child.req_id}")
            print(f"    Connection: {child.connection_type}")
            print(f"    Threshold: {child.threshold}")
            print(f"    Was pruned: {child.was_pruned}")
            print(f"    Num items: {len(child.items)}")
            
            # Check if this child is valid
            if child.was_pruned:
                print(f"    ⚠️  This child is INFEASIBLE")
                
                # Why is it infeasible?
                if child.threshold:
                    # Count valid children
                    valid_count = sum(
                        1 for item in child.items
                        if not (hasattr(item, 'was_pruned') and item.was_pruned)
                    )
                    print(f"    Threshold requires: {child.threshold.cutoff}")
                    print(f"    Valid children: {valid_count}/{len(child.items)}")
                    
                    if valid_count >= child.threshold.cutoff:
                        print(f"    🔍 BUG: Threshold IS met but marked infeasible!")
            else:
                print(f"    ✅ This child is feasible")
    
    # Summary
    print("\n" + "="*80)
    valid_direct = sum(
        1 for item in restricted.items
        if not (hasattr(item, 'was_pruned') and item.was_pruned)
    )
    print(f"Summary:")
    print(f"  Required threshold: {restricted.threshold.cutoff if restricted.threshold else 'N/A'}")
    print(f"  Valid direct children: {valid_direct}/{len(restricted.items)}")
    print(f"  Should be feasible: {valid_direct >= (restricted.threshold.cutoff if restricted.threshold else len(restricted.items))}")
    print(f"  Actually marked: {'infeasible' if restricted.was_pruned else 'feasible'}")
    
    if restricted.was_pruned and valid_direct >= (restricted.threshold.cutoff if restricted.threshold else len(restricted.items)):
        print("\n  ❌ BUG DETECTED: Group marked infeasible despite meeting threshold!")
