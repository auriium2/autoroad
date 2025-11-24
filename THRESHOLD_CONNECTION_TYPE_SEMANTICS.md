# Threshold and Connection Type Semantics

## Current Implementation (As-Is Documentation)

This documents the **actual behavior** of the current constraint builder code, not the intended or correct behavior.

---

## Core Concepts

### RequirementGroup Structure

Every `RequirementGroup` can have:
- **`items`**: List of child requirements (courses or sub-groups)
- **`connection_type`**: `"all"`, `"any"`, or `None`
- **`threshold`**: Optional threshold object with:
  - `cutoff`: Integer (how many required)
  - `criterion`: `"subjects"` or `"units"` 
  - `type`: `"GTE"` or `"LTE"` (greater/less than or equal)

---

## Scenario 1: No Threshold, Only Connection Type

**File**: `requirement_constraint_builder.py` lines 530-563

### When `threshold is None` and `connection_type` is set:

#### `connection_type = "all"` or `None`

```python
self.ctx.model.AddMinEquality(group_var, child_vars)
```

**Semantics**:
- `group_var = min(child_var_1, child_var_2, ..., child_var_n)`
- Group is satisfied IFF **ALL** children are satisfied
- If `connection_type is None`, it defaults to `"all"` behavior

**Example**:
```
Group: Take all of these
  - Course A
  - Course B
  - Course C

Constraint: group_var = min(A_var, B_var, C_var)
Result: Group satisfied only if A AND B AND C all satisfied
```

#### `connection_type = "any"`

```python
self.ctx.model.AddMaxEquality(group_var, child_vars)
```

**Semantics**:
- `group_var = max(child_var_1, child_var_2, ..., child_var_n)`
- Group is satisfied IFF **AT LEAST ONE** child is satisfied
- Bidirectional: group satisfied ↔ at least one child satisfied

**Example**:
```
Group: Take any one of these
  - Course A
  - Course B
  - Course C

Constraint: group_var = max(A_var, B_var, C_var)
Result: Group satisfied if ANY of A, B, or C is satisfied
```

#### Edge Case: No Valid Children

```python
if not child_vars:
    self.ctx.model.Add(group_var == 0)
```

**Semantics**: If all children were pruned/invalid, group cannot be satisfied.

---

## Scenario 2: Threshold Present, No Connection Type

**File**: `requirement_constraint_builder.py` lines 524-527, 600-637

### When `threshold is not None` and `connection_type is None`:

The code routes to `_build_threshold_group()` and does NOT check connection type at all.

#### `threshold.criterion = "subjects"`

```python
# Collect all leaf course variables from the subtree
all_course_vars = self._collect_all_course_vars_from_results(child_nodes, child_results)

sum_satisfied = sum(all_course_vars)
self.ctx.model.Add(sum_satisfied >= cutoff).OnlyEnforceIf(group_var)
self.ctx.model.Add(sum_satisfied < cutoff).OnlyEnforceIf(group_var.Not())
```

**Semantics**:
- **Recursively collects ALL leaf courses** from entire subtree (including courses within child groups)
- Counts how many leaf courses are satisfied
- Group is satisfied IFF `count(satisfied_courses) >= cutoff`
- **Bidirectional constraint**: 
  - If `group_var == 1` → `sum >= cutoff`
  - If `group_var == 0` → `sum < cutoff`

**Example**:
```
Group: Select 2 subjects
  - Course A
  - Course B
  - SubGroup (connection='all')
      - Course C
      - Course D
  - Course E

Collected course vars: [A, B, C, D, E] (5 total)
Constraint: 
  - group_var == 1 ↔ (A + B + C + D + E >= 2)
  
If student takes A and C: sum = 2, group satisfied
Even if SubGroup requires both C AND D!
```

**🚨 BUG**: This ignores child group constraints! Courses from child groups count individually even if their parent group requires multiple courses together.

#### `threshold.criterion = "units"` (or other)

