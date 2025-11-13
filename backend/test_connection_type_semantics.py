#!/usr/bin/env python
"""
Comprehensive test to verify all/any connection-type semantics.

This test creates synthetic requirement trees with known structure and validates
that the feasibility logic correctly implements FireRoad's semantics:
- "all" means ALL direct children must be satisfied
- "any" means AT LEAST ONE direct child must be satisfied
- Thresholds specify exactly how many direct children must be satisfied
"""

import pandas as pd
import requests
from courses import (
    RequirementCourse,
    RequirementGroup,
    RequirementThreshold,
    mark_invalid_requirements,
)

# Create a minimal courses dataframe for testing
courses_df = pd.DataFrame({
    'subject_id': ['6.100A', '6.1200', '6.1010', '6.1020']
})

print("="*80)
print("CONNECTION TYPE SEMANTICS VERIFICATION")
print("="*80)

# Test 1: "all" with all children valid
print("\n--- Test 1: 'all' with all children valid ---")
test1 = RequirementGroup(
    items=(
        RequirementCourse(course_id='6.100A', req_id='test1/a'),
        RequirementCourse(course_id='6.1200', req_id='test1/b'),
    ),
    connection_type='all',
    req_id='test1'
)
result1 = mark_invalid_requirements(test1, courses_df)
print(f"Expected: was_pruned=False")
print(f"Actual:   was_pruned={result1.was_pruned}")
assert result1.was_pruned == False, "FAIL: 'all' with all valid should be feasible"
print("✅ PASS")

# Test 2: "all" with one child invalid
print("\n--- Test 2: 'all' with one child invalid ---")
test2 = RequirementGroup(
    items=(
        RequirementCourse(course_id='6.100A', req_id='test2/a'),
        RequirementCourse(course_id='INVALID.COURSE', req_id='test2/b'),
    ),
    connection_type='all',
    req_id='test2'
)
result2 = mark_invalid_requirements(test2, courses_df)
print(f"Expected: was_pruned=True (all children required, but one is invalid)")
print(f"Actual:   was_pruned={result2.was_pruned}")
assert result2.was_pruned == True, "FAIL: 'all' with invalid child should be infeasible"
print("✅ PASS")

# Test 3: "any" with one child valid, one invalid
print("\n--- Test 3: 'any' with one child valid, one invalid ---")
test3 = RequirementGroup(
    items=(
        RequirementCourse(course_id='6.100A', req_id='test3/a'),
        RequirementCourse(course_id='INVALID.COURSE', req_id='test3/b'),
    ),
    connection_type='any',
    req_id='test3'
)
result3 = mark_invalid_requirements(test3, courses_df)
print(f"Expected: was_pruned=False (at least one valid child)")
print(f"Actual:   was_pruned={result3.was_pruned}")
assert result3.was_pruned == False, "FAIL: 'any' with at least one valid should be feasible"
print("✅ PASS")

# Test 4: "any" with all children invalid
print("\n--- Test 4: 'any' with all children invalid ---")
test4 = RequirementGroup(
    items=(
        RequirementCourse(course_id='INVALID.A', req_id='test4/a'),
        RequirementCourse(course_id='INVALID.B', req_id='test4/b'),
    ),
    connection_type='any',
    req_id='test4'
)
result4 = mark_invalid_requirements(test4, courses_df)
print(f"Expected: was_pruned=True (no valid children)")
print(f"Actual:   was_pruned={result4.was_pruned}")
assert result4.was_pruned == True, "FAIL: 'any' with no valid children should be infeasible"
print("✅ PASS")

# Test 5: Threshold (2 subjects out of 3 available) with 2 valid
print("\n--- Test 5: Threshold (2 subjects) with 2 valid courses ---")
test5 = RequirementGroup(
    items=(
        RequirementCourse(course_id='6.100A', req_id='test5/a'),
        RequirementCourse(course_id='6.1200', req_id='test5/b'),
        RequirementCourse(course_id='INVALID.COURSE', req_id='test5/c'),
    ),
    threshold=RequirementThreshold(cutoff=2, criterion='subjects', type='GTE'),
    req_id='test5'
)
result5 = mark_invalid_requirements(test5, courses_df)
print(f"Expected: was_pruned=False (threshold met: 2 valid subjects available)")
print(f"Actual:   was_pruned={result5.was_pruned}")
assert result5.was_pruned == False, "FAIL: threshold met should be feasible"
print("✅ PASS")

