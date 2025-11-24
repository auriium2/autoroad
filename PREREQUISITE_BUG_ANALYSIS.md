# Critical Bug: Prerequisite Constraints Not Enforced

## Bug Report

**Symptom:** Solver places courses that violate prerequisite requirements.

**Example:**
- Course: 2.005 (Thermal-Fluids Engineering I)
- Placed in: Senior Fall (semester 7)
- Prerequisites: `(2.001, 2.003, (2.005/2.051), (2.00B/2.670/2.678))/"permission of instructor"`
- Requirements: 6-3 major + minor in Course 2
- **Problem:** None of the prerequisites (2.001, 2.003, etc.) are in the schedule!

## Root Cause Hypotheses

### Hypothesis 1: Prerequisite Parser Error
The prerequisite string might be misparsed:
```
Prereq: (2.001, 2.003, (2.005/2.051), (2.00B/2.670/2.678))/'permission of instructor'
```

This has:
- AND group: 2.001, 2.003, (2.005 OR 2.051), (2.00B OR 2.670 OR 2.678)
- PLUS a "permission of instructor" text clause

**Possible issues:**
- Parser might ignore the entire prereq due to "permission of instructor" text
- Parser might interpret the structure incorrectly
- The `(2.005/2.051)` creates a circular dependency (2.005 requires itself?)

### Hypothesis 2: Constraint Not Added to Model
The constraint might be parsed correctly but never added to CP-SAT model:
- `add_prerequisite_constraints()` might skip certain courses
- Constraint creation might fail silently
- The `override_course_ids` filter might be too broad

### Hypothesis 3: Weak Constraint Instead of Hard Constraint
Prerequisite satisfaction might be a soft constraint that can be violated:
- If implemented as penalty in objective instead of hard constraint
- CP-SAT would minimize violations but allow them if needed

### Hypothesis 4: Constraint Logic Error
The boolean logic for "course taken before semester S" might be wrong:
- Off-by-one error in semester indexing
- Earlier semesters list might be empty
- AddMaxEquality might not enforce what we think it does

## Debugging Steps

1. **Check if constraint is added:**
   ```python
   # In add_prerequisite_constraints, add logging:
   print(f"[DEBUG] Building prereq constraint for {course_id} in semester {semester}")
   print(f"[DEBUG] Prereq tree: {prereq_tree}")
   print(f"[DEBUG] Satisfaction var: {prereq_satisfied_var}")
   print(f"[DEBUG] Constraint: {prereq_satisfied_var} >= {take_var}")
   ```

2. **Check prerequisite parsing:**
   ```python
   # For course 2.005, print parsed tree
   prereq_str = courses_df[course_2_005_idx, 'prerequisites']
   parsed = parse_fireroad(prereq_str)
   print(f"[DEBUG] 2.005 prereq string: {prereq_str}")
   print(f"[DEBUG] 2.005 parsed tree: {parsed}")
   ```

3. **Verify constraint in model:**
   ```python
   # After building all constraints, check model
   print(f"[DEBUG] Total constraints in model: {len(model.Proto().constraints)}")
   ```

4. **Check if course is in override list:**
   ```python
   if course_id in override_course_ids:
       print(f"[DEBUG] {course_id} is OVERRIDDEN - skipping prereqs!")
   ```

## Unit Test to Reproduce

```python
def test_prerequisite_enforcement_2_005():
    """
    Verify that 2.005 cannot be placed without its prerequisites.
    
    Prerequisites for 2.005:
    - 2.001 (Mechanics and Materials I)
    - 2.003 (Dynamics and Control I)
    - 2.005 OR 2.051
    - 2.00B OR 2.670 OR 2.678
    """
    # Create minimal test case
    courses_df = load_courses_including_2_005()
    
    model = cp_model.CpModel()
    take_vars = create_take_vars(model, courses_df, 2024, 12, markers=None)
    
    # Parse prerequisites for 2.005
    prereq_trees = parse_prerequisites_for_all_courses(courses_df)
    course_2_005_idx = get_course_index("2.005")
    
    assert course_2_005_idx in prereq_trees, "2.005 should have prerequisites"
    
    # Add prerequisite constraints
    add_prerequisite_constraints(model, take_vars, courses_df, 2024, prereq_trees, set())
    
    # Try to place 2.005 in semester 7 without any prerequisites
    model.Add(take_vars[course_2_005_idx, 7] == 1)
    
    # Ensure NO prerequisites are taken
    for prereq_course_id in ["2.001", "2.003", "2.051", "2.00B", "2.670", "2.678"]:
        prereq_idx = get_course_index(prereq_course_id)
        if prereq_idx is not None:
            for s in range(1, 7):  # Before semester 7
                if (prereq_idx, s) in take_vars:
                    model.Add(take_vars[prereq_idx, s] == 0)
    
    # Solve
    solver = cp_model.CpSolver()
    result = solver.Solve(model)
    
    # Should be INFEASIBLE because prerequisites aren't satisfied
    assert result == cp_model.INFEASIBLE, \
        f"Expected INFEASIBLE but got {result}. Prerequisites not enforced!"
```

## Next Steps

1. Run the unit test to confirm the bug
2. Add debug logging to prerequisite constraint building
3. Check if 2.005's prerequisites are parsed correctly
4. Verify the constraint is actually added to the model
5. Check for any "permission of instructor" text handling that might skip the constraint
