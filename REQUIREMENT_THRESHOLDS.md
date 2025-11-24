# Requirement Thresholds and Connection Types

This document explains how requirement groups work in the Autoroad optimizer, specifically the relationship between `connection-type` and `threshold` in the Fireroad requirement format.

## Overview

Requirements in Fireroad are represented as trees where:
- **Leaf nodes** represent individual courses (e.g., "6.100A", "GIR:CAL1")
- **Group nodes** represent collections of requirements with rules about how many must be satisfied

Group nodes use two complementary fields to specify their satisfaction rules:
1. **`connection-type`**: A high-level semantic hint ('all' or 'any')
2. **`threshold`**: Precise numerical constraints for satisfaction

## Connection Type

The `connection-type` field provides a simple, human-readable hint about the group's intent:

### `"all"` - Require Every Item
All children must be satisfied.

```json
{
  "connection-type": "all",
  "threshold-desc": "select all",
  "reqs": [
    {"req": "6.100A"},
    {"req": "6.1200"},
    {"req": "6.3900"}
  ],
  "title": "Required Core Courses"
}
```

**Meaning**: Students must take 6.100A AND 6.1200 AND 6.3900.

### `"any"` - Require At Least One
At least one child must be satisfied (but possibly more).

```json
{
  "connection-type": "any",
  "threshold-desc": "select any",
  "reqs": [
    {"req": "1.073"},
    {"req": "1.074"}
  ],
  "title": "Choose One Lab"
}
```

**Meaning**: Students must take 1.073 OR 1.074 (or both).

### No Connection Type
When `connection-type` is absent, the default behavior is equivalent to `"all"`.

## Threshold

The `threshold` field provides precise numerical constraints. It's an object with three fields:

```json
{
  "cutoff": 2,
  "criterion": "subjects",
  "type": "GTE"
}
```

### Threshold Fields

#### `cutoff` (number)
The numeric threshold value. What this represents depends on the `criterion` field.

#### `criterion` (string)
What we're counting:
- **`"subjects"`**: Count the number of satisfied sub-requirements
- **`"units"`**: Count the total units from satisfied courses

#### `type` (string)
The comparison operator:
- **`"EQ"`**: Must equal exactly (=)
- **`"GTE"`**: Must be greater than or equal (≥)
- **`"LTE"`**: Must be less than or equal (≤)

### Threshold Examples

#### Example 1: Pick Exactly 2 Courses
```json
{
  "connection-type": "any",
  "threshold": {
    "cutoff": 2,
    "criterion": "subjects",
    "type": "EQ"
  },
  "reqs": [
    {"req": "6.4100"},
    {"req": "6.4200"},
    {"req": "6.4300"},
    {"req": "6.4400"}
  ],
  "title": "Pick Two Advanced Subjects"
}
```

**Meaning**: Choose exactly 2 courses from the 4 options.

#### Example 2: At Least 48 Units
```json
{
  "plain-string": true,
  "req": "48-60 units",
  "threshold": {
    "cutoff": 48,
    "criterion": "units",
    "type": "GTE"
  },
  "title": "Elective Subjects"
}
```

**Meaning**: Take elective courses totaling at least 48 units.

#### Example 3: At Most 1 Course
```json
{
  "threshold": {
    "cutoff": 1,
    "criterion": "subjects",
    "type": "LTE"
  },
  "reqs": [
    {"req": "15.301"},
    {"req": "15.302"}
  ],
  "title": "Managerial Finance"
}
```

**Meaning**: Take at most 1 course from these options (0 or 1 is allowed).

## Relationship Between Connection Type and Threshold

### When Both Are Present
If a requirement has both `connection-type` and `threshold`, the **threshold takes precedence** as it's more specific.

```json
{
  "connection-type": "any",
  "threshold": {
    "cutoff": 2,
    "criterion": "subjects",
    "type": "GTE"
  },
  "reqs": [/* 4 courses */]
}
```

Here, `connection-type: "any"` suggests "at least one," but the explicit threshold overrides this to require "at least two."

### When Only Connection Type Is Present
Our parser **automatically infers** a threshold from the connection-type:

#### `connection-type: "all"` → Require ALL items
```python
threshold = RequirementThreshold(
    cutoff=len(items),    # Number of items
    criterion='subjects',
    type='EQ'             # Must equal exactly
)
```

#### `connection-type: "any"` → Require AT LEAST ONE item
```python
threshold = RequirementThreshold(
    cutoff=1,
    criterion='subjects',
    type='GTE'            # Greater than or equal
)
```

#### No connection-type → Default to "all" behavior
```python
threshold = RequirementThreshold(
    cutoff=len(items),
    criterion='subjects',
    type='EQ'
)
```

### Why Automatic Inference Is Critical

**Bug History**: In an earlier version of the parser, groups without explicit thresholds would have `threshold=None`. This caused the optimizer to generate malformed constraints, making degrees like Course 1 (Civil Engineering) and Course 7 (Biology) appear INFEASIBLE even though they were perfectly valid.

The fix (added 2025-01-23) ensures that **every group node always has a valid threshold**, either from:
1. An explicit `threshold` field in the JSON, OR
2. Automatic inference from `connection-type`, OR
3. A sensible default (require all items)

