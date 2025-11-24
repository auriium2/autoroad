# Fireroad Threshold Semantics - Complete Investigation Report

## Executive Summary

Through empirical testing of the Fireroad API, we discovered the **correct semantics** for how threshold constraints interact with nested groups. The key finding: **Fireroad counts satisfied direct children for thresholds, not leaf courses.**

---

## The Bug

### Original Problem
Our optimizer reported a Course 6-3 schedule as OPTIMAL/FEASIBLE, but Fireroad reported AUS requirement as only 1/2 satisfied.

### Root Cause
The constraint builder was collecting ALL leaf course variables from the entire subtree (including courses inside nested groups) and counting them toward the threshold. This allowed courses from unsatisfied groups to contribute to parent thresholds, violating group constraints.

```python
# WRONG (current implementation):
all_course_vars = self._collect_all_course_vars_from_results(child_nodes, child_results)
sum_satisfied = sum(all_course_vars)  # Counts 6.C01 even if its group is unsatisfied!
```

---

## Empirical Findings

### Test Setup
- Queried Fireroad API with various course combinations
- Tested major6-3new AUS requirement (threshold: 2 subjects, connection: any)
- AUS has 52 direct courses + 1 nested group (connection: all, containing 6.C01 and 6.C011)

### Key Results

| Test Case | Courses Taken | AUS Progress | AUS Fulfilled | Interpretation |
|-----------|---------------|--------------|---------------|----------------|
| Partial group | 6.C01 + 18.404 | 1/2 | ✗ | Only 18.404 counts (group unsatisfied) |
| Complete group only | 6.C01 + 6.C011 | 1/2 | ✗ | Group counts as 1 child |
| Group + one course | 6.C01 + 6.C011 + 18.404 | 2/2 | ✓ | Group (1) + course (1) = 2 |
| Two direct courses | 18.404 + 6.3100 | 2/2 | ✓ | Two satisfied children |
| Invalid course | 6.3900 + 18.404 | 1/2 | ✗ | 6.3900 not in AUS! |

### Critical Insight

**Courses inside unsatisfied groups contribute ZERO to parent thresholds.**

When we take 6.C01 + 18.404:
- 6.C01 is inside the nested group with connection='all'
- The group is NOT satisfied (missing 6.C011)
- Therefore: only 18.404 counts → progress = 1/2 → NOT SATISFIED ✓

---

## The Correct Semantics

### Rule 1: Threshold with `criterion='subjects'`

Count **satisfied direct children** (not leaf courses):
- Each satisfied direct **course** child = 1
- Each satisfied direct **group** child = 1
- Unsatisfied children = 0

### Rule 2: Threshold with `criterion='units'` (EMPIRICALLY VERIFIED)

Sum **units from ALL leaf courses** (ignores group boundaries):
- Counts actual catalog units from all taken courses that are children (at any depth)
- Does NOT respect group boundaries (unlike subjects)
- Uses real catalog unit values, not API payload values
- This is fundamentally different from subjects criterion!

### Rule 3: Group Boundaries - Different for Subjects vs Units

**For `criterion='subjects'`**: Group boundaries ARE enforced
- You cannot "reach into" an unsatisfied group and count its courses
- The group must be satisfied first before it contributes to parent thresholds

**For `criterion='units'`**: Group boundaries are IGNORED
- Units from all leaf courses count, regardless of group satisfaction status
- This means the current implementation might actually be correct for units!

---

## The Fix

### Current (Wrong) Implementation

```python
# backend/optimizer/requirement_constraint_builder.py, lines 600-620

if threshold.criterion == 'subjects':
    # WRONG: Collects ALL leaf courses, ignoring group boundaries
    all_course_vars = self._collect_all_course_vars_from_results(child_nodes, child_results)
    sum_satisfied = sum(all_course_vars)
    self.ctx.model.Add(sum_satisfied >= cutoff).OnlyEnforceIf(group_var)
```

**Problem**: This counts 6.C01 toward AUS threshold even when the nested group (requiring both 6.C01 and 6.C011) is unsatisfied.

### Correct Implementation

```python
if threshold.criterion == 'subjects':
    # Count satisfied DIRECT CHILDREN (not leaf courses)
    child_satisfaction_vars = [result.satisfies_var for result in child_results]
    count = sum(child_satisfaction_vars)
    self.ctx.model.Add(count >= cutoff).OnlyEnforceIf(group_var)
    self.ctx.model.Add(count < cutoff).OnlyEnforceIf(group_var.Not())

elif threshold.criterion == 'units':
    # Sum units from ALL LEAF COURSES (ignores group boundaries)
    # This is what the current implementation does - and it's CORRECT for units!
    all_course_vars = self._collect_all_course_vars_from_results(child_nodes, child_results)
    
    # For each course var, multiply by its actual unit value
    unit_contributions = []
    for course_var, course_node in zip(all_course_vars, all_course_nodes):
        units = course_node.units  # Get actual catalog units
        # Multiply: if course is taken (1) then contribute units, else contribute 0
        unit_var = model.NewIntVar(0, units, f'units_{course_node.id}')
        model.Add(unit_var == units).OnlyEnforceIf(course_var)
        model.Add(unit_var == 0).OnlyEnforceIf(course_var.Not())
        unit_contributions.append(unit_var)
    
    total_units = sum(unit_contributions)
    model.Add(total_units >= cutoff).OnlyEnforceIf(group_var)
    model.Add(total_units < cutoff).OnlyEnforceIf(group_var.Not())
```

---

## Testing Plan

### Unit Tests Required

1. **AUS bug scenario** (major6-3new):
   - ✗ 6.C01 + 18.404 → should be INFEASIBLE
   - ✓ 6.C01 + 6.C011 + 18.404 → should be FEASIBLE

2. **Threshold with all-connection group**:
   - Group requires all children, parent requires threshold
   - Partial group satisfaction should not count

3. **Threshold with any-connection group**:
   - Group requires any child, parent requires threshold
   - Partially satisfied group should still count as 1 if it meets its threshold

4. **Units criterion** (if applicable):
   - Test that units from unsatisfied groups don't count
   - Test that satisfied groups contribute their total units

5. **Multiple nested groups**:
   - Test with multiple groups at same level
   - Ensure each is evaluated independently

---

## Files to Modify

1. **`backend/optimizer/requirement_constraint_builder.py`**
   - Lines 600-620: Fix threshold with criterion='subjects'
   - Lines 575-595: Fix threshold with criterion='units' (if exists)
   - Remove or fix `_collect_all_course_vars_from_results()` method

2. **`backend/tests/test_aus_bug_exact_replication.py`**
   - Should pass after fix (currently fails)

3. **Add new test file**: `backend/tests/test_threshold_semantics.py`
   - Comprehensive tests for all threshold + connection-type combinations

---

## Validation

After implementing the fix, verify:

1. ✓ The AUS bug test passes (6.C01 + 18.404 is INFEASIBLE)
2. ✓ All existing optimizer tests still pass
3. ✓ The validator and constraint builder produce consistent results
4. ✓ Real-world course plans match Fireroad's evaluation

---

## Related Documents

- `AUS_BUG_INVESTIGATION.md` - Original bug analysis
- `FIREROAD_SEMANTICS_DISCOVERED.md` - Detailed empirical findings
- `backend/tests/test_fireroad_api_semantics.py` - API testing script
- `backend/tests/test_fireroad_semantics_empirical.py` - Additional empirical tests

---

## Key Takeaway

**"Threshold counting operates on satisfied direct children, not leaf courses. Group boundaries matter."**

This ensures that all group constraints (connection types, nested thresholds) are respected before courses can contribute to parent requirements.
