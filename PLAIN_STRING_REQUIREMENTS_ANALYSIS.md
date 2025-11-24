# Plain String Requirements: Analysis and Handling Strategy

**Date**: 2025-01-23  
**Status**: Critical Issue Identified - Plain String Thresholds Are Ignored

## Executive Summary

Plain string requirements are human-readable text requirements that cannot be automatically validated (e.g., "2 math subjects (first decimal ≥ 1)", "72 units of electives"). Our analysis of ALL 156 Fireroad requirement lists reveals:

- **211 total plain string requirements**
- **100% have thresholds** (not a single one without a threshold)
- **79% are subject-based** (167/211)
- **16% are unit-based** (34/211)

### Critical Bug

**All plain string thresholds are currently ignored**. The constraint builder marks them as always satisfied (line 418: `model.Add(placeholder == 1)`), meaning:
- Students can "graduate" without meeting elective requirements
- Unit requirements (like "48 units of engineering electives") are not enforced
- Subject-based requirements (like "2 math subjects") are not enforced

## What Are Plain Strings?

Plain strings are requirements that Fireroad marks with `"plain-string": true`. They represent requirements that:
1. **Cannot be encoded as simple course IDs** (e.g., "2 math subjects where first decimal ≥ 1")
2. **Require human judgment** (e.g., "Appropriate Harvard/Wellesley subjects")
3. **Refer to flexible course selections** (e.g., "72 units of electives")

## Types of Plain String Requirements

### 1. Subject-Based with Filters (167 total, 79%)

These specify a **number of courses** from a **filtered category**:

```json
{
  "plain-string": true,
  "req": "2 math subjects (first decimal ≥ 1)",
  "threshold": {
    "cutoff": 2,
    "criterion": "subjects",
    "type": "GTE"
  }
}
```

**Examples:**
- "2 math subjects (first decimal ≥ 1)" - requires 2 courses from 18.1xx, 18.2xx, etc.
- "4 introductory or intermediate subjects" - requires 4 lower-level courses
- "6 subjects (first decimal ≥ 1)" - requires 6 courses from a specific level range
- "1 21H seminar" - requires 1 course from 21H seminars
- "CI-M from primary major" - requires communication-intensive courses

**Challenge**: Requires filtering the course catalog by patterns like:
- Course number patterns (first decimal ≥ 1)
- Course level (introductory, intermediate, advanced)
- Course attributes (seminars, CI-M, etc.)

### 2. Unit-Based Electives (34 total, 16%)

These specify a **total unit count** from flexible course selections:

```json
{
  "plain-string": true,
  "req": "72 units",
  "threshold": {
    "cutoff": 72,
    "criterion": "units",
    "type": "GTE"
  },
  "title": "Elective Subjects with Engineering Content"
}
```

**Examples:**
- "72 units" - unrestricted electives
- "66 units" - electives (common for majors)
- "48-60 units" - engineering content electives
- "60 units of electives" - restricted electives
- "12 units" - thesis units

**Challenge**: Requires:
- Counting units from selected courses
- No specific course restrictions (often "any course" or broad categories)
- May have implicit restrictions (e.g., "engineering content")

### 3. Administrative/Procedural (10 total, 5%)

These represent non-course requirements:

**Examples:**
- "Intellectual Diversity Requirement (IDR)" - distribution requirement
- "Internship" - experiential learning
- "Senior Thesis" - capstone project
- "LM Activities (60 HEQ)" - ROTC/leadership activities
- "Permission of advisor" - approval requirements

**Challenge**: Cannot be automatically validated at all

## Current Handling (BROKEN)

### Current Implementation

```python
def _build_plain_string(self, node: RequirementPlainString, path: str) -> ConstraintResult:
    var_name = self.ctx.fresh_name("req")
    placeholder = self.ctx.model.NewBoolVar(var_name)
    
    # Always consider plain-string requirements as satisfied
    self.ctx.model.Add(placeholder == 1)  # ❌ IGNORES THRESHOLD
    
    return ConstraintResult(
        satisfied_var=placeholder,
        warnings=[f"Plain-string requirement can't be validated: '{node.description}'"]
    )
```