## How The Optimizer Uses Thresholds

The constraint builder (backend/optimizer/requirement_constraint_builder.py) translates thresholds into CP-SAT constraints:

### Subject-Based Thresholds
For `criterion: "subjects"`, the optimizer:
1. **Recursively traverses the entire subtree** to collect ALL leaf course variables (not just direct children)
2. Sums these course satisfaction variables
3. Applies the threshold constraint

**Important**: Subject thresholds count ALL descendant courses in the subtree, not just immediate children.

```python
# Example: threshold = {cutoff: 2, criterion: "subjects", type: "GTE"}

# Group structure:
#   Group A (threshold: 2 subjects)
#     ├─ Course 1
#     ├─ Group B
#     │   ├─ Course 2
#     │   └─ Course 3
#     └─ Course 4

# The optimizer collects: [course1_var, course2_var, course3_var, course4_var]
# ALL 4 courses from the subtree, including nested ones

total_satisfied = sum(all_descendant_course_vars)

if threshold.type == "GTE":
    model.Add(total_satisfied >= threshold.cutoff)
elif threshold.type == "EQ":
    model.Add(total_satisfied == threshold.cutoff)
elif threshold.type == "LTE":
    model.Add(total_satisfied <= threshold.cutoff)
```

### Unit-Based Thresholds
For `criterion: "units"`, the optimizer **should** (when implemented):
1. **Recursively traverse the entire subtree** to collect all descendant courses
2. Multiply each course's units by its "taken" variable
3. Sum and apply the constraint

**Current Status**: As of 2025-01-23, unit-based thresholds are **not fully implemented** in the constraint builder. The code falls back to subject counting with a warning. See `requirement_constraint_builder.py:560-565`.

```python
# Example (planned implementation): threshold = {cutoff: 48, criterion: "units", type: "GTE"}

# For each course in the subtree:
# course_units = [12, 12, 9, 15, ...]  # units for each descendant course
# take_vars = [take1, take2, ...]      # boolean: is each course taken?

total_units = sum(units * take_var for units, take_var in zip(course_units, take_vars))
model.Add(total_units >= 48)
```

### Key Difference: Direct Children vs. All Descendants

**Common Misconception**: Thresholds only count immediate children.

**Reality**: Both subject and unit thresholds **recursively count ALL descendant courses** in the subtree.

#### Example: Nested Groups

```json
{
  "threshold": {
    "cutoff": 3,
    "criterion": "subjects",
    "type": "GTE"
  },
  "reqs": [
    {"req": "6.100A"},
    {
      "connection-type": "any",
      "reqs": [
        {"req": "6.4100"},
        {"req": "6.4200"},
        {"req": "6.4300"}
      ],
      "title": "Advanced Track"
    }
  ],
  "title": "Core and Electives"
}
```

**Counting behavior**: The threshold counts **4 courses total**:
- 6.100A (direct child)
- 6.4100 (grandchild via "Advanced Track")
- 6.4200 (grandchild via "Advanced Track")
- 6.4300 (grandchild via "Advanced Track")

So "at least 3 subjects" means picking at least 3 from these 4 options, not "at least 3 from the 2 direct children."

### Why Recursive Counting?

This matches the validation logic in `courses/requirements/validator.py`, which also recursively counts all descendants. The constraint builder must match the validator's behavior to ensure:
1. Requirements validated as feasible actually ARE feasible in the optimizer
2. The optimizer can satisfy requirements the same way the validator checks them

## Common Patterns

### Pattern 1: Required Core (All Courses)
```json
{
  "connection-type": "all",
  "threshold-desc": "select all",
  "reqs": [/* courses */],
  "title": "Core Requirements"
}
```
**Inferred threshold**: `{cutoff: N, criterion: "subjects", type: "EQ"}` where N = number of courses

### Pattern 2: Pick One (OR Group)
```json
{
  "connection-type": "any",
  "threshold-desc": "select either",
  "reqs": [/* 2 courses */],
  "title": "Lab Requirement"
}
```
**Inferred threshold**: `{cutoff: 1, criterion: "subjects", type: "GTE"}`

### Pattern 3: Pick N From M
```json
{
  "connection-type": "any",
  "threshold": {
    "cutoff": 2,
    "criterion": "subjects",
    "type": "GTE"
  },
  "reqs": [/* M courses */],
  "title": "Advanced Electives"
}
```
**Explicit threshold**: Pick at least 2 from M options

### Pattern 4: Unit Requirements
```json
{
  "plain-string": true,
  "req": "Description text",
  "threshold": {
    "cutoff": 48,
    "criterion": "units",
    "type": "GTE"
  },
  "title": "Unrestricted Electives"
}
```
**Unit-based constraint**: Total units must be ≥ 48

