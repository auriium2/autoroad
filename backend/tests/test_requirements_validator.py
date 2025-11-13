"""
Unit tests for requirements validator.
"""

import pandas as pd  # type: ignore[import-untyped]
import pytest

from courses import (
    RequirementCourse,
    RequirementGroup,
    RequirementPlainString,
    RequirementThreshold,
    mark_invalid_requirements,
    remove_invalid_requirements,
    validate_and_prune,
    validate_course_exists,
)


@pytest.fixture
def valid_courses_df():
    """Create a DataFrame with valid courses."""
    return pd.DataFrame({
        'subject_id': ['6.100A', '6.1200', '6.1010', '6.1020', '18.01', '18.02']
    })


class TestCourseValidation:
    """Tests for validate_course_exists."""

    def test_valid_course(self, valid_courses_df):
        """Test that valid courses return True."""
        assert validate_course_exists('6.100A', valid_courses_df) == True

    def test_invalid_course(self, valid_courses_df):
        """Test that invalid courses return False."""
        assert validate_course_exists('INVALID.COURSE', valid_courses_df) == False

    def test_gir_always_valid(self, valid_courses_df):
        """Test that GIR requirements are always valid."""
        assert validate_course_exists('GIR:CAL1', valid_courses_df) == True
        assert validate_course_exists('GIR:PHY1', valid_courses_df) == True

    def test_hass_always_valid(self, valid_courses_df):
        """Test that HASS requirements are always valid."""
        assert validate_course_exists('HASS', valid_courses_df) == True
        assert validate_course_exists('HASS-A', valid_courses_df) == True
        assert validate_course_exists('HASS-H', valid_courses_df) == True

    def test_ci_always_valid(self, valid_courses_df):
        """Test that CI requirements are always valid."""
        assert validate_course_exists('CI-H', valid_courses_df) == True
        assert validate_course_exists('CI-HW', valid_courses_df) == True