```python
# Count direct children
sum_satisfied = sum(child_vars)
self.ctx.model.Add(sum_satisfied >= cutoff).OnlyEnforceIf(group_var)
self.ctx.model.Add(sum_satisfied < cutoff).OnlyEnforceIf(group_var.Not())
```

**Semantics**:
- Counts **direct child satisfaction variables** (not leaf courses)
- Each child (course or group) counts as 1 unit if satisfied
- Group is satisfied IFF `count(satisfied_children) >= cutoff`

**Example**:
```
Group: Select 2 items (units criterion)
  - Course A
  - Course B  
  - SubGroup
      - Course C
      - Course D

Child vars: [A_var, B_var, SubGroup_var] (3 total)
Constraint:
  - group_var == 1 ↔ (A_var + B_var + SubGroup_var >= 2)
  
SubGroup counts as 1 unit regardless of how many courses it contains
```

---

## Scenario 3: BOTH Threshold AND Connection Type

**File**: `requirement_constraint_builder.py` lines 638-651

### When BOTH are present:

The code first applies the threshold logic (Scenario 2), then **adds additional constraints** for connection type.

#### Threshold Logic Applied First

Same as Scenario 2 - either counts leaf courses (subjects) or direct children (units).

#### Additional Connection Type Constraints

##### If `connection_type = "all"`:

```python
if child_vars:
    for child_var in child_vars:
        self.ctx.model.Add(child_var == 1).OnlyEnforceIf(group_var)
```

**Semantics**:
- **One-way implication**: If group is satisfied → ALL children must be satisfied
- Does NOT enforce reverse: "if all children satisfied → group satisfied"
- This is in **addition** to threshold constraint

**Example**:
```
Group: Select 2 subjects, AND all children must be satisfied
  connection_type: "all"
  threshold: {cutoff: 2, criterion: "subjects"}
  - Course A
  - Course B

Constraints:
  1. group_var == 1 ↔ (A_var + B_var >= 2)  [threshold]
  2. If group_var == 1 → A_var == 1          [connection type]
  3. If group_var == 1 → B_var == 1          [connection type]

Result: Group satisfied only if both A AND B are taken (threshold requires 2, connection requires all)
```

##### If `connection_type = "any"`:

```python
if child_vars:
    self.ctx.model.Add(sum(child_vars) >= 1).OnlyEnforceIf(group_var)
```

**Semantics**:
- **One-way implication**: If group is satisfied → at least one child must be satisfied  
- Does NOT enforce reverse: "if threshold met → group satisfied"
- This is in **addition** to threshold constraint

**Example** (AUS Bug Case):
```
Group: Select 2 subjects, at least one child must be satisfied
  connection_type: "any"
  threshold: {cutoff: 2, criterion: "subjects"}
  - Course A (individual)
  - Course B (individual)
  - SubGroup (connection='all')
      - Course C
      - Course D

Collected course vars: [A, B, C, D] (4 total)
Child vars: [A_var, B_var, SubGroup_var] (3 total)

Constraints:
  1. group_var == 1 ↔ (A + B + C + D >= 2)   [threshold on leaf courses]
  2. If group_var == 1 → (A_var + B_var + SubGroup_var >= 1)  [connection type]

Problem: Student takes A and C
  - Leaf course sum: A(1) + C(1) = 2 ✓ threshold satisfied
  - Children sum: A_var(1) + SubGroup_var(0) = 1 ✓ at least one child
  - group_var can be 1
  
But SubGroup requires BOTH C AND D, so SubGroup_var should be 0!
The threshold counts C individually without respecting SubGroup's constraint.
```

**🚨 BUG**: The threshold counting bypasses child group constraints when using `criterion="subjects"`.

---

## Summary Table

