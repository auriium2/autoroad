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

    def test_course_2_quality(self, optimizer_config):
        """Test Course 2 (Mechanical Engineering) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major2', 'girs'),
            degree_id='major2',
            optimizer_config=optimizer_config
        )

    def test_course_15_quality(self, optimizer_config):
        """Test Course 15 (Management) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major15-1', 'girs'),
            degree_id='major15-1',
            optimizer_config=optimizer_config
        )

    def test_course_18c_quality(self, optimizer_config):
        """Test Course 18-C (Mathematics with Computer Science) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major18c', 'girs'),
            degree_id='major18c',
            optimizer_config=optimizer_config
        )

    def test_course_18am_quality(self, optimizer_config):
        """Test Course 18 (Applied Mathematics) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major18am', 'girs'),
            degree_id='major18am',
            optimizer_config=optimizer_config
        )

    def test_course_3_quality(self, optimizer_config):
        """Test Course 3 (Materials Science and Engineering) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major3', 'girs'),
            degree_id='major3',
            optimizer_config=optimizer_config
        )

    def test_course_3a_quality(self, optimizer_config):
        """Test Course 3-A (Materials Science Flexible) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major3a', 'girs'),
            degree_id='major3a',
            optimizer_config=optimizer_config
        )

    def test_course_3c_quality(self, optimizer_config):
        """Test Course 3-C (Archaeology and Materials) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major3c', 'girs'),
            degree_id='major3c',
            optimizer_config=optimizer_config
        )

    def test_course_4_quality(self, optimizer_config):
        """Test Course 4 (Architecture) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major4', 'girs'),
            degree_id='major4',
            optimizer_config=optimizer_config
        )

    def test_course_6_4_quality(self, optimizer_config):
        """Test Course 6-4 (AI and Decision Making) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major6-4', 'girs'),
            degree_id='major6-4',
            optimizer_config=optimizer_config
        )

    def test_course_6_5_quality(self, optimizer_config):
        """Test Course 6-5 (Computer Systems) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major6-5', 'girs'),
            degree_id='major6-5',
            optimizer_config=optimizer_config
        )

    def test_course_6_7_quality(self, optimizer_config):
        """Test Course 6-7 (Computer Science and Molecular Biology) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major6-7', 'girs'),
            degree_id='major6-7',
            optimizer_config=optimizer_config
        )

    def test_course_6_14_quality(self, optimizer_config):
        """Test Course 6-14 (CS, Economics, and Data Science) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major6-14', 'girs'),
            degree_id='major6-14',
            optimizer_config=optimizer_config
        )

    def test_course_8_quality(self, optimizer_config):
        """Test Course 8 (Physics) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major8', 'girs'),
            degree_id='major8',
            optimizer_config=optimizer_config
        )

    def test_course_11_quality(self, optimizer_config):
        """Test Course 11 (Urban Studies and Planning) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major11', 'girs'),
            degree_id='major11',
            optimizer_config=optimizer_config
        )

    def test_course_16_quality(self, optimizer_config):
        """Test Course 16 (Aerospace Engineering) produces quality solution."""
        run_optimizer_quality_test(
            requirement_keys=('major16', 'girs'),
            degree_id='major16',
            optimizer_config=optimizer_config
        )
