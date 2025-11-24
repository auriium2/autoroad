# Test Suite Recommendations

Following the prerequisite parser bug postmortem, this document outlines which tests to keep, remove, or improve, and identifies gaps that need new tests.

## Summary

- **Keep**: 6 test files (mostly unchanged)
- **Revise**: 2 test files (remove trivial tests)
- **Add**: 4 new test files for markers, category weighting, and constraints

---

## Current Tests: Keep/Remove/Revise

### ✅ **KEEP** - test_fuzzers.py
**Verdict**: Keep all tests unchanged

**Rationale**:
- Validates parser works on ALL real Fireroad data (1000+ courses, 100+ requirements)
- Quality gates: `test_success_rate_meets_threshold` ensures 99%+ success rate
- Caught 12 prerequisite parsing bugs through exhaustive fuzzing
- `test_all_groups_have_thresholds` - regression test for threshold inference bug

**Value**: High - catches real-world edge cases that unit tests miss

---

### ✅ **KEEP** - test_prerequisites_parser_property.py
**Verdict**: Keep all tests unchanged

**Rationale**:
- Property-based testing using Hypothesis
- Tests invariants that must hold for ANY input:
  - Parser never returns empty groups (critical bug fix)
  - AND groups have threshold = # of items
  - OR groups have threshold = 1
  - All nodes are well-formed
- Generates thousands of random inputs to find edge cases

**Value**: High - found the empty group bug, prevents regressions

---

### ✅ **KEEP** - test_optimizer_integration.py
**Verdict**: Keep all tests unchanged

**Rationale**:
- Tests real marker behaviors that caused production bugs:
  - `test_override_does_not_block_other_courses` - caught critical regression
  - `test_ase_course_not_duplicated_in_regular_semester` - caught duplication bug
  - `test_must_take_forces_course_in_any_regular_semester` - validates Must Take logic
- Every test validates actual production scenarios with real constraints

**Value**: Critical - regression tests for features that have repeatedly broken

---

### ✅ **KEEP** - test_optimizer_feasibility.py
**Verdict**: Keep all tests, ensure marked @pytest.mark.slow

**Rationale**:
- Uses real Fireroad data to test common scenarios
- Smoke tests for feasibility (GIRs only, pinned courses, ASE credit, override markers)
- Already uses @pytest.fixture for caching API calls

**Recommendation**: Mark all tests with `@pytest.mark.slow` - these shouldn't run on every commit

**Value**: Medium - good smoke tests but slow

---

### ✅ **KEEP** - test_full_optimizer_e2e.py
**Verdict**: Keep all tests, mark @pytest.mark.e2e and @pytest.mark.slow

**Rationale**:
- Tests actual degree combinations with real requirements (Course 6-3, 18, 2, 7, etc.)
- `test_course_2_with_2_013_prerequisites` - validates the actual 2.013 bug fix
- Verifies prerequisites are satisfied in correct order
- Catches infeasibility issues that unit tests cannot detect

**Recommendation**: Consider parameterizing common majors instead of individual test functions

**Value**: Critical - end-to-end validation that degrees remain feasible

---

### ✅ **KEEP** - test_category_rewards.py
**Verdict**: Keep all tests unchanged

**Rationale**:
- Well-designed unit tests for geometric decay rewards
- Tests behavior, not implementation
- Good isolation and edge case coverage (tier 0, missing mappings, decay rates)

**Value**: High - good example of how unit tests should work

---

### ✅ **KEEP** - test_requirement_constraint_builder.py
**Verdict**: Keep all tests unchanged

**Rationale**:
- Comprehensive coverage of requirement types (courses, GIRs, HASS, CI, plain-string)
- Tests pruned requirement handling (important for validation)
- Tests enforcement and threshold logic
- Tests edge cases (all children pruned, infeasible thresholds)

**Value**: High - validates complex constraint builder logic

---