class TestMarkInvalidRequirements:
    """Tests for mark_invalid_requirements."""

    def test_valid_course_not_pruned(self, valid_courses_df):
        """Test that valid courses are not pruned."""
        req = RequirementCourse(course_id='6.100A', req_id='test')
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == False
        assert isinstance(result, RequirementCourse)
        assert result.course_id == '6.100A'

    def test_invalid_course_pruned(self, valid_courses_df):
        """Test that invalid courses are pruned."""
        req = RequirementCourse(course_id='INVALID.COURSE', req_id='test')
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == True
        assert isinstance(result, RequirementCourse)
        assert result.course_id == 'INVALID.COURSE'

    def test_plain_string_never_pruned(self, valid_courses_df):
        """Test that plain strings are never pruned."""
        req = RequirementPlainString(description='Some text', req_id='test')
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == False

    def test_all_group_with_all_valid(self, valid_courses_df):
        """Test 'all' group with all valid children."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='6.1200', req_id='b'),
            ),
            connection_type='all',
            req_id='test'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == False

    def test_all_group_with_one_invalid(self, valid_courses_df):
        """Test 'all' group with one invalid child."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='b'),
            ),
            connection_type='all',
            req_id='test'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == True

    def test_any_group_with_one_valid(self, valid_courses_df):
        """Test 'any' group with one valid child."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='b'),
            ),
            connection_type='any',
            req_id='test'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == False

    def test_any_group_with_all_invalid(self, valid_courses_df):
        """Test 'any' group with all invalid children."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='INVALID.A', req_id='a'),
                RequirementCourse(course_id='INVALID.B', req_id='b'),
            ),
            connection_type='any',
            req_id='test'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == True

    def test_threshold_subjects_met(self, valid_courses_df):
        """Test threshold with criterion='subjects' when met."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='6.1200', req_id='b'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='c'),
            ),
            threshold=RequirementThreshold(cutoff=2, criterion='subjects', type='GTE'),
            req_id='test'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == False

    def test_threshold_subjects_not_met(self, valid_courses_df):
        """Test threshold with criterion='subjects' when not met."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.A', req_id='b'),
                RequirementCourse(course_id='INVALID.B', req_id='c'),
            ),
            threshold=RequirementThreshold(cutoff=2, criterion='subjects', type='GTE'),
            req_id='test'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == True

    def test_nested_groups(self, valid_courses_df):
        """Test nested groups with mixed validity."""
        req = RequirementGroup(
            items=(
                RequirementGroup(
                    items=(
                        RequirementCourse(course_id='6.100A', req_id='g1a'),
                        RequirementCourse(course_id='INVALID.A', req_id='g1b'),
                    ),
                    connection_type='any',
                    req_id='g1'
                ),
                RequirementGroup(
                    items=(
                        RequirementCourse(course_id='6.1200', req_id='g2a'),
                        RequirementCourse(course_id='INVALID.B', req_id='g2b'),
                    ),
                    connection_type='any',
                    req_id='g2'
                ),
            ),
            connection_type='all',
            req_id='test'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == False
        assert isinstance(result, RequirementGroup)
        assert result.items[0].was_pruned == False
        assert result.items[1].was_pruned == False


class TestRemoveInvalidRequirements:
    """Tests for remove_invalid_requirements."""

    def test_valid_course_kept(self, valid_courses_df):
        """Test that valid courses are kept."""
        req = RequirementCourse(course_id='6.100A', req_id='test')
        result = remove_invalid_requirements(req, valid_courses_df)

        assert result is not None
        assert isinstance(result, RequirementCourse)
        assert result.course_id == '6.100A'

    def test_invalid_course_removed(self, valid_courses_df):
        """Test that invalid courses are removed."""
        req = RequirementCourse(course_id='INVALID.COURSE', req_id='test')
        result = remove_invalid_requirements(req, valid_courses_df)

        assert result is None

    def test_group_with_invalid_children_removed(self, valid_courses_df):
        """Test that group removes invalid children."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='b'),
                RequirementCourse(course_id='6.1200', req_id='c'),
            ),
            connection_type='any',
            req_id='test'
        )
        result = remove_invalid_requirements(req, valid_courses_df)

        assert result is not None
        assert isinstance(result, RequirementGroup)
        assert len(result.items) == 2
        assert all(isinstance(item, RequirementCourse) and item.course_id in ['6.100A', '6.1200'] for item in result.items)

    def test_single_item_group_simplified(self, valid_courses_df):
        """Test that single-item groups are simplified."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='b'),
            ),
            connection_type='any',
            req_id='test'
        )
        result = remove_invalid_requirements(req, valid_courses_df)

        assert isinstance(result, RequirementCourse)
        assert result.course_id == '6.100A'

    def test_all_group_becomes_single_course_when_simplified(self, valid_courses_df):
        """Test that 'all' group is simplified to single course when one child is removed."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='b'),
            ),
            connection_type='all',
            req_id='test'
        )
        result = remove_invalid_requirements(req, valid_courses_df)

        # When an 'all' group has one child removed, it simplifies to a single course
        # because a single-item group is automatically simplified
        assert isinstance(result, RequirementCourse)
        assert result.course_id == '6.100A'

    def test_all_group_with_threshold_infeasible(self, valid_courses_df):
        """Test that 'all' group with threshold becomes infeasible properly."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='b'),
            ),
            connection_type='all',
            threshold=RequirementThreshold(cutoff=2, criterion='subjects', type='GTE'),
            req_id='test'
        )
        result = remove_invalid_requirements(req, valid_courses_df)

        # With threshold requiring 2 subjects but only 1 valid, should be infeasible
        assert result is None

    def test_threshold_becomes_infeasible(self, valid_courses_df):
        """Test that threshold group becomes infeasible."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.A', req_id='b'),
                RequirementCourse(course_id='INVALID.B', req_id='c'),
            ),
            threshold=RequirementThreshold(cutoff=2, criterion='subjects', type='GTE'),
            req_id='test'
        )
        result = remove_invalid_requirements(req, valid_courses_df)

        assert result is None


class TestValidateAndPrune:
    """Tests for validate_and_prune function."""

    def test_mark_mode(self, valid_courses_df):
        """Test validate_and_prune in mark mode."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='b'),
            ),
            connection_type='any',
            req_id='test'
        )
        result = validate_and_prune(req, valid_courses_df, remove_invalid=False)

        assert result.is_feasible == True
        assert result.pruned_tree is not None
        assert len(result.removed_courses) == 1
        assert 'INVALID.COURSE' in result.removed_courses
        assert len(result.warnings) > 0

    def test_remove_mode(self, valid_courses_df):
        """Test validate_and_prune in remove mode."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='6.100A', req_id='a'),
                RequirementCourse(course_id='INVALID.COURSE', req_id='b'),
            ),
            connection_type='any',
            req_id='test'
        )
        result = validate_and_prune(req, valid_courses_df, remove_invalid=True)

        assert result.is_feasible == True
        assert result.pruned_tree is not None
        assert len(result.removed_courses) == 1

    def test_infeasible_result(self, valid_courses_df):
        """Test validate_and_prune with infeasible requirement."""
        req = RequirementGroup(
            items=(
                RequirementCourse(course_id='INVALID.A', req_id='a'),
                RequirementCourse(course_id='INVALID.B', req_id='b'),
            ),
            connection_type='any',
            req_id='test'
        )
        result = validate_and_prune(req, valid_courses_df, remove_invalid=True)

        assert result.is_feasible == False
        assert result.pruned_tree is None
        assert len(result.removed_courses) == 2


class TestConnectionTypeSemantics:
    """Tests confirming connection-type semantics."""

    def test_all_applies_to_direct_children(self, valid_courses_df):
        """Test that 'all' applies to direct children, not leaf courses."""
        req = RequirementGroup(
            items=(
                RequirementGroup(
                    items=(
                        RequirementCourse(course_id='6.100A', req_id='g1a'),
                        RequirementCourse(course_id='INVALID.A', req_id='g1b'),
                    ),
                    connection_type='any',
                    req_id='g1'
                ),
                RequirementGroup(
                    items=(
                        RequirementCourse(course_id='6.1200', req_id='g2a'),
                        RequirementCourse(course_id='INVALID.B', req_id='g2b'),
                    ),
                    connection_type='any',
                    req_id='g2'
                ),
            ),
            connection_type='all',
            req_id='parent'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == False

    def test_threshold_subjects_counts_all_descendants(self, valid_courses_df):
        """Test that threshold with criterion='subjects' counts all descendants."""
        req = RequirementGroup(
            items=(
                RequirementGroup(
                    items=(
                        RequirementCourse(course_id='6.100A', req_id='g1a'),
                        RequirementCourse(course_id='6.1200', req_id='g1b'),
                    ),
                    connection_type='any',
                    req_id='g1'
                ),
                RequirementGroup(
                    items=(
                        RequirementCourse(course_id='6.1010', req_id='g2a'),
                        RequirementCourse(course_id='INVALID.A', req_id='g2b'),
                    ),
                    connection_type='any',
                    req_id='g2'
                ),
            ),
            threshold=RequirementThreshold(cutoff=3, criterion='subjects', type='GTE'),
            req_id='parent'
        )
        result = mark_invalid_requirements(req, valid_courses_df)

        assert result.was_pruned == False
