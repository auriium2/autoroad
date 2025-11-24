# AUS Requirement Bug Investigation

## Summary

The backend optimizer reports a solution as FEASIBLE/OPTIMAL, but the Fireroad frontend reports the same schedule as having the AUS requirement only 1/2 satisfied. Investigation reveals a critical bug in how threshold-based requirements with mixed children (courses + groups) are handled.

---

## Bug Reproduction

### Test File
`backend/tests/test_aus_bug_exact_replication.py`

### Scenario
- Class of 2028 (planning_year_start = 2024)
- Freeze past semesters mode enabled
- Major: 6-3new (Course 6-3)
- All 35 courses from actual backend solution pinned to exact semesters

### Key Courses
- **6.C01**: Taken in Junior Spring (semester 9, section 8)
- **6.C011**: NOT taken
- **18.404**: Taken in Senior Fall (semester 10, section 9)

### Expected Behavior
Solution should be INFEASIBLE because:
- AUS has a child group at index 48 called `all1`
- This group has `connection_type='all'` with 2 children: 6.C01 and 6.C011
- Taking only 6.C01 without 6.C011 should NOT satisfy this group
- Therefore AUS should not be fully satisfied

### Actual Behavior
- Solver reports: **OPTIMAL** (status 4)
- AUS auxiliary variable value: **1** (SATISFIED)
- Child group `all1` variable value: **0** (NOT SATISFIED)
- **BUG**: Parent is satisfied even though a child group is not satisfied

---

## Root Cause Analysis

### AUS Requirement Structure

```
AUS (major6-3new/aus)
├── connection_type: "any"
├── threshold: cutoff=2, criterion='subjects', type='GTE'
├── Total children: 53
│   ├── 52 individual courses (RequirementCourse)
│   └── 1 group at index 48 (RequirementGroup)
│       └── all1 (major6-3new/aus/all1)
│           ├── connection_type: "all"
│           ├── threshold: None
│           └── Children: 2
│               ├── 6.C01 (was_pruned=False)
│               └── 6.C011 (was_pruned=False)
```

### Constraint Building Behavior

From `backend/optimizer/requirement_constraint_builder.py`:

#### For threshold with `criterion='subjects'` (lines 600-620):

```python
# Collect all leaf course variables from the subtree
all_course_vars = self._collect_all_course_vars_from_results(child_nodes, child_results)

# Count how many courses are satisfied
sum_satisfied = sum(all_course_vars)
self.ctx.model.Add(sum_satisfied >= cutoff).OnlyEnforceIf(group_var)
self.ctx.model.Add(sum_satisfied < cutoff).OnlyEnforceIf(group_var.Not())
```

**Problem**: This collects ALL leaf courses from the subtree, including 6.C01 and 6.C011 from within the `all1` group. It then counts them individually toward the threshold.

**Result**: 
- If 6.C01 is taken (1) + 18.404 is taken (1) = 2 courses
- Threshold requires 2 courses → **SATISFIED**
- But this **ignores** the constraint that 6.C01 and 6.C011 must **BOTH** be taken as a group!

#### For `connection_type='any'` with threshold (lines 647-651):

```python
elif node.connection_type == "any":
    # If group_var is 1, then at least one child must be 1
    self.ctx.model.Add(sum(child_vars) >= 1).OnlyEnforceIf(group_var)
```

**Problem**: This is a **one-way implication**:
- If AUS is satisfied → at least one child must be satisfied ✓
- But NOT: If threshold is met → AUS must be satisfied

This allows the solver to satisfy the threshold without satisfying AUS, breaking the bidirectional relationship.

---

## Semantic Confusion: Thresholds vs Connection Types

### Current Understanding (Needs Verification)

There are **two separate constraint mechanisms** that can both be present:

1. **`threshold`**: A counting-based constraint
   - `criterion='subjects'`: Count **leaf courses** in subtree
   - `criterion='units'`: Count **direct children** (or units?)
   - `cutoff=N`: Require at least N items

2. **`connection_type`**: A logical constraint on children
   - `'all'`: ALL direct children must be satisfied
   - `'any'`: At least ONE direct child must be satisfied
   - `None`: Container group, no specific constraint

### The Problem

When **BOTH** are present (like in AUS):
- `threshold: {cutoff=2, criterion='subjects'}` 
- `connection_type: 'any'`

**What should this mean?**

#### Interpretation A (Current Implementation?)
- Threshold: Count all leaf courses, need ≥2
- Connection: At least one direct child must be satisfied
- **Issue**: Courses within child groups are counted individually, bypassing group constraints

#### Interpretation B (Fireroad's Behavior?)
- Threshold: Count **satisfied children** (treating groups as single units), need ≥2
- Connection: At least one direct child must be satisfied
- **Issue**: Unclear how to "count" a group that's partially satisfied

#### Interpretation C (What validator might expect?)
- Threshold applies to leaf courses globally
- Connection type still must be respected for child groups
- **Issue**: Need to enforce group satisfaction constraints separately

### Key Questions

1. **When counting for a threshold with `criterion='subjects'`, should we:**
   - Count all leaf courses regardless of group structure? (Current)
   - Count only leaf courses from satisfied groups?
   - Count satisfied direct children (courses=1, groups=count their courses)?

2. **When a group has BOTH threshold AND connection_type:**
   - Are they both required constraints? (validator suggests yes)
   - Which takes precedence if they conflict?
   - How do they interact?

3. **For groups with `connection_type='all'` nested under threshold groups:**
   - Should the group's courses count individually toward parent threshold?
   - Or should the group be treated as a single atomic unit?

