"""
Unit tests for prerequisites validator.
"""

import polars as pl  # type: ignore[import-untyped]
import pytest

from courses.prerequisites.types import PrereqCourse, PrereqGroup
from courses.prerequisites.validator import (
    mark_invalid_prerequisites,
    remove_invalid_prerequisites,
)
from courses.prerequisites.validator import (
    validate_and_prune as prereq_validate_and_prune,
)
from courses.prerequisites.validator import (
    validate_course_exists as prereq_validate_course_exists,
)


@pytest.fixture
def valid_courses_df():
    """Create a DataFrame with valid courses."""
    return pl.DataFrame({
        'subject_id': ['6.100A', '6.1200', '6.1010', '6.1020', '18.01', '18.02']
    })


class TestCourseValidation:
    """Tests for validate_course_exists."""

    def test_valid_course(self, valid_courses_df):
        """Test that valid courses return True."""
        assert prereq_validate_course_exists('6.100A', valid_courses_df)

    def test_invalid_course(self, valid_courses_df):
        """Test that invalid courses return False."""
        assert not prereq_validate_course_exists('INVALID.COURSE', valid_courses_df)

    def test_gir_always_valid(self, valid_courses_df):
        """Test that GIR requirements are always valid."""
        assert prereq_validate_course_exists('GIR:CAL1', valid_courses_df)

    def test_hass_always_valid(self, valid_courses_df):
        """Test that HASS requirements are always valid."""
        assert prereq_validate_course_exists('HASS', valid_courses_df)


