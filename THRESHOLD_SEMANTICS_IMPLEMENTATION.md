# Threshold Semantics Implementation - Final Documentation

## Overview

This document explains how we fixed the AUS bug by implementing Fireroad's exact threshold semantics in our constraint-based optimizer. The fix was developed through:
1. Empirical API testing to discover the behavior
2. Analysis of Fireroad's source code to confirm the exact logic
3. Translation of runtime logic to constraint-based formulation

---

## The Problem: AUS Bug

### Original Bug
The optimizer reported a schedule as FEASIBLE, but Fireroad showed the AUS requirement as only 1/2 satisfied.

**Test case**: `tests/test_aus_bug_exact_replication.py`
- Schedule includes: 6.C01 (in Junior Spring), 18.404 (in Senior Fall)
- Schedule does NOT include: 6.C011
- AUS requirement structure:
  - Threshold: `{cutoff: 2, criterion: 'subjects'}`
  - 52 direct course children (including 18.404)
  - 1 group child called `all1` with `connection_type='all'` containing [6.C01, 6.C011]

**Why it was wrong:**
- The old code collected ALL leaf courses from the subtree (54 total courses)
- If any 2 courses were taken, the threshold was met
- This ignored the constraint that the `all1` group requires BOTH 6.C01 AND 6.C011

**Expected behavior:**
- 18.404 taken → contributes 1
- `all1` group NOT satisfied (missing 6.C011) → contributes 0
- Total: 1 < 2 → AUS should be NOT satisfied

---

## Fireroad's Three Rules

From `fireroad-server/requirements/progress.py:809-816`:

```python
if req_progress.statement.connection_type == CONNECTION_TYPE_ALL and req_progress.children:
    # ALL group with children contributes 1 when fulfilled
    num_courses_satisfied += req_progress.is_fulfilled and len(req_progress.satisfied_courses) > 0
else:
    # Everything else contributes count of satisfied courses
    num_courses_satisfied += len(req_satisfied_courses)
```

**Translation to contribution rules:**

When a parent requirement has a threshold with `criterion='subjects'`, each child contributes:

1. **Direct course child (taken)** → contributes **1**
2. **Group child with `connection_type='all'` and children** → contributes **1** when satisfied
3. **Other groups** → contributes **len(satisfied_courses)**:
   - Groups WITH threshold: when satisfied, they have exactly `threshold.cutoff` courses
   - Groups WITHOUT threshold: they have however many courses you actually take from them

---

## Implementation Details

### File Changed
`backend/optimizer/requirement_constraint_builder.py:598-651`

### Key Code Structure

```python
if threshold.criterion == "subjects":
    contribution_vars = []
    
    for idx, (child_node, child_result) in enumerate(zip(child_nodes, child_results)):
        if child_result.satisfied_var is None:
            continue  # Skip invalid children
            
        if isinstance(child_node, RequirementCourse):
            # RULE 1: Direct course contributes 1
            contribution_var = NewIntVar(0, 1)
            model.Add(contribution_var == 1).OnlyEnforceIf(child_result.satisfied_var)
            model.Add(contribution_var == 0).OnlyEnforceIf(child_result.satisfied_var.Not())
            contribution_vars.append(contribution_var)
            
        elif isinstance(child_node, RequirementGroup):
            if child_node.connection_type == "all" and len(child_node.items) > 0:
                # RULE 2: ALL group contributes 1 when satisfied
                contribution_var = NewIntVar(0, 1)
                model.Add(contribution_var == 1).OnlyEnforceIf(child_result.satisfied_var)
                model.Add(contribution_var == 0).OnlyEnforceIf(child_result.satisfied_var.Not())
                contribution_vars.append(contribution_var)
            else:
                # RULE 3: Other groups contribute len(satisfied_courses)
                if child_node.threshold and child_node.threshold.criterion == "subjects":
                    # Group WITH threshold: contributes threshold.cutoff when satisfied
                    contribution = child_node.threshold.cutoff
                    contribution_var = NewIntVar(0, contribution)
                    model.Add(contribution_var == contribution).OnlyEnforceIf(child_result.satisfied_var)
                    model.Add(contribution_var == 0).OnlyEnforceIf(child_result.satisfied_var.Not())
                    contribution_vars.append(contribution_var)
                else:
                    # Group WITHOUT threshold: contribute actual courses taken
                    child_course_vars = _collect_all_course_vars_from_results([child_node], [child_result])
                    contribution_vars.extend(child_course_vars)
    
    # Sum all contributions and enforce threshold
    total_contribution = sum(contribution_vars)
    model.Add(total_contribution >= cutoff).OnlyEnforceIf(group_var)
    model.Add(total_contribution < cutoff).OnlyEnforceIf(group_var.Not())
```

### Why This Works

**Runtime vs Constraint-Based Logic:**

Fireroad's runtime approach:
- After courses are selected, count how many each child contributed
- ALL groups that are satisfied contribute 1
- Other children contribute their actual satisfied course count

Our constraint approach:
- Before courses are selected, define contribution variables
- For ALL groups: IntVar that equals 1 if satisfied, 0 otherwise
- For groups with thresholds: IntVar that equals threshold.cutoff if satisfied, 0 otherwise
- For groups without thresholds: directly use the course variables from that group

The key insight: **groups without thresholds need to contribute dynamically** based on how many courses you actually take from them. We handle this by collecting all course variables from that group and adding them directly to the contribution list.

---

## Edge Cases Handled