### Pattern 5: Nested Groups (Root Wrapper)
```json
{
  "reqs": [
    {
      "connection-type": "all",
      "reqs": [/* core courses */],
      "title": "Core"
    },
    {
      "connection-type": "any",
      "threshold": {"cutoff": 2, "criterion": "subjects", "type": "GTE"},
      "reqs": [/* electives */],
      "title": "Electives"
    }
  ],
  "title": "Major Requirements"
}
```
**Root has no connection-type**: Automatically gets `{cutoff: 2, criterion: "subjects", type: "EQ"}` (must satisfy both children: Core AND Electives)

## Testing

We have comprehensive tests to ensure threshold handling is correct:

### Unit Tests (test_requirements_parser.py::TestThresholdInference)
- Verifies `connection-type: "all"` infers correct threshold
- Verifies `connection-type: "any"` infers correct threshold
- Verifies no connection-type defaults to "all" behavior
- Verifies explicit thresholds override inference
- Verifies nested groups all get thresholds

### Fuzzer Tests (test_fuzzers.py::TestRequirementParserFuzzer)
- Fetches ALL requirements from Fireroad
- Verifies parser handles them without exceptions
- **Critical**: Verifies every group node has a valid threshold
- Ensures 95%+ parsing success rate

### E2E Integration Tests (test_full_optimizer_e2e.py)
- Tests complete optimizer flow for real degrees
- Includes Course 1 and Course 7 (the degrees that exposed the original bug)
- Verifies degrees are FEASIBLE and produce valid schedules

## Debugging Tips

### Symptom: Degree shows as INFEASIBLE but should be possible
**Check**: Do all requirement groups have valid thresholds?

```python
from courses.requirements.parser import parse_requirement
from courses.requirements.types import RequirementGroup

def check_thresholds(node, path="root"):
    if isinstance(node, RequirementGroup):
        if node.threshold is None:
            print(f"❌ Missing threshold at {path}")
        else:
            print(f"✓ {path}: threshold={node.threshold.cutoff}/{len(node.items)}")
        
        for i, child in enumerate(node.items):
            check_thresholds(child, f"{path}.{i}")

req_tree = parse_requirement({'reqs': requirement_data['reqs'], 'title': 'major1'})
check_thresholds(req_tree)
```

### Symptom: Parser fails on a requirement
**Check**: What's the error? Is there an unsupported threshold type?

```python
try:
    result = parse_requirement(req_data)
except RequirementParseError as e:
    print(f"Parse error: {e}")
    print(f"Requirement data: {req_data}")
```

### Symptom: Degree requires too many/too few courses
**Check**: Are the threshold cutoffs correct?

Look at the parsed tree and verify the cutoffs match the intended requirement.

## Implementation Notes

### Parser Location
- **File**: `backend/courses/requirements/parser.py`
- **Function**: `parse_requirement()`
- **Lines**: 166-204 (threshold inference logic)

### Type Definitions
- **File**: `backend/courses/requirements/types.py`
- **Classes**: `RequirementThreshold`, `RequirementGroup`

### Constraint Builder
- **File**: `backend/optimizer/requirement_constraint_builder.py`
- **Function**: `_build_group()`
- Translates thresholds into CP-SAT constraints

## Known Limitations and Issues

### Issue 1: Plain String Thresholds Are Ignored (CRITICAL)

**Status**: Open as of 2025-01-23  
**Severity**: High - Affects most degrees

Plain string requirements (e.g., "72 units of electives", "2 math subjects (first decimal ≥ 1)") have thresholds that are **completely ignored** by the constraint builder. Currently, ALL plain strings are marked as "always satisfied" regardless of their threshold.

**Impact:**
- ~211 plain string requirements across all Fireroad data
- 100% have thresholds (79% subject-based, 16% unit-based)
- Nearly every major has plain string elective requirements
- Students can "graduate" without actually meeting these requirements

**See**: `PLAIN_STRING_REQUIREMENTS_ANALYSIS.md` for comprehensive analysis and proposed solutions.

### Issue 2: Unit-Based Thresholds in Groups Not Implemented

**Status**: Open  
**Severity**: Medium

Group nodes with `criterion: "units"` fall back to subject counting with a warning. This is less critical than Issue 1 because most unit-based requirements are encoded as plain strings anyway.

**Workaround**: Use plain strings with unit thresholds (but see Issue 1).

## References

- [Fireroad Requirements Format](https://fireroad.mit.edu/requirements/) - Official format specification
- [CP-SAT Documentation](https://developers.google.com/optimization/cp/cp_solver) - Google OR-Tools constraint solver
- `backend/fuzzers/requirements_fuzzer.py` - Standalone fuzzer for testing all Fireroad requirements
- `PREREQUISITE_BUG_ANALYSIS.md` - Analysis of the missing prerequisite bug (related issue)
- `PLAIN_STRING_REQUIREMENTS_ANALYSIS.md` - Comprehensive analysis of plain string requirements and handling strategies

## Changelog

### 2025-01-23: Automatic Threshold Inference
- **Bug**: Groups without explicit thresholds had `threshold=None`, causing optimizer infeasibility
- **Fix**: Parser now automatically infers thresholds from `connection-type`
- **Impact**: Fixed Course 1 and Course 7 infeasibility
- **Tests Added**: 5 unit tests, 3 fuzzer tests for all Fireroad requirements
- **Author**: Claude (with human verification)