### ⚠️ **REVISE** - test_prerequisites_parser.py
**Verdict**: Remove trivial tests, keep regression and real-world tests

**Remove (too trivial, don't catch bugs)**:
- `test_simple_course` - trivial
- `test_and_prerequisites` - trivial
- `test_or_prerequisites` - trivial
- `test_gir_requirements` - covered by property tests
- All tests in `TestCourseIDValidation` - these are unit tests for a helper function

**Keep (valuable regression tests)**:
- All of `TestRegressionFireroadBugs` - caught 12 real bugs
- All of `TestRealWorldExamples` - uses actual Fireroad data
- `test_complex_nested` - tests parser edge cases
- `test_filter_permission_text` - validates junk filtering

**Rationale**: Focus on tests that catch real bugs, not tests of trivial functionality

**Lines to remove**: ~150 lines of trivial tests

---

### ⚠️ **REVISE** - test_prerequisites_constraint_builder.py
**Verdict**: Major revision - remove fake data tests, keep regression tests

**Remove (use fake data, don't test real prerequisites)**:
- `test_simple_course_prereq`
- `test_gir_prereq`
- `test_hass_prereq`
- `test_and_prereq`
- `test_or_prereq`
- `test_2013_complex_and_group_prerequisites` (superseded by E2E tests)

**Keep (critical regression tests)**:
- `test_missing_course_returns_unsatisfied` - core bug fix
- `test_missing_course_in_or_group_forces_alternative` - 2.013 bug regression test
- `test_all_missing_in_or_group_makes_untakeable` - edge case validation
- `test_missing_in_and_group_makes_untakeable` - edge case validation
- All ASE and Must Take tests - real production features
- `test_override_courses_skip_prereq_constraints`

**Rationale**: As the postmortem notes, tests with fake data don't catch real bugs. Focus on edge cases and regression tests.

**Lines to remove**: ~200 lines of low-value tests

---

## New Tests Needed

### 🆕 **test_marker_constraints_comprehensive.py**
**Status**: NEW FILE NEEDED

**What to test**:
1. **Pin marker**:
   - Correctly forces course to specific semester
   - Works with ASE (-1) and Must Take (-2) semesters
   - Multiple pins in same semester are allowed

2. **Override marker**:
   - Skips prerequisite checking
   - Still pins to semester
   - Does NOT block other courses in same semester (regression)

3. **Banish marker**:
   - Prevents course in specific semester only
   - Course can still be placed elsewhere
   - Multiple banish markers for same course work

4. **Edge cases**:
   - Conflicting markers (pin + banish same course/semester)
   - Marker for non-existent course
   - Multiple markers on same course
   - Markers in past semesters (with lock_past_semesters)

**Test strategy**: E2E with real optimizer, property-based for edge cases

---

### 🆕 **test_category_weighting_e2e.py**
**Status**: NEW FILE NEEDED

**What to test**:
1. **Weighted subcategories**:
   - Courses in higher-tier categories are preferred
   - Diminishing returns work correctly (geometric decay)
   - Multiple subcategories with different tiers

2. **course_to_requirements mapping**:
   - Courses correctly mapped to requirement paths
   - Nested requirements tracked properly
   - Course in multiple categories gets rewards from both

3. **Tier inference**:
   - Stars (★★★) correctly converted to tiers
   - Tier 0 (no stars) gets no reward
   - Nested starred categories inherit correctly

4. **Integration with optimizer**:
   - Optimizer actually prefers higher-tier courses
   - Rewards don't override hard constraints
   - Works with multiple requirements simultaneously

**Test strategy**: E2E tests with crafted requirements, verify solutions prefer starred categories

---

### 🆕 **test_basic_constraints_property.py**
**Status**: NEW FILE NEEDED

**What to test**:
Property-based tests for basic constraints:

1. **At most once constraint**:
   - Property: Sum of take_vars for any course ≤ 1
   - Includes ASE and Must Take semesters
   - Test with random semester ranges

2. **Semester capacity**:
   - Property: Sum of courses in any semester ≤ max_courses
   - Test with various max_courses values
   - Include unit limits if enabled

3. **Fall/Spring/IAP offerings**:
   - Property: Courses only placed in semesters they're offered
   - Generate random offering patterns
   - Test edge cases (IAP-only, Fall-only)

4. **Lock past semesters**:
   - Property: No courses placed in semesters < current
   - Exception: pinned courses are allowed
   - Test with various current semester values

**Test strategy**: Hypothesis property tests with random course catalogs

---

### 🆕 **test_optimizer_e2e_comprehensive.py**
**Status**: File exists but needs expansion

**Currently in test_optimizer_e2e_comprehensive.py**:
- Basic degree feasibility tests

**Add tests for**:
1. **Constraint combinations**:
   - Markers + prerequisites + requirements together
   - Lock past semesters + ASE courses + requirements
   - Override markers + category rewards + unit limits

2. **Schedule quality validation**:
   - Verify prerequisites satisfied in correct order
   - Verify no course appears twice
   - Verify all semesters respect capacity
   - Verify all requirements actually satisfied

3. **Realistic scenarios**:
   - Student transfers in (some courses in past)
   - Student with ASE credit + override for one course
   - Double major with starred subcategories
   - Course not offered in needed semester

4. **Infeasibility detection**:
   - Detect when requirements are truly impossible
   - Provide useful error messages
   - Handle missing courses gracefully

**Test strategy**: Parameterized tests with realistic scenarios, validate solution quality

---

## Test Organization Recommendations

### Mark test categories clearly:
```python
@pytest.mark.unit
def test_parser_simple_course():
    pass

@pytest.mark.integration
def test_constraint_builder_with_real_data():
    pass

@pytest.mark.e2e
@pytest.mark.slow
def test_course_6_3_feasible():
    pass

@pytest.mark.property
def test_parser_never_returns_empty_groups():
    pass
```

### Run different test suites:
```bash
# Fast tests only (unit + property)
pytest -m "unit or property"

# Integration tests
pytest -m integration

# Full suite (includes E2E)
pytest

# Only E2E
pytest -m e2e
```

---

## Priority Order for Implementation

1. **HIGH**: Add `test_marker_constraints_comprehensive.py` - markers are core feature, recently had bugs
2. **HIGH**: Expand `test_optimizer_e2e_comprehensive.py` - validates real scenarios
3. **MEDIUM**: Add `test_category_weighting_e2e.py` - validates new feature, prevents regressions
4. **MEDIUM**: Clean up `test_prerequisites_constraint_builder.py` - remove low-value tests
5. **LOW**: Add `test_basic_constraints_property.py` - basic constraints rarely break
6. **LOW**: Clean up `test_prerequisites_parser.py` - remove trivial tests

---

## Key Lessons from Postmortem

1. **Fuzz tests catch real bugs** - `test_fuzzers.py` found 12 parser bugs
2. **Property tests enforce invariants** - "never return empty groups" caught the core bug
3. **E2E tests validate real scenarios** - unit tests with fake data don't catch integration issues
4. **Test constraint behavior, not structure** - verify courses are actually untakeable, not just that constraints exist
5. **Use real data** - tests with Course 6-3, Course 7, etc. catch issues that "TestCourse1, TestCourse2" don't

---

## Summary Statistics

**Current tests**:
- Keep unchanged: 6 files (~2000 lines)
- Revise: 2 files (~350 lines to remove)
- Result: ~1650 lines of high-value tests

**New tests to add**:
- 3 new comprehensive test files (~800 lines total)
- Expansions to existing files (~300 lines)

**Final coverage**:
- ~2750 lines of tests
- Focus on regression prevention and real-world scenarios
- Better balance of unit/property/integration/e2e tests