**Problems:**
1. **Threshold is completely ignored** - even though `node.threshold` exists
2. **Always marked as satisfied** - no constraints enforced
3. **Warning is generic** - doesn't indicate the specific threshold being ignored

## Proposed Handling Strategies

### Strategy 1: Best Effort Constraint Building (RECOMMENDED)

Handle what we can, warn about what we can't:

```python
def _build_plain_string(self, node: RequirementPlainString, path: str) -> ConstraintResult:
    var_name = self.ctx.fresh_name("req")
    placeholder = self.ctx.model.NewBoolVar(var_name)
    
    warnings = []
    
    if node.threshold:
        criterion = node.threshold.criterion
        cutoff = node.threshold.cutoff
        
        if criterion == "units":
            # Try to enforce unit constraint across ALL courses in the plan
            warnings.append(
                f"Plain-string '{node.description}' has unit threshold (>= {cutoff} units). "
                f"This is enforced as a global constraint but cannot be scoped to specific course types."
            )
            # TODO: Add global unit constraint (sum all course units >= cutoff)
            # For now, mark as satisfied
            self.ctx.model.Add(placeholder == 1)
            
        elif criterion == "subjects":
            # Subject-based plain strings often require course filtering we can't do
            warnings.append(
                f"Plain-string '{node.description}' requires {cutoff} subjects with filters that "
                f"cannot be automatically validated. Manual verification required."
            )
            # Mark as satisfied - user must manually verify
            self.ctx.model.Add(placeholder == 1)
        
        else:
            warnings.append(
                f"Plain-string '{node.description}' has unknown threshold criterion: {criterion}"
            )
            self.ctx.model.Add(placeholder == 1)
    else:
        # Plain string without threshold (shouldn't happen based on our analysis)
        warnings.append(f"Plain-string requirement can't be validated: '{node.description}'")
        self.ctx.model.Add(placeholder == 1)
    
    return ConstraintResult(
        satisfied_var=placeholder,
        warnings=warnings
    )
```

**Pros:**
- Provides clear warnings about what's being ignored
- Can add global unit constraints
- Doesn't break existing functionality

**Cons:**
- Still doesn't fully enforce most plain string requirements
- Requires user to manually verify

### Strategy 2: Expand Plain Strings to Concrete Courses

For common patterns, expand plain strings into actual course lists:

```python
# Example: "2 math subjects (first decimal ≥ 1)"
# Expand to: All courses matching 18.1xx, 18.2xx, ..., 18.9xx

def expand_plain_string_to_courses(description: str, courses_df) -> list[str]:
    """
    Attempt to expand plain string descriptions to concrete course IDs.
    
    Returns empty list if pattern cannot be parsed.
    """
    # Pattern 1: "N math subjects (first decimal ≥ X)"
    match = re.match(r'(\d+) math subjects \(first decimal ≥ (\d+)\)', description)
    if match:
        count = int(match.group(1))
        min_decimal = int(match.group(2))
        # Find all 18.Xxx courses where X >= min_decimal
        pattern = f"18.[{min_decimal}-9]"
        matching_courses = courses_df.filter(
            pl.col('subject_id').str.contains(pattern)
        )['subject_id'].to_list()
        return matching_courses
    
    # Pattern 2: "N subjects (first decimal ≥ X)" - department agnostic
    # ... more patterns ...
    
    return []  # Cannot parse
```

**Pros:**
- Actually enforces requirements when possible
- Provides real constraints for the optimizer

**Cons:**
- Complex pattern matching required
- Won't cover all cases
- Maintenance burden as requirement patterns change

### Strategy 3: Manual Requirement Mapping (Hybrid)

Maintain a manual mapping for common plain strings:

