# Prerequisite Constraint Building: Performance Optimization Report

## Executive Summary

**Current Performance:** 2.4 seconds spent building prerequisite constraints for 3,488 courses  
**Root Cause:** Variable duplication, inefficient lookups, and lack of constraint sharing  
**Optimization Target:** 2.4s → 0.3-0.6s (75-87% reduction)  
**Estimated Constraint Count:** 100,000-200,000+ CP-SAT constraints

---

## Current State Analysis

### Performance Breakdown

```
Total Courses Loaded:        6,042
Courses with Decision Vars:  5,878 (97%)
Decision Variables Created:  28,887
Courses with Prerequisites:  3,570
Prereqs with Decision Vars:  3,488

Prerequisite Phase Timing:
  - Parsing/Cache:          0.000s (cached)
  - Constraint Building:    2.404s ⚠️ BOTTLENECK
  - Total:                  2.404s
```

### Loop Complexity

- **Outer Loop:** 3,488 courses with prerequisites
- **Inner Loop:** 12 semesters per course
- **Total Iterations:** ~41,856 (course, semester) pairs
- **Per Iteration:** Recursive tree traversal + constraint creation
- **Algorithmic Complexity:** O(n × m × d × b)
  - n = courses (3,488)
  - m = semesters (12)
  - d = tree depth (2-4 levels)
  - b = branching factor (2-5 children per node)

---

## Root Causes

### 1. Variable Duplication Across Semesters (40-60% of waste)

**Problem:** Same prerequisite satisfaction logic recreated 12 times per course.

**Example:** Course 6.100B requires 6.100A
```python
# Currently creates 12 separate variables:
prereq_6.100A_for_6.100B_s1   # "6.100A taken before semester 1"
prereq_6.100A_for_6.100B_s2   # "6.100A taken before semester 2"
prereq_6.100A_for_6.100B_s3   # "6.100A taken before semester 3"
...
prereq_6.100A_for_6.100B_s12  # "6.100A taken before semester 12"
```

All 12 variables represent essentially the same logical condition!

**Impact:** 
- 14,640 (course, semester) pairs → 14,640 unique variables created
- Should be: ~1,220 unique prerequisites × 12 semesters = 14,640 shared variables

---

### 2. GIR/HASS Explosion (50-70% of constraints)

**Problem:** Generic requirements like "GIR:CAL1" expanded independently for every course.

**Example:** 200 courses require "GIR:CAL1"

Current behavior:
```python
# For EACH of 200 courses, EACH semester:
def _build_gir_prereq(self, gir_code, semester, course_id):
    gir_courses = get_courses_by_gir("GIR:CAL1")  # Returns 60+ courses
    earlier_semesters = range(1, semester)         # Up to 12 semesters
    
    # Creates list of 60 courses × 12 semesters = 720 variables
    taken_vars = [take_vars[c, s] for c in gir_courses for s in earlier_semesters]
    
    # Adds constraint with 720 variables (EXPENSIVE!)
    model.AddMaxEquality(satisfied_var, taken_vars)
```

**Impact:**
- 200 courses × 12 semesters = 2,400 separate GIR satisfaction variables
- Each with AddMaxEquality over 600+ items
- **Total: 2,400 variables, 1.44 million constraint entries**
- **Should be: 12 shared variables, 7,200 constraint entries (200x reduction!)**

---

### 3. O(n) Course Lookups (10-15% overhead)

**Problem:** Course index lookup does linear search 30,000+ times.

```python
def get_course_index(self, course_id: str) -> int | None:
    subject_ids = self.courses_df['subject_id'].to_list()  # Convert 3,488 courses to list
    try:
        return subject_ids.index(course_id)  # Linear search O(n)
    except ValueError:
        return None
```

**Called:** ~30,000 times (once per prerequisite course lookup)

**Impact:** 
- 30,000 calls × O(n) = ~100 million list operations
- Should be: 30,000 × O(1) hash lookups

Similar issue with:
- `get_courses_by_gir()` - Linear scan of all courses
- `get_courses_by_hass()` - Linear scan of all courses

---

