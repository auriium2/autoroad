"""
Solution quality tests for the optimizer.

These tests verify that the optimizer produces high-quality, realistic schedules.
They check not just feasibility but also:
- Reasonable course counts
- Prerequisites satisfied
- Good distribution across semesters
- No violations

Separate from test_full_optimizer_e2e.py which focuses on feasibility/regression.
"""

import pytest

from tests.test_helpers import run_optimizer_quality_test


@pytest.mark.e2e
@pytest.mark.slow
class TestOptimizerQuality:
    """Quality tests for optimizer solutions."""

    def test_course_6_9_quality(self, optimizer_config):
        """Test Course 6-9 (Computation and Cognition) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major6-9', 'girs'),
            degree_id='major6-9',
            optimizer_config=optimizer_config
        )

    def test_course_6_3_new_quality(self, optimizer_config):
        """Test Course 6-3 (Computer Science) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major6-3new', 'girs'),
            degree_id='major6-3new',
            optimizer_config=optimizer_config
        )

    def test_course_18pm_quality(self, optimizer_config):
        """Test Course 18 (Pure Mathematics) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major18pm', 'girs'),
            degree_id='major18',
            optimizer_config=optimizer_config
        )

    def test_course_9_quality(self, optimizer_config):
        """Test Course 9 (Brain and Cognitive Sciences) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major9', 'girs'),
            degree_id='major9',
            optimizer_config=optimizer_config
        )

    def test_course_20_quality(self, optimizer_config):
        """Test Course 20 (Biological Engineering) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major20', 'girs'),
            degree_id='major20',
            optimizer_config=optimizer_config
        )

    def test_course_6_2_quality(self, optimizer_config):
        """Test Course 6-2 (EECS) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major6-2new', 'girs'),
            degree_id='major6-2',
            optimizer_config=optimizer_config
        )

    def test_course_1_quality(self, optimizer_config):
        """Test Course 1 (Civil Engineering) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major1', 'girs'),
            degree_id='major1',
            optimizer_config=optimizer_config
        )

    def test_course_7_quality(self, optimizer_config):
        """Test Course 7 (Biology) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major7', 'girs'),
            degree_id='major7',
            optimizer_config=optimizer_config
        )
