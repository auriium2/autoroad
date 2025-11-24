# Fireroad API Semantics - Empirical Findings

## Summary

Through empirical testing of the Fireroad API, we've discovered the **actual semantics** of threshold and connection-type combinations. The key insight: **Fireroad does NOT count individual courses from unsatisfied groups toward threshold progress.**

---

## Key Findings

### Finding 1: Courses in Unsatisfied Groups Don't Count

**Test**: 6.C01 + 18.404 (missing 6.C011)
- AUS has `threshold: 2 subjects, connection: any`
- AUS contains a nested group with `connection: all` containing [6.C01, 6.C011]
- We take 6.C01 (from group) + 18.404 (direct child)

**Expected (our buggy behavior)**: 2 courses → threshold satisfied
**Actual Fireroad behavior**: 
- AUS: **NOT SATISFIED** (progress=1/2)
- Nested group: NOT SATISFIED (progress=1/2)
- **Only 18.404 counts toward AUS**
- 6.C01 does NOT count because its parent group is unsatisfied

### Finding 2: Satisfied Groups Count as Children, Not as Sum of Courses

**Test**: 6.C01 + 6.C011 (group complete, nothing else)
- Both courses in the nested group taken
- Nested group becomes SATISFIED

**Result**:
- AUS: **NOT SATISFIED** (progress=1/2)
- Nested group: SATISFIED (progress=2/2)
- **The satisfied group counts as 1 child toward the parent threshold**
- Not as 2 courses!

### Finding 3: Satisfied Group + One Other Course = Threshold Met

**Test**: 6.C01 + 6.C011 + 18.404
- Nested group: SATISFIED (both courses taken)
- One direct course: 18.404

**Result**:
- AUS: **SATISFIED** (progress=2/2)
- **1 satisfied group + 1 course = 2 children toward threshold**

### Finding 4: Only Direct Children Count (Not All Courses)

**Test**: Two courses (6.3900 + 18.404)
- AUS: NOT SATISFIED (progress=1/2)
- **Discovery**: 6.3900 is NOT in the AUS requirement at all!
- Only 18.404 counts because it's the only AUS course taken

**Test**: Three courses (6.3900 + 18.404 + 6.3100)
- AUS: SATISFIED (progress=2/2)
- Both 18.404 and 6.3100 are direct children of AUS
- 6.3900 doesn't count (not in AUS)

**Interpretation**: Fireroad counts satisfied **direct children** only. Courses not in the requirement don't contribute.

---

## Semantic Rules (Derived)

### Rule 1: Threshold Counting with `criterion='subjects'`

When a requirement has `threshold: {criterion: 'subjects', cutoff: N}`:

1. **For direct course children**: Each satisfied course counts as 1 toward threshold
2. **For group children with `connection='all'`**: 
   - If the group is NOT satisfied → courses within the group contribute 0
   - If the group IS satisfied → the group itself counts as 1 (not the sum of its courses)
3. **For group children with `connection='any'`**: (needs more testing)

### Rule 2: Connection Type + Threshold Interaction

When a requirement has BOTH `threshold` AND `connection_type`:
- Both constraints must be satisfied
- `connection_type='any'`: At least one direct child must be satisfied (in addition to threshold)
- `connection_type='all'`: All direct children must be satisfied (in addition to threshold)

### Rule 3: Group Boundaries Matter

Courses within a group are NOT counted individually for parent threshold calculations unless the group itself is satisfied.

---

## Bug in Our Implementation

### Current (Wrong) Behavior

From `backend/optimizer/requirement_constraint_builder.py` lines 600-620:

```python
# For threshold with criterion='subjects'
all_course_vars = self._collect_all_course_vars_from_results(child_nodes, child_results)
sum_satisfied = sum(all_course_vars)
self.ctx.model.Add(sum_satisfied >= cutoff).OnlyEnforceIf(group_var)
```

**Problem**: We collect ALL leaf course variables from the entire subtree, ignoring group boundaries. This allows courses from unsatisfied groups to count toward the parent threshold.