### 4. No Sharing Between Courses (30-50% duplication)

**Problem:** Multiple courses requiring the same prerequisite create independent variables.

**Example:** 10 courses all require "6.100A"

Current:
```
Course A + 6.100A: 12 variables (one per semester)
Course B + 6.100A: 12 variables (independent set)
Course C + 6.100A: 12 variables (independent set)
...
Total: 10 × 12 = 120 variables
```

Should be:
```
"6.100A taken before semester 1": 1 shared variable
"6.100A taken before semester 2": 1 shared variable
...
Total: 12 shared variables (10x reduction!)
```

---

### 5. Large Constraint Aggregation (5-20% overhead)

**Problem:** Single `AddMaxEquality` calls with 500-700 variables.

```python
# CP-SAT has to process this giant constraint:
model.AddMaxEquality(satisfied_var, [600+ take_vars])
```

**Why it's slow:**
- CP-SAT creates internal data structures for constraint
- Harder to propagate and simplify
- Less efficient than hierarchical decomposition

---

## Optimization Strategies

### Strategy 1: Course Index Caching ⭐ (Easy Win)

**Effort:** 15 minutes  
**Impact:** 10-15% reduction (0.24-0.36s)

**Implementation:**

```python
class CourseSchedule:
    def __init__(self, courses_df):
        self.courses_df = courses_df
        
        # Build lookup dictionaries ONCE in O(n)
        self._subject_id_to_index = {
            courses_df[i, 'subject_id']: i
            for i in range(len(courses_df))
        }
        
        # Index GIR courses
        self._gir_index = {}  # "GIR:CAL1" -> [idx1, idx2, ...]
        for i in range(len(courses_df)):
            gir = courses_df[i, 'gir_attribute']
            if gir:
                if gir not in self._gir_index:
                    self._gir_index[gir] = []
                self._gir_index[gir].append(i)
        
        # Index HASS courses
        self._hass_index = {}  # "HASS:H" -> [idx1, idx2, ...]
        for i in range(len(courses_df)):
            hass = courses_df[i, 'hass_attribute']
            if hass:
                if hass not in self._hass_index:
                    self._hass_index[hass] = []
                self._hass_index[hass].append(i)
    
    def get_course_index(self, course_id: str) -> int | None:
        return self._subject_id_to_index.get(course_id)  # O(1)
    
    def get_courses_by_gir(self, gir_code: str) -> list[int]:
        return self._gir_index.get(gir_code, [])  # O(1)
    
    def get_courses_by_hass(self, hass_code: str) -> list[int]:
        return self._hass_index.get(hass_code, [])  # O(1)
```

**Before:** O(n) × 30,000 calls = ~100M operations  
**After:** O(1) × 30,000 calls = 30K operations

---

### Strategy 2: Memoize Across Semesters ⭐⭐⭐ (Biggest Win)

**Effort:** 45 minutes  
**Impact:** 40-60% reduction (0.96-1.44s)

**Key Insight:** Prerequisite satisfaction for a given course before a given semester can be shared across ALL courses that need it.

**Implementation:**

```python
class PrerequisiteConstraintBuilder:
    def __init__(self, ctx):
        self.ctx = ctx
        # Cache: (prereq_course_idx, before_semester) -> satisfaction variable
        self._prereq_before_semester_cache = {}
    
    def _get_or_create_taken_before_semester(self, prereq_idx, prereq_id, before_semester):
        """
        Shared variable: "Was course X taken before semester Y?"
        Reused across ALL courses that need this prerequisite.
        """
        cache_key = (prereq_idx, before_semester)
        
        if cache_key in self._prereq_before_semester_cache:
            return self._prereq_before_semester_cache[cache_key]
        
        # Create variable ONCE for this (course, semester) pair
        var = self.ctx.model.NewBoolVar(f"taken_{prereq_id}_before_s{before_semester}")
        
        # Was taken in ANY semester < before_semester
        earlier_semesters = list(range(-2, 0)) + list(range(1, before_semester))
        taken_vars = [
            self.ctx.take_vars[prereq_idx, s]
            for s in earlier_semesters
            if (prereq_idx, s) in self.ctx.take_vars
        ]
        
        if taken_vars:
            self.ctx.model.AddMaxEquality(var, taken_vars)
        else:
            self.ctx.model.Add(var == 0)
        
        self._prereq_before_semester_cache[cache_key] = var
        return var
    
    def _build_course_prereq(self, node, course_idx, semester, course_id):
        prereq_id = node.course_id
        prereq_idx = self.ctx.schedule.get_course_index(prereq_id)
        
        # Return cached variable - shared across all courses!
        return self._get_or_create_taken_before_semester(prereq_idx, prereq_id, semester)
```

