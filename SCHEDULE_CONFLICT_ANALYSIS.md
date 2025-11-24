# Schedule Conflict Detection Analysis

**Date:** 2025-11-23
**Objective:** Investigate how to implement calendar feasibility constraints for course scheduling in the optimizer

## Executive Summary

Implementing hard constraints to prevent schedule conflicts is **MEDIUM difficulty** (estimated 2-3 days). The existing constraint infrastructure is well-designed and can easily accommodate schedule conflict detection. The main work involves:

1. Extending time parsing utilities to extract end times (not just start times)
2. Implementing interval overlap detection
3. Efficiently handling O(N²) conflict pair checking
4. Integrating with the existing CP-SAT constraint system

## Current System Architecture

### Constraint Infrastructure

Our optimizer uses **Google OR-Tools CP-SAT** solver with a clean constraint architecture:

- **Hard Constraints**: Must be satisfied (implemented via `HardConstraint` protocol)
- **Soft Constraints**: Objectives to optimize (tier-based penalty system)
- **Constraint Registry**: Enable/disable constraints via API
- **Existing Example**: `BanIAP` constraint in `backend/optimizer/constraints/scheduling.py:15`

### Available Data

**Schedule Data Format** (already in `courses_df['schedule']`):
```
"Lecture,4-237/MWF/0/1;Recitation,34-101/TR/0/1,34-301/TR/0/2"
```

Format breakdown:
- Semicolon-separated sections (Lecture, Recitation, Lab, Design)
- Comma-separated meetings within each section
- Meeting format: `room/days/is_evening/time`
  - `days`: "MWF", "TR", etc.
  - `is_evening`: "0" (day) or "1" (evening)
  - `time`: "9", "1-2.30", "5.30 PM", etc.

**Existing Parsing Utilities** (`backend/optimizer/objectives/utils.py`):
- `parse_schedule_time_slots()` - Extracts (days, start_time_minutes) tuples
- `parse_time_to_minutes()` - Converts time strings to minutes since midnight
- `parse_schedule_has_friday()` - Example of schedule parsing in use

**Gap**: Current utilities only extract **start times**, not end times or durations.

## Hydrant Investigation

### Overview