---

## Validator vs Constraint Builder

### Validator Logic (`backend/courses/requirements/validator.py`)

Lines 125-145 show validator checks **BOTH** threshold AND connection_type:

```python
# Check threshold requirement (if present)
if req.threshold:
    # ... check if threshold can be satisfied ...

# Check connection_type requirement (if present and not already infeasible)
if not is_group_infeasible and req.connection_type == "all":
    # ... check if all children are valid ...
```

**Key insight**: Validator treats them as **independent constraints** that BOTH must be satisfied.

### Constraint Builder Logic

Lines 638-651 attempt to enforce both:

```python
# Also enforce connection_type if present (both threshold AND connection_type must be satisfied)
if node.connection_type == "all":
    if child_vars:
        for child_var in child_vars:
            self.ctx.model.Add(child_var == 1).OnlyEnforceIf(group_var)
elif node.connection_type == "any":
    if child_vars:
        self.ctx.model.Add(sum(child_vars) >= 1).OnlyEnforceIf(group_var)
```

**Issue**: The `connection_type='any'` constraint is one-directional and weak when combined with threshold counting.

---

## Specific Bug in AUS Case

### What's Happening

1. AUS has 53 children: 52 courses + 1 group (`all1` with 6.C01 and 6.C011)
2. Threshold counting collects **54 course variables** from subtree:
   - 52 direct course children
   - 2 courses from within `all1` group
3. Solver satisfies threshold by taking:
   - 6.C01 (from within `all1`) = 1
   - 18.404 (direct child) = 1
   - Total = 2 ≥ 2 threshold ✓
4. The `all1` group variable is **0** because 6.C011 is not taken
5. But the `connection_type='any'` constraint is satisfied because:
   - 18.404 is satisfied (a direct child)
   - So at least one child is satisfied ✓
6. **Result**: AUS variable = 1, even though `all1` group = 0

### Why This Is Wrong

The `all1` group has `connection_type='all'`, meaning 6.C01 and 6.C011 must **BOTH** be taken. But the threshold counting treats them as independent courses, allowing 6.C01 to count toward the threshold without 6.C011.

**The child group's internal constraints are being bypassed.**

---

## Aux Vars Observed

From test output:

```
✓ major6-3new/aus: 1
✗ major6-3new/aus/all1: 0
✓ 18.404 (individual course): 1
✓ 6.C01 (individual course): 1
✗ 6.C011 (individual course): 0
```

The parent `aus` is satisfied despite child `all1` being unsatisfied.

---

## Potential Fixes

### Option 1: Don't Count Courses from Child Groups Individually

When collecting course vars for threshold counting, don't descend into child **groups**. Instead:
- Count direct course children individually
- For group children, require the group to be satisfied first, then count its courses

**Pseudocode**:
```python
if threshold.criterion == 'subjects':
    for each child:
        if child is RequirementCourse:
            course_vars.append(child_var)
        elif child is RequirementGroup:
            # Count courses in group, but ONLY if group is satisfied
            group_courses = collect_courses(child)
            for course_var in group_courses:
                # course_var counts only if group_var is satisfied
                conditional_var = model.NewBoolVar()
                model.Add(conditional_var == 1).OnlyEnforceIf([group_var, course_var])
                model.Add(conditional_var == 0).OnlyEnforceIf(group_var.Not())
                course_vars.append(conditional_var)
```

### Option 2: Use Group Vars, Not Course Vars

For threshold counting, use child satisfaction variables (which might be courses OR groups):
- Treat each direct child as 1 unit toward threshold
- Groups contribute 1 if satisfied, 0 if not
- Don't look inside groups

**Issue**: Doesn't match `criterion='subjects'` semantic (counting courses, not children)

### Option 3: Fix Connection Type Constraint

Make the `connection_type` enforcement bidirectional:

```python
if node.connection_type == "any":
    # Bidirectional: group is satisfied IFF (threshold met AND at least one child satisfied)
    model.AddMaxEquality(group_var, child_vars)  # group = max(children)
    # But also enforce threshold
    model.Add(sum_satisfied >= cutoff).OnlyEnforceIf(group_var)
```

**Issue**: Still doesn't address the core problem of counting courses within groups

### Option 4: Validator-Style Counting

Match exactly what the validator does in `count_valid_courses()`:
- For threshold with `criterion='subjects'`, recursively count ALL valid courses
- But separately enforce that child groups must satisfy their own connection_type constraints
- This requires the group auxiliary vars to properly reflect their constraints

**This might be what's intended, but needs group constraints to be sound**

---

## Next Steps

1. **Clarify the semantics**: What should threshold + connection_type mean?
   - Review Fireroad frontend code for their interpretation
   - Check requirement JSON structure for examples
   - Define precise semantics for each combination

2. **Identify the fix**: Once semantics are clear, determine which fix is correct
   - Option 1: Conditional counting of group courses
   - Option 3: Stronger connection type constraints  
   - Option 4: Ensure group vars correctly enforce all constraints

3. **Test thoroughly**: 
   - AUS case (threshold + any + nested all group)
   - Other combinations (threshold + all, no threshold + all, etc.)
   - Edge cases (all groups, all courses, mixed)

4. **Document the semantics**: Add clear documentation to the constraint builder explaining how thresholds and connection types interact

---

## Files Involved

- `backend/optimizer/requirement_constraint_builder.py` - Constraint building logic
- `backend/courses/requirements/validator.py` - Validation and pruning
- `backend/courses/requirements/types.py` - Data structures
- `backend/tests/test_aus_bug_exact_replication.py` - Bug reproduction test