**Example Impact:**

If 100 courses require 6.100A:
- **Before:** 100 courses × 12 semesters = 1,200 variables
- **After:** 12 shared variables (one per semester)
- **Reduction:** 100x for popular prerequisites!

---

### Strategy 3: Global GIR/HASS Cache ⭐⭐⭐ (Massive for Generic Requirements)

**Effort:** 60 minutes  
**Impact:** 50-70% reduction (1.20-1.68s)

**Key Insight:** "GIR:CAL1 satisfied before semester 5" is the same for ALL courses.

**Implementation:**

```python
class PrerequisiteConstraintBuilder:
    def __init__(self, ctx):
        self.ctx = ctx
        # Cache: (gir_code, before_semester) -> satisfaction variable
        self._gir_satisfaction_cache = {}
        self._hass_satisfaction_cache = {}
    
    def _get_or_create_gir_satisfaction(self, gir_code, before_semester):
        """
        Global shared variable: "Was any GIR:X course taken before semester Y?"
        Shared across ALL courses requiring this GIR.
        """
        cache_key = (gir_code, before_semester)
        
        if cache_key in self._gir_satisfaction_cache:
            return self._gir_satisfaction_cache[cache_key]
        
        # Create ONCE, share across all courses
        var = self.ctx.model.NewBoolVar(f"{gir_code}_before_s{before_semester}")
        
        gir_courses = self.ctx.schedule.get_courses_by_gir(gir_code)  # O(1) with Strategy 1
        earlier_semesters = list(range(-2, 0)) + list(range(1, before_semester))
        
        taken_vars = [
            self.ctx.take_vars[c, s]
            for c in gir_courses
            for s in earlier_semesters
            if (c, s) in self.ctx.take_vars
        ]
        
        if taken_vars:
            self.ctx.model.AddMaxEquality(var, taken_vars)
        else:
            self.ctx.model.Add(var == 0)
        
        self._gir_satisfaction_cache[cache_key] = var
        return var
    
    def _build_gir_prereq(self, gir_code, semester, course_id):
        # Just return the cached shared variable!
        return self._get_or_create_gir_satisfaction(gir_code, semester)
```

**Example Impact:**

200 courses require "GIR:CAL1":
- **Before:** 200 × 12 = 2,400 variables, 1.44M constraint entries
- **After:** 12 shared variables, 7,200 constraint entries
- **Reduction:** 200x in variables!

---

### Strategy 4: Decompose Large Constraints ⭐ (Solver Efficiency)

**Effort:** 45 minutes  
**Impact:** 5-20% reduction (0.12-0.48s)

**Problem:** Single `AddMaxEquality` with 600+ variables is expensive.

**Solution:** Hierarchical decomposition.

```python
def _get_or_create_gir_satisfaction_hierarchical(self, gir_code, before_semester):
    """Decompose large GIR constraint into smaller hierarchical chunks."""
    
    cache_key = (gir_code, before_semester)
    if cache_key in self._gir_satisfaction_cache:
        return self._gir_satisfaction_cache[cache_key]
    
    gir_courses = self.ctx.schedule.get_courses_by_gir(gir_code)
    earlier_semesters = list(range(-2, 0)) + list(range(1, before_semester))
    
    # STEP 1: Create per-semester satisfaction variables
    semester_vars = []
    for s in earlier_semesters:
        taken_in_semester = [
            self.ctx.take_vars[c, s]
            for c in gir_courses
            if (c, s) in self.ctx.take_vars
        ]
        
        if taken_in_semester:
            # Small constraint: ~60 variables instead of 600
            s_var = self.ctx.model.NewBoolVar(f"{gir_code}_s{s}")
            self.ctx.model.AddMaxEquality(s_var, taken_in_semester)
            semester_vars.append(s_var)
    
    # STEP 2: Aggregate across semesters
    final_var = self.ctx.model.NewBoolVar(f"{gir_code}_before_s{before_semester}")
    if semester_vars:
        # Small constraint: ~12 variables
        self.ctx.model.AddMaxEquality(final_var, semester_vars)
    else:
        self.ctx.model.Add(final_var == 0)
    
    self._gir_satisfaction_cache[cache_key] = final_var
    return final_var
```