[Hydrant](https://github.com/sipb/hydrant) is MIT's course planning app maintained by SIPB. It implements schedule conflict detection using a different approach than we would use.

**Tech Stack:**
- Frontend: TypeScript + React + FullCalendar
- Backend: Python scrapers
- Conflict Detection: Custom backtracking algorithm

### Time Representation System

Hydrant uses a **fixed slot numbering system** (`src/lib/dates.ts`):

- **Granularity**: 30-minute blocks
- **Coverage**: Monday-Friday, 6 AM - 11 PM
- **Total Slots**: 34 slots/day × 5 days = 170 slots (numbered 0-169)
- **Encoding**: `slot_number = 34 * (day - 1) + time_offset`

**Example Slot Numbers:**
```
Monday 9:00 AM    → slot 12  (34*0 + 12)
Monday 9:30 AM    → slot 13
Tuesday 1:00 PM   → slot 48  (34*1 + 14)
Friday 10:00 PM   → slot 168 (34*4 + 32)
```

### Conflict Detection Algorithm

**1. Timeslot Data Structure** (`src/lib/activity.ts`):
```typescript
class Timeslot {
  startSlot: Slot;
  numSlots: number;  // Duration in 30-min blocks

  get endSlot(): Slot {
    return this.startSlot.add(this.numSlots);
  }

  conflicts(other: Timeslot): boolean {
    // Classic interval overlap test
    return (
      this.startSlot.slot < other.endSlot.slot &&
      other.startSlot.slot < this.endSlot.slot
    );
  }
}
```

**Key Insight**: Two intervals overlap if `start1 < end2 AND start2 < end1`

**2. Section-Level Conflict Counting** (`src/lib/class.ts`):
```typescript
countConflicts(currentSlots: Timeslot[]): number {
  let conflicts = 0;
  for (const slot of this.timeslots) {
    for (const otherSlot of currentSlots) {
      conflicts += slot.conflicts(otherSlot) ? 1 : 0;
    }
  }
  return conflicts;
}
```

Compares each meeting time of a course section against all currently scheduled meetings.

**3. Schedule Optimization** (`src/lib/calendarSlots.ts`):

Uses **greedy backtracking with pruning**:
1. Try different section combinations for courses
2. Calculate conflicts at each step
3. Prune branches exceeding minimum conflicts found
4. Return all schedules with minimum conflicts

**Important**: Hydrant treats conflicts as a **soft constraint** (minimize conflicts) rather than a **hard constraint** (forbid conflicts).

### Why Hydrant's Approach Differs

| Aspect | Hydrant | Our System |
|--------|---------|------------|
| **Use Case** | Interactive course selection | Automatic schedule optimization |
| **User Workflow** | User manually picks sections | Optimizer chooses everything |
| **Conflict Handling** | Soft (allow but minimize) | Hard (forbid entirely) |
| **Solver** | Custom backtracking | Google OR-Tools CP-SAT |
| **Data Structure** | Pre-parsed Slot objects | Parse-on-demand from strings |
| **Performance Focus** | Fast incremental updates | Comprehensive optimization |

## Recommended Implementation

### Strategy

**Don't copy Hydrant's slot numbering system.** Instead:
1. Parse schedule strings directly to time ranges
2. Use simple interval overlap detection (Hydrant's algorithm)
3. Add hard constraints to CP-SAT model
4. Let CP-SAT handle the optimization

### Implementation Steps

#### Step 1: Extend Time Parsing (~2-4 hours)

Enhance `backend/optimizer/objectives/utils.py` to extract end times:

```python
def parse_time_range(time_str: str, is_evening: str) -> tuple[int, int] | None:
    """
    Parse time string to (start_minutes, end_minutes) tuple.

    Args:
        time_str: Time like "9", "1-2.30", "5.30 PM"
        is_evening: "0" for day, "1" for evening

    Returns:
        (start, end) in minutes since midnight, or None if unparseable

    Examples:
        "9", "0" -> (540, 590)  # 9:00-9:50 AM (assume 50-min default)
        "1-2.30", "0" -> (780, 870)  # 1:00-2:30 PM
        "5.30 PM", "1" -> (1050, 1140)  # 5:30-7:00 PM
    """
    pass

def parse_schedule_ranges(schedule: str | None) -> list[tuple[set[str], int, int]]:
    """
    Parse schedule into list of (day_set, start_min, end_min) tuples.

    Args:
        schedule: Schedule string from Fireroad API

    Returns:
        List of (days, start, end) tuples, e.g.:
        [({'M','W','F'}, 540, 630), ({'T','R'}, 810, 920)]

    Examples:
        "Lecture,4-237/MWF/0/9;Recitation,34-101/TR/0/1-2.30"
        -> [({'M','W','F'}, 540, 630), ({'T','R'}, 780, 870)]
    """
    pass
```

**Challenges:**
- Handle various time formats: "9", "1-2.30", "5.30 PM", "4-7 PM"
- Infer duration when only start time given (assume 50 min? 80 min?)
- Handle "TBA" meetings gracefully

#### Step 2: Implement Conflict Detection (~2-4 hours)

```python
def schedules_conflict(schedule_a: str | None, schedule_b: str | None) -> bool:
    """
    Check if two course schedules have any time conflicts.

    Uses interval overlap detection: two intervals overlap if
    start1 < end2 AND start2 < end1 (same as Hydrant's algorithm).

    Args:
        schedule_a: First course schedule string
        schedule_b: Second course schedule string

    Returns:
        True if any meetings overlap
    """
    if not schedule_a or not schedule_b:
        return False

    ranges_a = parse_schedule_ranges(schedule_a)
    ranges_b = parse_schedule_ranges(schedule_b)

    for days_a, start_a, end_a in ranges_a:
        for days_b, start_b, end_b in ranges_b:
            # Check if days overlap
            if days_a & days_b:  # Set intersection
                # Check if times overlap (Hydrant's algorithm)
                if start_a < end_b and start_b < end_a:
                    return True

    return False
```

#### Step 3: Create Hard Constraint (~4-6 hours)

Add to `backend/optimizer/constraints/scheduling.py`:

```python
class NoScheduleConflicts:
    """
    Hard constraint: Prevent scheduling courses with overlapping meeting times.

    This ensures the final schedule is calendar-feasible (no time conflicts).
    """

    def __init__(self):
        self._conflict_cache: dict[tuple[int, int], bool] | None = None

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ConstraintContext
    ) -> None:
        """
        Add schedule conflict constraints to model.

        For each pair of courses that have time conflicts, add a constraint
        that they cannot both be taken in the same semester.
        """
        # Precompute all conflicting course pairs (O(N²) but done once)
        conflicts = self._find_all_conflicts(context.courses_df)

        print(f"[NoScheduleConflicts] Found {len(conflicts)} conflicting course pairs")

        # Add constraints for each semester
        constraint_count = 0
        for semester in range(1, context.max_semesters + 1):
            for (idx_a, idx_b) in conflicts:
                # Only add constraint if both courses could be taken this semester
                if (idx_a, semester) in take_vars and (idx_b, semester) in take_vars:
                    var_a = take_vars[(idx_a, semester)]
                    var_b = take_vars[(idx_b, semester)]

                    # Hard constraint: cannot take both courses in same semester
                    model.Add(var_a + var_b <= 1)
                    constraint_count += 1

        print(f"[NoScheduleConflicts] Added {constraint_count} constraints across {context.max_semesters} semesters")

    def _find_all_conflicts(self, courses_df: pl.DataFrame) -> list[tuple[int, int]]:
        """
        Find all pairs of courses that have schedule conflicts.

        Returns:
            List of (course_idx_a, course_idx_b) tuples where a < b
        """
        if self._conflict_cache is not None:
            return self._conflict_cache

        conflicts = []
        n = len(courses_df)

        # Check all pairs (only need to check i < j due to symmetry)
        for i in range(n):
            schedule_i = courses_df[i, 'schedule'] if 'schedule' in courses_df.columns else None
            if not schedule_i:
                continue

            for j in range(i + 1, n):
                schedule_j = courses_df[j, 'schedule'] if 'schedule' in courses_df.columns else None
                if not schedule_j:
                    continue

                if schedules_conflict(schedule_i, schedule_j):
                    conflicts.append((i, j))

        self._conflict_cache = conflicts
        return conflicts

    def get_name(self) -> str:
        return "No Schedule Conflicts"

    def get_description(self) -> str:
        return "Hard constraint: prevents scheduling courses with overlapping meeting times"

    def get_category(self) -> str:
        return "scheduling"
```

**Performance Optimization:**
- Precompute conflicts once (O(N²) but cached)
- Only add constraints where both courses are valid for the semester
- For 1000 courses: worst case ~500K pairs, but most won't have schedule data or conflicts
- Typical case: ~10-50K actual constraints added

#### Step 4: Register and Test (~2-4 hours)

**A. Register in `backend/optimizer/constraints/registry.py`:**
```python
from .scheduling import BanIAP, NoScheduleConflicts

CONSTRAINTS_REGISTRY: dict[str, ConstraintMetadata] = {
    "ban_iap": ConstraintMetadata(...),
    "no_schedule_conflicts": ConstraintMetadata(
        key="no_schedule_conflicts",
        class_ref=NoScheduleConflicts,
        name="No Schedule Conflicts",
        description="Prevents scheduling courses with overlapping meeting times",
        category="scheduling",
        default_enabled=False,
    ),
}
```

**B. Export in `backend/optimizer/constraints/__init__.py`:**
```python
from .scheduling import BanIAP, NoScheduleConflicts

__all__ = [
    "ConstraintContext",
    "HardConstraint",
    "BanIAP",
    "NoScheduleConflicts",
]
```

**C. Use via API:**
```json
{
  "hardConstraints": ["ban_iap", "no_schedule_conflicts"],
  "markers": [...],
  "requirements": ["major6-3new", "girs"]
}
```

**D. Write Unit Tests:**
```python
# backend/tests/test_schedule_conflicts.py

def test_schedules_conflict_same_time():
    # MWF 9-10 vs MWF 9:30-10:30 -> conflict
    sched_a = "Lecture,4-237/MWF/0/9-10"
    sched_b = "Lecture,10-250/MWF/0/9.30-10.30"
    assert schedules_conflict(sched_a, sched_b) == True

def test_schedules_no_conflict_different_days():
    # MWF 9-10 vs TR 9-10 -> no conflict
    sched_a = "Lecture,4-237/MWF/0/9-10"
    sched_b = "Lecture,10-250/TR/0/9-10"
    assert schedules_conflict(sched_a, sched_b) == False

def test_schedules_no_conflict_different_times():
    # MWF 9-10 vs MWF 10-11 -> no conflict
    sched_a = "Lecture,4-237/MWF/0/9-10"
    sched_b = "Lecture,10-250/MWF/0/10-11"
    assert schedules_conflict(sched_a, sched_b) == False
```

## Edge Cases to Handle

### 1. Missing Schedule Data
- **Scenario**: Course has no schedule string or empty string
- **Handling**: Skip conflict checking (assume no conflict)

### 2. TBA Meetings
- **Scenario**: Meeting is "TBA" (time to be announced)
- **Handling**: Skip these meetings in conflict detection

### 3. Multiple Sections
- **Scenario**: Course has multiple section options (e.g., Recitation A or B)
- **Current Issue**: Fireroad schedule string shows ALL sections concatenated
- **Handling**: This is actually a limitation - we'd need section-level scheduling which requires more complex data
- **Workaround**: Conservative approach - if ANY section conflicts, flag as conflict

### 4. Evening vs Daytime
- **Scenario**: is_evening flag might affect time interpretation
- **Handling**: Already handled by `parse_time_to_minutes()`

### 5. Time Duration Inference
- **Scenario**: Some schedules only show start time, e.g., "9" without end time
- **Handling**: Need to infer duration (MIT classes are typically 50 min or 80 min)
- **Heuristic**: Assume 50 minutes for single times, or check course units

### 6. Cross-Year Scheduling
- **Scenario**: Courses offered in different years shouldn't conflict
- **Handling**: Already handled by semester isolation - only check conflicts within same semester

## Performance Analysis

### Complexity

**Conflict Detection:**
- **Preprocessing**: O(N² × P) where N=courses, P=avg meetings per course
  - ~1000 courses × ~1000 comparisons × ~2 meetings = ~2M comparisons
  - But many courses lack schedule data, reducing effective N
- **Constraint Addition**: O(C × S) where C=conflict pairs, S=semesters
  - ~10K conflicts × 12 semesters = ~120K constraints
  - CP-SAT handles this efficiently

**Optimization:**
- Precompute conflicts once (cache in constraint object)
- Only check valid semester combinations
- Skip courses without schedule data early

**Expected Runtime:**
- Preprocessing: ~1-2 seconds
- Constraint addition: ~0.1 seconds
- CP-SAT solving: No significant slowdown (constraints are simple)

## Comparison: Hydrant vs Our Approach

| Aspect | Hydrant | Our Autoroad System | Winner |
|--------|---------|---------------------|--------|
| **Solver** | Custom backtracking | Google OR-Tools CP-SAT | **Ours** (more powerful) |
| **Conflict Type** | Soft (minimize) | Hard (forbid) | **Ours** (stricter guarantee) |
| **Time Representation** | Fixed 30-min slots (0-169) | Minutes since midnight | **Ours** (simpler) |
| **Pre-processing** | Parse all to Slot objects | Parse on-demand | **Ours** (less memory) |
| **Algorithm** | Custom interval check | Same interval check | **Tie** |
| **Data Source** | MIT course catalog scraper | Fireroad API | **Tie** |
| **Integration** | Standalone system | Constraint in larger optimizer | **Ours** (more flexible) |

## Potential Issues & Solutions

### Issue 1: Schedule Data Quality
**Problem**: Fireroad schedule data might be incomplete, outdated, or incorrect

**Investigation Needed:**
- Compare Fireroad vs Hydrant's scraped data
- Check what percentage of courses have schedule data
- Validate schedule string format consistency

**Solution:**
- Start with warning mode: log conflicts but don't enforce
- Add data validation layer
- Fall back gracefully when schedule missing

### Issue 2: Section Selection
**Problem**: Courses have multiple sections (e.g., different recitation times)

**Current Limitation**: Our system doesn't model section selection within a course

**Potential Solutions:**
1. **Conservative**: If any section pair conflicts, forbid course pair
2. **Optimistic**: Only forbid if ALL sections conflict
3. **Advanced**: Model each section as separate decision variable (major refactor)

**Recommendation**: Start with #1 (conservative) - safer and simpler

### Issue 3: Performance at Scale
**Problem**: O(N²) conflict checking might be slow

**Benchmarking Needed:**
- Test with full course catalog (~1000 courses)
- Measure preprocessing time
- Profile constraint addition

**Optimizations if needed:**
- Spatial indexing (group by time slots)
- Parallel conflict checking
- Cache results aggressively

## Next Steps

### Immediate
1. ✅ **DONE**: Research Hydrant's implementation
2. **TODO**: Examine Fireroad schedule data quality
3. **TODO**: Implement `parse_time_range()` with comprehensive time format handling
4. **TODO**: Implement `schedules_conflict()` with tests

### Short-term
5. **TODO**: Create `NoScheduleConflicts` hard constraint
6. **TODO**: Register constraint in system
7. **TODO**: Write unit tests for edge cases
8. **TODO**: Integration test with real course data

### Validation
9. **TODO**: Compare results against Hydrant for same course selections
10. **TODO**: Benchmark performance with full catalog
11. **TODO**: User testing with real student schedules

## Conclusion

**Difficulty: MEDIUM** (2-3 days)

**Key Findings:**
1. ✅ Infrastructure is ready - constraint system is well-designed
2. ✅ Schedule data is available - Fireroad provides schedule strings
3. ✅ Algorithm is proven - Hydrant's interval overlap is simple and effective
4. ⚠️ Data quality unknown - need to validate Fireroad schedule completeness
5. ⚠️ Section selection is a limitation - current model doesn't support it

**Implementation is straightforward** because:
- We have better tools (CP-SAT vs backtracking)
- Core algorithm is simple (interval overlap)
- Existing constraint infrastructure makes integration easy
- Hydrant proves the concept works at MIT scale

**Main challenge**: Getting time parsing exactly right for all edge cases in MIT's schedule format.

**Recommendation**: Proceed with implementation using the strategy outlined above.

## References

- [Hydrant GitHub Repository](https://github.com/sipb/hydrant)
- [Hydrant Web Application](https://hydrant.mit.edu/)
- Internal: `backend/optimizer/constraints/base.py`
- Internal: `backend/optimizer/objectives/utils.py`
- Internal: `backend/api/routes/optimize.py`