class TestMarkInvalidPrerequisites:
    """Tests for mark_invalid_prerequisites."""

    def test_valid_course_not_pruned(self, valid_courses_df):
        """Test that valid courses are not pruned."""
        prereq = PrereqCourse(course_id='6.100A')
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert not result.was_pruned
        assert isinstance(result, PrereqCourse)
        assert result.course_id == '6.100A'

    def test_invalid_course_pruned(self, valid_courses_df):
        """Test that invalid courses are pruned."""
        prereq = PrereqCourse(course_id='INVALID.COURSE')
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert result.was_pruned
        assert isinstance(result, PrereqCourse)
        assert result.course_id == 'INVALID.COURSE'

    def test_and_group_with_all_valid(self, valid_courses_df):
        """Test AND group with all valid children."""
        prereq = PrereqGroup(
            threshold=2,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='6.1200'),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert not result.was_pruned

    def test_and_group_with_one_invalid(self, valid_courses_df):
        """Test AND group with one invalid child."""
        prereq = PrereqGroup(
            threshold=2,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert result.was_pruned

    def test_or_group_with_one_valid(self, valid_courses_df):
        """Test OR group with one valid child."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert not result.was_pruned

    def test_or_group_with_all_invalid(self, valid_courses_df):
        """Test OR group with all invalid children."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='INVALID.A'),
                PrereqCourse(course_id='INVALID.B'),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert result.was_pruned

    def test_threshold_group_met(self, valid_courses_df):
        """Test threshold group when threshold is met."""
        prereq = PrereqGroup(
            threshold=2,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='6.1200'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert not result.was_pruned

    def test_threshold_group_not_met(self, valid_courses_df):
        """Test threshold group when threshold is not met."""
        prereq = PrereqGroup(
            threshold=2,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.A'),
                PrereqCourse(course_id='INVALID.B'),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert result.was_pruned

    def test_nested_groups(self, valid_courses_df):
        """Test nested groups with mixed validity."""
        prereq = PrereqGroup(
            threshold=2,
            items=(
                PrereqGroup(
                    threshold=1,
                    items=(
                        PrereqCourse(course_id='6.100A'),
                        PrereqCourse(course_id='INVALID.A'),
                    )
                ),
                PrereqGroup(
                    threshold=1,
                    items=(
                        PrereqCourse(course_id='6.1200'),
                        PrereqCourse(course_id='INVALID.B'),
                    )
                ),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert not result.was_pruned
        assert isinstance(result, PrereqGroup)
        assert not result.items[0].was_pruned
        assert not result.items[1].was_pruned


class TestRemoveInvalidPrerequisites:
    """Tests for remove_invalid_prerequisites."""

    def test_valid_course_kept(self, valid_courses_df):
        """Test that valid courses are kept."""
        prereq = PrereqCourse(course_id='6.100A')
        result = remove_invalid_prerequisites(prereq, valid_courses_df)

        assert result is not None
        assert isinstance(result, PrereqCourse)
        assert result.course_id == '6.100A'

    def test_invalid_course_removed(self, valid_courses_df):
        """Test that invalid courses are removed."""
        prereq = PrereqCourse(course_id='INVALID.COURSE')
        result = remove_invalid_prerequisites(prereq, valid_courses_df)

        assert result is None

    def test_group_with_invalid_children_removed(self, valid_courses_df):
        """Test that group removes invalid children."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
                PrereqCourse(course_id='6.1200'),
            )
        )
        result = remove_invalid_prerequisites(prereq, valid_courses_df)

        assert result is not None
        assert isinstance(result, PrereqGroup)
        assert len(result.items) == 2
        assert all(isinstance(item, PrereqCourse) and item.course_id in ['6.100A', '6.1200'] for item in result.items)

    def test_single_item_group_simplified(self, valid_courses_df):
        """Test that single-item groups are simplified."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = remove_invalid_prerequisites(prereq, valid_courses_df)

        assert isinstance(result, PrereqCourse)
        assert result.course_id == '6.100A'

    def test_and_group_infeasible_when_child_removed(self, valid_courses_df):
        """Test that AND group becomes infeasible when a child is removed."""
        prereq = PrereqGroup(
            threshold=2,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = remove_invalid_prerequisites(prereq, valid_courses_df)

        assert result is None

    def test_threshold_becomes_infeasible(self, valid_courses_df):
        """Test that threshold group becomes infeasible."""
        prereq = PrereqGroup(
            threshold=2,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.A'),
                PrereqCourse(course_id='INVALID.B'),
            )
        )
        result = remove_invalid_prerequisites(prereq, valid_courses_df)

        assert result is None


class TestValidateAndPrune:
    """Tests for prereq_validate_and_prune function."""

    def test_mark_mode(self, valid_courses_df):
        """Test prereq_validate_and_prune in mark mode."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = prereq_validate_and_prune(prereq, valid_courses_df, remove_invalid=False)

        assert result.is_feasible
        assert result.pruned_tree is not None
        assert len(result.removed_courses) == 1
        assert 'INVALID.COURSE' in result.removed_courses
        assert len(result.warnings) > 0

    def test_remove_mode(self, valid_courses_df):
        """Test prereq_validate_and_prune in remove mode."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = prereq_validate_and_prune(prereq, valid_courses_df, remove_invalid=True)

        assert result.is_feasible
        assert result.pruned_tree is not None
        assert len(result.removed_courses) == 1

    def test_infeasible_result(self, valid_courses_df):
        """Test prereq_validate_and_prune with infeasible prerequisite."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='INVALID.A'),
                PrereqCourse(course_id='INVALID.B'),
            )
        )
        result = prereq_validate_and_prune(prereq, valid_courses_df, remove_invalid=True)

        assert not result.is_feasible
        assert result.pruned_tree is None
        assert len(result.removed_courses) == 2


class TestThresholdSemantics:
    """Tests confirming threshold semantics for prerequisites."""

    def test_threshold_zero_means_all(self):
        """Test that threshold=0 is converted to all items."""
        prereq = PrereqGroup(
            threshold=0,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='6.1200'),
            )
        )

        assert prereq.threshold == 2

    def test_threshold_one_means_or(self, valid_courses_df):
        """Test that threshold=1 means OR semantics."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert not result.was_pruned

    def test_threshold_two_of_three(self, valid_courses_df):
        """Test 2-of-3 threshold."""
        prereq = PrereqGroup(
            threshold=2,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='6.1200'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        result = mark_invalid_prerequisites(prereq, valid_courses_df)

        assert not result.was_pruned


class TestWarningsAndMetadata:
    """Tests for validation warnings and metadata."""

    def test_removed_courses_tracked(self, valid_courses_df):
        """Test that removed courses are tracked."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.A'),
                PrereqCourse(course_id='INVALID.B'),
            )
        )
        removed_courses: list[str] = []
        mark_invalid_prerequisites(prereq, valid_courses_df, removed_courses)

        assert len(removed_courses) == 2
        assert 'INVALID.A' in removed_courses
        assert 'INVALID.B' in removed_courses

    def test_warnings_generated(self, valid_courses_df):
        """Test that warnings are generated."""
        prereq = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse(course_id='6.100A'),
                PrereqCourse(course_id='INVALID.COURSE'),
            )
        )
        warnings: list[str] = []
        mark_invalid_prerequisites(prereq, valid_courses_df, warnings=warnings)

        assert len(warnings) > 0
        assert any('INVALID.COURSE' in w for w in warnings)