### Correct Behavior

For threshold with `criterion='subjects'`, we should:

1. **Count satisfied direct course children**: 1 each
2. **Count satisfied direct group children**: 1 each (not their course count)
3. **Do NOT count courses from within child groups directly**

**Pseudocode**:
```python
if threshold.criterion == 'subjects':
    counting_vars = []
    for child, child_result in zip(child_nodes, child_results):
        if isinstance(child, RequirementCourse):
            # Direct course: counts as 1 if taken
            counting_vars.append(child_result.satisfies_var)
        elif isinstance(child, RequirementGroup):
            # Group: counts as 1 if the group is satisfied
            counting_vars.append(child_result.satisfies_var)
    
    sum_satisfied = sum(counting_vars)
    model.Add(sum_satisfied >= cutoff).OnlyEnforceIf(group_var)
```

---

## Questions Remaining

1. ~~**Why does "Two non-group AUS" show progress=1/2 instead of 2/2?**~~ **RESOLVED**
   - 6.3900 is not in the AUS requirement at all
   - Only courses that are actual children of the requirement count

2. ~~**What about `criterion='units'`?**~~ **RESOLVED - EMPIRICALLY TESTED**
   - **Units counts ALL LEAF COURSES regardless of group boundaries**
   - This is OPPOSITE behavior from subjects!
   - Uses actual catalog unit values (not API payload values)
   - The current implementation of collecting all leaf courses is CORRECT for units
   - Only `criterion='subjects'` needs to be fixed to count children instead

3. **What about nested groups with `connection='any'`?**
   - How do partially satisfied "any" groups count?
   - Do they count as satisfied once threshold is met?
   - Need more empirical tests on requirements with nested "any" groups

---

## Next Steps

1. ✅ **Discovered the semantics** through empirical API testing
   - Threshold with `criterion='subjects'` counts satisfied direct children (not leaf courses)
   - Courses in unsatisfied groups don't count
   - Groups count as 1 child when satisfied

2. **Fix the constraint builder** to use child satisfaction variables instead of leaf course variables
   - For threshold counting with `criterion='subjects'`: count satisfied children
   - For threshold counting with `criterion='units'`: sum units from satisfied children
   - Don't descend into child groups to collect leaf courses

3. **Test the fix** against the AUS bug scenario to ensure:
   - 6.C01 + 18.404 → INFEASIBLE (our solver should reject this)
   - 6.C01 + 6.C011 + 18.404 → FEASIBLE (our solver should accept this)

4. **Add comprehensive tests** to ensure all threshold + connection-type combinations work correctly

---

## Summary for Implementation

### The Fix (Pseudocode)

```python
def build_threshold_constraint(group_var, child_results, threshold):
    if threshold.criterion == 'subjects':
        # Count satisfied direct children (each counts as 1)
        counting_vars = [child.satisfies_var for child in child_results]
        count = sum(counting_vars)
        model.Add(count >= threshold.cutoff).OnlyEnforceIf(group_var)
        model.Add(count < threshold.cutoff).OnlyEnforceIf(group_var.Not())
    
    elif threshold.criterion == 'units':
        # Sum units from satisfied direct children
        unit_contributions = []
        for child in child_results:
            # child.satisfies_var * child.units (or sum of child's courses' units if group)
            unit_contribution = model.NewIntVar(0, max_units, f'unit_contrib_{child.id}')
            model.Add(unit_contribution == child.total_units).OnlyEnforceIf(child.satisfies_var)
            model.Add(unit_contribution == 0).OnlyEnforceIf(child.satisfies_var.Not())
            unit_contributions.append(unit_contribution)
        
        total_units = sum(unit_contributions)
        model.Add(total_units >= threshold.cutoff).OnlyEnforceIf(group_var)
        model.Add(total_units < threshold.cutoff).OnlyEnforceIf(group_var.Not())
```

### Key Principle

**Group boundaries matter.** When counting for thresholds, only satisfied children contribute. This ensures that group constraints (like `connection='all'`) are respected before their courses can count toward parent thresholds.