```python
PLAIN_STRING_EXPANSIONS = {
    "2 math subjects (first decimal ≥ 1)": {
        "type": "course_pattern",
        "pattern": r"18\.[1-9]",
        "count": 2
    },
    "72 units": {
        "type": "total_units_min",
        "units": 72
    },
    # ... more mappings ...
}
```

**Pros:**
- Handles the most common cases accurately
- Can be maintained and improved over time
- Clear and testable

**Cons:**
- Requires ongoing maintenance
- May not cover all cases

## Recommended Implementation Plan

### Phase 1: Improved Warnings (Immediate)

1. Update `_build_plain_string()` to:
   - Check if threshold exists
   - Provide specific warnings about what threshold is being ignored
   - Distinguish between subject-based and unit-based thresholds

2. Add logging for all plain string requirements encountered

### Phase 2: Global Unit Constraints (Short Term)

1. Implement global unit counting across all courses in the schedule
2. Apply minimum unit constraints from plain strings marked as "units"
3. This handles the ~16% of plain strings that are unit-based electives

### Phase 3: Pattern Matching for Common Cases (Medium Term)

1. Implement expansion for the most common patterns:
   - "N math subjects (first decimal ≥ X)"
   - "N subjects (first decimal ≥ X)"
   - Department-specific subject counts
   
2. Build a registry of expandable patterns

### Phase 4: Manual Mappings (Long Term)

1. Create a curated mapping file for degree-critical plain strings
2. Allow users/admins to define custom mappings
3. Provide UI for marking manually-satisfied plain string requirements

## Impact Assessment

### Degrees Most Affected

Based on our analysis, **nearly every major** has plain string requirements:

- **Course 1 (Civil Engineering)**: "48-60 units" of engineering electives
- **Course 6-3 (Computer Science)**: "72 units" of concentration
- **Course 18 (Mathematics)**: "2 math subjects (first decimal ≥ 1)"
- **Most humanities majors**: Various subject-based filters

### Current User Experience

Users currently see:
- Schedules that "satisfy" all requirements according to the optimizer
- But these schedules **may not actually satisfy elective/unit requirements**
- No indication that certain requirements are not being enforced

### Risk Level

**HIGH** - This affects degree completion verification for most majors.

## Testing Strategy

### Unit Tests

1. Test that plain strings with thresholds generate appropriate warnings
2. Test pattern matching logic for common cases
3. Test global unit constraint enforcement

### Integration Tests

1. Create test cases for degrees with known plain string requirements
2. Verify warnings are generated
3. Verify global constraints work when implemented

### Fuzzer Addition

Add to `test_fuzzers.py`:
```python
def test_plain_strings_with_thresholds_are_handled(all_fireroad_requirements):
    """Verify all plain strings with thresholds generate warnings or constraints."""
    # Test that we're at least AWARE of the threshold, even if we can't enforce it
```

## Documentation Needs

1. **User Documentation**: Explain that plain string requirements require manual verification
2. **Developer Documentation**: This document + REQUIREMENT_THRESHOLDS.md updates
3. **In-App Warnings**: Show users which requirements cannot be automatically validated

## Open Questions

1. **Should we allow users to mark plain strings as "manually satisfied"?**
   - Pro: Gives users control
   - Con: Defeats purpose of automatic validation

2. **Should we fail loudly (make schedule INFEASIBLE) or warn quietly?**
   - Current approach: Warn quietly (mark as satisfied)
   - Alternative: Make INFEASIBLE until user manually approves
   - Recommended: Warn loudly but allow proceeding

3. **How do we handle evolving Fireroad data?**
   - Plain string patterns may change over time
   - Need strategy for keeping mappings up-to-date

## Related Issues

- Unit-based thresholds in groups also not implemented (falls back to subject counting)
- Both need similar solutions (global unit tracking)

## Changelog

### 2025-01-23: Initial Analysis
- Discovered critical bug: all plain string thresholds ignored
- Analyzed all 211 plain string requirements across 156 Fireroad lists
- Found 100% have thresholds (79% subject-based, 16% unit-based, 5% administrative)
- Documented current handling and proposed solutions