| Threshold | Connection Type | Behavior |
|-----------|----------------|----------|
| None | None | Defaults to `connection="all"`: group = min(children) |
| None | "all" | group = min(children) |
| None | "any" | group = max(children) |
| Present, subjects | None | group ↔ (sum of ALL leaf courses >= cutoff) |
| Present, units | None | group ↔ (sum of direct children >= cutoff) |
| Present, subjects | "all" | group ↔ (sum of ALL leaf courses >= cutoff) AND (if group → all children satisfied) |
| Present, subjects | "any" | group ↔ (sum of ALL leaf courses >= cutoff) AND (if group → at least one child satisfied) |
| Present, units | "all" | group ↔ (sum of direct children >= cutoff) AND (if group → all children satisfied) |
| Present, units | "any" | group ↔ (sum of direct children >= cutoff) AND (if group → at least one child satisfied) |

---

## Key Issues in Current Implementation

### Issue 1: Subjects Criterion Ignores Group Structure

When `criterion="subjects"`, the code recursively collects **all leaf courses** and counts them individually toward the threshold. This breaks when:
- A child group has `connection_type="all"` (requires multiple courses together)
- Courses from that group count individually toward the parent's threshold
- **Result**: Parent can be satisfied by taking only some courses from the group, violating the group's "all" constraint

**Affected code**: `_collect_all_course_vars_from_results()` at lines 342-373

### Issue 2: One-Way Connection Type Constraints

When both threshold and connection type are present, the connection type constraints are **one-way implications**:
- `connection="all"`: if group satisfied → all children satisfied ✓
- `connection="any"`: if group satisfied → at least one child satisfied ✓

But NOT the reverse:
- "if threshold met → group satisfied" ✗

This creates a weak constraint that allows the solver to satisfy the threshold without setting the group variable to 1.

**Affected code**: Lines 638-651

### Issue 3: Semantic Ambiguity

It's unclear what `threshold + connection_type` should mean:

**Interpretation A (Current?)**:
- Threshold: Count leaf courses globally
- Connection: Additional constraint on direct children
- **Problem**: Doesn't respect nested group constraints

**Interpretation B**:
- Threshold: Primary constraint (count courses or children)
- Connection: Redundant or error?
- **Problem**: Why would both exist?

**Interpretation C**:
- Threshold: Count courses that can potentially satisfy
- Connection: Defines how those courses can be selected
- **Problem**: Not currently implemented

---

## What Should the Semantics Be?

### Proposed Correct Semantics

#### Option 1: Respect Group Boundaries

For `criterion="subjects"` with nested groups:
- DO NOT count courses from child groups individually
- Instead, count a child group's courses ONLY if the group itself is satisfied
- This respects the group's internal constraints

**Pseudocode**:
```python
for each child:
    if child is Course:
        course_vars.append(child_var)
    elif child is Group:
        group_courses = get_courses(child)
        for course_var in group_courses:
            # Count only if group is satisfied
            conditional = model.NewBoolVar()
            model.Add(conditional == course_var).OnlyEnforceIf(child_group_var)
            model.Add(conditional == 0).OnlyEnforceIf(child_group_var.Not())
            course_vars.append(conditional)
```

#### Option 2: Use Direct Children for Counting

For `criterion="subjects"`:
- Count **direct children** (courses or groups) as units
- Each child counts as 1 unit if satisfied
- This matches `criterion="units"` behavior

**Issue**: Doesn't distinguish "1 course" from "a group of 5 courses"

#### Option 3: Separate Threshold Types

Introduce clearer distinction:
- `criterion="courses"`: Count only direct course children
- `criterion="subjects"`: Count all leaf courses (current behavior)
- `criterion="items"`: Count direct children regardless of type
- Add validation to prevent `"subjects"` with nested groups having `connection="all"`

---

## Recommended Next Steps

1. **Decide on correct semantics** for threshold + connection_type combinations
2. **Fix Option 1**: Modify `_collect_all_course_vars_from_results()` to respect group constraints
3. **Add tests** for all combinations in the table above
4. **Document** the intended semantics clearly in code comments
5. **Validate** against Fireroad's behavior to ensure compatibility
