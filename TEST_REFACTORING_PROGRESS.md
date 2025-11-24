# Test Suite Refactoring Progress

Following the prerequisite parser bug postmortem recommendations.

## Completed ✅

### 1. Extracted Basic Constraints to New Module
**File**: `backend/optimizer/constraints/basic.py`

Moved from `api/routes/optimize.py`:
- `create_take_vars()` - Creates decision variables for course scheduling
- `add_at_most_once_constraint()` - Course can only be taken once
- `add_freshman_fall_limit()` - 48 unit limit for first semester
- `add_iap_limits()` - 12 unit limit for IAP semesters
- `add_basic_constraints()` - Convenience function for all basic constraints
- `add_past_semester_constraints()` - Prevents scheduling in past semesters

**Benefits**:
- Better separation of concerns (constraints vs API endpoint logic)
- Easier to test constraints in isolation
- Clearer module organization
- Updated all imports across 5 files:
  - `api/routes/optimize.py`
  - `tests/test_optimizer_integration.py`
  - `tests/test_optimizer_e2e_comprehensive.py`
  - `tests/test_full_optimizer_e2e.py`
  - `test_enforce_check.py`
  - `test_debug_optimizer.py`

### 2. Revised test_prerequisites_parser.py
**Removed**: ~150 lines of trivial tests
**Kept**: 12 regression tests

**Tests Removed**:
- `TestCourseIDValidation` - trivial validation tests
- `TestTokenizer` - trivial tokenization tests
- `TestFilterJunkTokens` - trivial filtering tests
- `TestPrereqToString` - trivial string conversion tests
- Trivial tests in `TestFireroadParser` (simple_course, and_prerequisites, or_prerequisites, etc.)

**Tests Kept**:
- `test_complex_nested` - Real nested structure from production
- `test_filter_permission_text` - Real edge case
- `TestRealWorldExamples` - All tests with actual Fireroad data
- `TestRegressionFireroadBugs` - All 12 regression tests for parser bugs

**Result**: Focused test suite with only valuable regression tests. Trivial functionality covered by property-based tests.

### 3. Revised test_prerequisites_constraint_builder.py
**Removed**: ~210 lines of fake data tests
**Kept**: 19 regression tests

**Tests Removed**:
- `test_simple_course_prereq` - trivial test with fake data
- `test_gir_prereq` - trivial test with fake data
- `test_hass_prereq` - trivial test with fake data
- `test_and_prereq` - trivial test with fake data
- `test_or_prereq` - trivial test with fake data
- `test_add_prerequisite_constraints` - trivial convenience function test
- `test_2013_complex_and_group_prerequisites` - superseded by E2E tests with real data
- `test_2013_with_satisfied_prerequisites` - superseded by E2E tests with real data

**Tests Kept**:
- `TestCourseSchedule` - Helper class validation (3 tests)
- `TestMissingCourseHandling` - Core bug fix test (1 test)
- `TestASEAndMustTake` - Real production features (5 tests)
- `TestComplexPrerequisites` - Critical regression tests for 2.013 bug (5 tests)
  - `test_missing_course_returns_unsatisfied` - Core bug fix
  - `test_missing_course_in_or_group_forces_alternative` - 2.013 bug scenario
  - `test_all_missing_in_or_group_makes_untakeable` - Edge case
  - `test_missing_in_and_group_makes_untakeable` - Edge case
  - `test_2013_bug_full_integration` - Full integration test with real Fireroad data

**Result**: Focused on edge cases and real bugs. Tests now validate actual constraint behavior, not just that constraints exist.

---

## Next Steps (Remaining)

### 4. Create test_marker_constraints_e2e.py
Test all marker types with real optimizer:
- Pin markers (regular, ASE, Must Take)
- Override markers (skip prereqs, don't block other courses)
- Banish markers (prevent specific semester only)
- Edge cases (conflicting markers, non-existent courses)

### 5. Create test_marker_constraints_property.py
Property-based tests for markers:
- Markers never violate basic constraints
- Pin markers always place in specified semester
- Override markers always skip prereqs
- Banish markers never appear in banned semester

### 6. Create test_category_weighting_e2e.py
Test category rewards/weighting:
- Weighted subcategories and tier preferences
- Diminishing returns (geometric decay)
- Integration with optimizer (verify it prefers starred categories)
- course_to_requirements mapping correctness

### 7. Create test_basic_constraints_property.py
Property-based tests for basic constraints:
- At most once constraint (including ASE/Must Take)
- Semester capacity limits
- Fall/Spring/IAP offering constraints
- Lock past semesters logic

---

## Summary Statistics

### Before Refactoring:
- `test_prerequisites_parser.py`: ~400 lines, many trivial tests
- `test_prerequisites_constraint_builder.py`: ~740 lines, many fake data tests
- Basic constraints: Mixed into API endpoint (no tests)

### After Refactoring:
- `test_prerequisites_parser.py`: ~250 lines, focused regression tests (12 tests)
- `test_prerequisites_constraint_builder.py`: ~530 lines, edge case tests (19 tests)
- `optimizer/constraints/basic.py`: ~310 lines, well-documented constraint builders
- Improved test quality: Focus on real bugs, not trivial functionality

### Lines Removed:
- Trivial tests: ~360 lines
- Result: Cleaner, more maintainable test suite that focuses on catching real bugs

### Test Results:
- `test_prerequisites_parser.py`: ✅ 12 passed
- `test_prerequisites_constraint_builder.py`: ✅ 19 passed
- `test_optimizer_integration.py`: ✅ 15 passed
- All imports updated successfully

---

## Key Improvements

1. **Better Organization**: Basic constraints extracted to dedicated module
2. **Focused Tests**: Removed trivial tests, kept regression and edge case tests
3. **Real Data**: Tests now use actual Fireroad data or validate real production bugs
4. **Clear Documentation**: Each test explains why it exists and what bug it prevents
5. **Maintainability**: Easier to understand what each test validates

---

## Lessons Applied from Postmortem

✅ **Remove tests with fake data** - They don't catch real bugs  
✅ **Focus on regression tests** - Tests should prevent known bugs from recurring  
✅ **Test behavior, not structure** - Verify courses are untakeable, not just that constraints exist  
✅ **Use real examples** - Real course data catches integration issues  
✅ **Property-based tests** - Already have good coverage in `test_prerequisites_parser_property.py`

---

## Next Session Plan

1. Create marker E2E and property tests (high priority - markers had recent bugs)
2. Create category weighting E2E tests (validates new feature)
3. Create basic constraints property tests (lower priority - rarely break)
4. Consider expanding `test_optimizer_e2e_comprehensive.py` with more realistic scenarios