### Case 1: AUS with ALL Group
**Structure:**
- Parent: AUS with threshold={cutoff: 2, criterion: 'subjects'}
- Children:
  - 52 direct courses (including 18.404)
  - 1 ALL group with [6.C01, 6.C011]

**Contribution:**
- Each direct course: 1 when taken
- ALL group: 1 when BOTH courses taken, 0 otherwise
- If only 6.C01 + 18.404 taken: 1 + 0 = 1 < 2 → NOT satisfied ✓

### Case 2: Subjects from Two Tracks
**Structure:**
- Parent: threshold={cutoff: 2, criterion: 'subjects'}
- Children:
  - Track 1: threshold={cutoff: 2, criterion: 'subjects'}
  - Track 2: threshold={cutoff: 2, criterion: 'subjects'}

**Contribution:**
- Each track contributes 2 when satisfied (their threshold cutoff)
- If both tracks satisfied: 2 + 2 = 4 ≥ 2 → satisfied ✓
- Parent shows progress=4 (matches Fireroad API)

### Case 3: Course 18 Communication-Intensive
**Structure:**
- Parent: connection_type='all', threshold={cutoff: 2, criterion: 'subjects'}
- Children:
  - Option A: connection_type='any', NO threshold, 11 courses
  - Option B: connection_type='any', threshold={cutoff: 0}, 7 courses

**Contribution:**
- Option A: NOT 'all' type, NO threshold → contributes actual courses taken
- Option B: NOT 'all' type, HAS threshold of 0 → contributes 0 when satisfied
- If 2 courses from Option A taken: 2 + 0 = 2 ≥ 2 → satisfied ✓

**Why the old code passed this incorrectly:**
- Old code collected all 18 courses from both groups
- Taking any 2 of those 18 satisfied the threshold
- This ignored the parent's `connection_type='all'` requiring both Option A AND Option B to be satisfied

**Why the new code is correct:**
- We check group satisfaction separately
- Option A contributes based on courses actually taken from it
- Parent's `connection_type='all'` is enforced separately (lines 859-870)
- Both constraints must be met

---

## Testing

### Tests Passing (26 total)
1. `test_aus_bug_exact_replication.py::test_aus_bug_with_exact_solution` ✓
2. All 10 full optimizer e2e tests ✓
3. All 15 optimizer integration tests ✓

### Critical Tests
- **AUS bug**: Correctly reports infeasible when group constraints not met
- **Course 6-3**: Subjects from Two Tracks counts progress correctly
- **Course 18**: Complex nested groups with mixed thresholds work correctly

---

## Key Learnings

### 1. Runtime vs Constraint Logic
Translating runtime logic to constraints requires thinking about:
- What variables exist before solving?
- How do we express "count of satisfied courses" as a constraint?
- How do we handle dynamic contributions?

### 2. The Critical Insight: Groups Without Thresholds
Groups without thresholds were the hardest case because:
- In runtime: count the actual courses in `satisfied_courses` list
- In constraints: we don't have a "list" - we need to sum course variables

Solution: Don't create a single contribution variable for these groups. Instead, collect all course variables from the group and add them directly to the contribution list.

### 3. Connection Type vs Threshold
These are **two separate constraints** that both must be satisfied:
- `threshold`: counting constraint (need N subjects/units)
- `connection_type`: logical constraint (all children vs any child)

A group can have both! Example: Course 18 Communication-Intensive has `connection_type='all'` AND `threshold={cutoff: 2}`.

### 4. Fireroad's Parsing Affects Connection Type
From the source code analysis (`reqlist.py:651-655`):
- Requirements with thresholds often get `connection_type='any'` during parsing
- This affects which branch they fall into in the contribution logic
- Requirements like `"A,B,C{>=2}"` parse as `connection_type='any'` (not 'all')

---

## Implementation Checklist

For anyone implementing similar threshold semantics:

- [ ] Identify if parent has threshold with `criterion='subjects'`
- [ ] For each child, determine its type:
  - [ ] Direct course? → contribute 1
  - [ ] ALL group with children? → contribute 1 when satisfied
  - [ ] Group with threshold? → contribute threshold.cutoff when satisfied
  - [ ] Group without threshold? → contribute actual courses taken
- [ ] Sum all contributions
- [ ] Enforce threshold constraint bidirectionally:
  - [ ] If satisfied → total contribution >= cutoff
  - [ ] If not satisfied → total contribution < cutoff
- [ ] Separately enforce `connection_type` constraints (if present)

---

## References

- **Fireroad Source Code**: `/Users/matt/summer/autoroad/SUMMARY.md`
  - Key file: `fireroad-server/requirements/progress.py:809-816`
  - Data structures: `fireroad-server/requirements/reqlist.py`
- **Bug Investigation**: `/Users/matt/summer/autoroad/AUS_BUG_INVESTIGATION.md`
- **Empirical Testing**: `/Users/matt/summer/autoroad/FIREROAD_THRESHOLD_SEMANTICS_FINAL.md`
- **Test File**: `backend/tests/test_aus_bug_exact_replication.py`
- **Implementation**: `backend/optimizer/requirement_constraint_builder.py:598-651`

---

## Conclusion

The fix successfully translates Fireroad's runtime threshold logic into a constraint-based formulation. The key insight was understanding that groups without thresholds need to contribute dynamically based on the actual courses taken from them, which we handle by directly using their course variables rather than creating a single contribution variable.

All tests pass, confirming that our implementation matches both the empirical API behavior and Fireroad's actual source code logic.