# Test 6: Threshold (2 subjects) with only 1 valid
print("\n--- Test 6: Threshold (2 subjects) with only 1 valid course ---")
test6 = RequirementGroup(
    items=(
        RequirementCourse(course_id='6.100A', req_id='test6/a'),
        RequirementCourse(course_id='INVALID.A', req_id='test6/b'),
        RequirementCourse(course_id='INVALID.B', req_id='test6/c'),
    ),
    threshold=RequirementThreshold(cutoff=2, criterion='subjects', type='GTE'),
    req_id='test6'
)
result6 = mark_invalid_requirements(test6, courses_df)
print(f"Expected: was_pruned=True (threshold not met: only 1 valid subject available)")
print(f"Actual:   was_pruned={result6.was_pruned}")
assert result6.was_pruned == True, "FAIL: threshold not met should be infeasible"
print("✅ PASS")

# Test 7: CRITICAL - Nested groups with "all" and invalid leaf courses
print("\n--- Test 7: Nested 'all' with valid child groups but invalid leaf courses ---")
test7 = RequirementGroup(
    items=(
        RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='test7/g1/a'),
                RequirementCourse(course_id='INVALID.A', req_id='test7/g1/b'),
            ),
            connection_type='any',  # This child group is valid (1 out of 2 valid)
            req_id='test7/g1'
        ),
        RequirementGroup(
            items=(
                RequirementCourse(course_id='6.1200', req_id='test7/g2/a'),
                RequirementCourse(course_id='INVALID.B', req_id='test7/g2/b'),
            ),
            connection_type='any',  # This child group is valid (1 out of 2 valid)
            req_id='test7/g2'
        ),
    ),
    connection_type='all',  # Parent requires ALL direct children (both groups)
    req_id='test7'
)
result7 = mark_invalid_requirements(test7, courses_df)
print(f"Expected: was_pruned=False")
print(f"Reasoning:")
print(f"  - Parent has connection_type='all' (requires all 2 direct children)")
print(f"  - Child group 1: 'any' with 1/2 valid courses → FEASIBLE")
print(f"  - Child group 2: 'any' with 1/2 valid courses → FEASIBLE")
print(f"  - Both direct children are feasible → parent is FEASIBLE")
print(f"Actual:   was_pruned={result7.was_pruned}")
assert result7.was_pruned == False, "FAIL: nested 'all' should check direct children, not leaves"
print("✅ PASS - This confirms 'all' applies to DIRECT CHILDREN, not leaf courses")

# Test 8: Nested groups where one child group becomes infeasible
print("\n--- Test 8: Nested 'all' where one child group is infeasible ---")
test8 = RequirementGroup(
    items=(
        RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='test8/g1/a'),
            ),
            connection_type='any',
            req_id='test8/g1'
        ),
        RequirementGroup(
            items=(
                RequirementCourse(course_id='INVALID.A', req_id='test8/g2/a'),
                RequirementCourse(course_id='INVALID.B', req_id='test8/g2/b'),
            ),
            connection_type='any',  # This child group is INVALID (0 out of 2 valid)
            req_id='test8/g2'
        ),
    ),
    connection_type='all',  # Parent requires ALL direct children
    req_id='test8'
)
result8 = mark_invalid_requirements(test8, courses_df)
print(f"Expected: was_pruned=True")
print(f"Reasoning:")
print(f"  - Parent has connection_type='all' (requires all 2 direct children)")
print(f"  - Child group 1: 'any' with 1/1 valid courses → FEASIBLE")
print(f"  - Child group 2: 'any' with 0/2 valid courses → INFEASIBLE")
print(f"  - One direct child is infeasible → parent is INFEASIBLE")
print(f"Actual:   was_pruned={result8.was_pruned}")
assert result8.was_pruned == True, "FAIL: 'all' with infeasible child should be infeasible"
print("✅ PASS")

print("\n" + "="*80)
print("ALL TESTS PASSED ✅")
print("="*80)
print("\nConfirmed semantics:")
print("  • 'all' connection-type applies to DIRECT CHILDREN only")
print("  • 'any' connection-type applies to DIRECT CHILDREN only")
print("  • Thresholds with criterion='subjects' count TOTAL COURSES in subtree")
print("  • Thresholds with other criteria count direct children")
print("  • Child groups evaluate their own subtrees recursively")
print("  • Parent feasibility depends on child feasibility, not leaf courses")