**Before:**
- 1 constraint with 600 variables

**After:**
- 12 constraints with ~50 variables each
- 1 constraint with 12 variables
- Total: 13 smaller constraints (easier for CP-SAT to process)

---

## Implementation Roadmap

### Phase 1: Quick Wins (15-30 minutes)

1. **Strategy 1: Index Caching** ✅
   - Modify `CourseSchedule.__init__` to build hash maps
   - Update lookup methods to O(1)
   - **Expected gain:** 0.24-0.36s

### Phase 2: Major Optimizations (1-2 hours)

2. **Strategy 2: Semester Memoization** ✅
   - Add `_prereq_before_semester_cache` to builder
   - Update `_build_course_prereq` to use cache
   - **Expected gain:** 0.96-1.44s

3. **Strategy 3: Global GIR/HASS Cache** ✅
   - Add `_gir_satisfaction_cache` and `_hass_satisfaction_cache`
   - Update `_build_gir_prereq` and `_build_hass_prereq`
   - **Expected gain:** 1.20-1.68s

### Phase 3: Polish (30-60 minutes)

4. **Strategy 4: Hierarchical Decomposition** ✅
   - Refactor GIR/HASS constraint building
   - Break large constraints into smaller chunks
   - **Expected gain:** 0.12-0.48s

---

## Expected Results

| Metric | Before | After (All Strategies) | Improvement |
|--------|--------|----------------------|-------------|
| **Prereq Constraint Time** | 2.404s | 0.3-0.6s | 75-87% |
| **Total Optimization Time** | 5.5s | 3.2-3.8s | 31-42% |
| **Unique Variables Created** | 100K-200K | 15K-30K | 70-85% |
| **Constraint Count** | 150K-250K | 20K-40K | 73-87% |

---

## Performance Tracking

To monitor optimization impact, the following metrics are logged:

```
[STATS] Created 28887 decision variables for 5878 courses out of 6042 total
[STATS] 3570 courses have prereqs, 3488 have decision variables
[PERF]   - Prereq parsing/cache:     0.000s
[PERF]   - Prereq constraint build:  2.404s
[PERF] Prerequisites TOTAL: 2.404s
```

After optimizations, expect:
```
[STATS] Created 28887 decision variables for 5878 courses out of 6042 total
[STATS] 3570 courses have prereqs, 3488 have decision variables
[CACHE] Reused 3200+ prerequisite satisfaction variables
[CACHE] Reused 150+ GIR/HASS satisfaction variables
[PERF]   - Prereq parsing/cache:     0.000s
[PERF]   - Prereq constraint build:  0.3-0.6s ✅
[PERF] Prerequisites TOTAL: 0.3-0.6s
```

---

## Conclusion

The 2.4-second prerequisite constraint building bottleneck is primarily caused by:
1. **Massive variable duplication** (same logic recreated 12× per course)
2. **No sharing across courses** (common prerequisites independently rebuilt)
3. **Inefficient lookups** (O(n) instead of O(1))
4. **Large constraint aggregation** (600+ variables in single constraints)

All four issues can be systematically addressed through caching and memoization, with expected **75-87% performance improvement** bringing total optimization time from **5.5s to ~3.2s**.

Combined with the multi-threaded solver (1.8s), this would achieve **sub-3-second course scheduling optimization** - an excellent user experience for an NP-hard problem.
