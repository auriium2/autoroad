"""
Unit tests for semester utility functions.
"""

from datetime import datetime
from unittest.mock import patch

from utils.utils import get_current_semester_index


class TestGetCurrentSemesterIndex:
    """Tests for get_current_semester_index function."""

    def test_freshman_fall_september(self):
        """Test that September of planning year start is semester 1 (Freshman Fall)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 1

    def test_freshman_iap_january(self):
        """Test that January is semester 2 (Freshman IAP)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 2

    def test_freshman_spring_march(self):
        """Test that March is semester 3 (Freshman Spring)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 3

    def test_sophomore_fall_september(self):
        """Test that September one year later is semester 4 (Sophomore Fall)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 9, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 4

    def test_sophomore_iap_january(self):
        """Test that January one year later is semester 5 (Sophomore IAP)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2027, 1, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 5

    def test_sophomore_spring_april(self):
        """Test that April one year later is semester 6 (Sophomore Spring)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2027, 4, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 6

    def test_junior_fall(self):
        """Test Junior Fall (semester 7)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2027, 9, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 7

    def test_junior_iap(self):
        """Test Junior IAP (semester 8)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2028, 1, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 8

    def test_junior_spring(self):
        """Test Junior Spring (semester 9)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2028, 5, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 9

    def test_senior_fall(self):
        """Test Senior Fall (semester 10)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2028, 10, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 10

    def test_senior_iap(self):
        """Test Senior IAP (semester 11)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2029, 1, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 11

    def test_senior_spring(self):
        """Test Senior Spring (semester 12)."""
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2029, 2, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 12

    def test_before_planning_year_returns_zero(self):
        """Test that dates before planning year start return 0."""
        with patch('utils.utils.datetime') as mock_datetime:
            # August 2024 is before planning year 2025-2026
            mock_datetime.now.return_value = datetime(2024, 8, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 0

    def test_after_graduation_returns_twelve(self):
        """Test that dates after graduation are clamped to 12."""
        with patch('utils.utils.datetime') as mock_datetime:
            # September 2029 is after graduation (May 2029)
            mock_datetime.now.return_value = datetime(2029, 9, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 12

    def test_august_before_fall_semester(self):
        """Test that August is still counted as Spring semester (Fall starts in September)."""
        with patch('utils.utils.datetime') as mock_datetime:
            # August 2026 is still Freshman Spring (summer before Sophomore Fall)
            mock_datetime.now.return_value = datetime(2026, 8, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            # August is before Fall semester starts (September)
            # Still counted as Freshman Spring (semester 3)
            assert result == 3

    def test_boundary_fall_starts_september(self):
        """Test that Fall semester starts in September (month 9)."""
        with patch('utils.utils.datetime') as mock_datetime:
            # September 1st should be Fall
            mock_datetime.now.return_value = datetime(2025, 9, 1)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 1  # Freshman Fall

    def test_boundary_iap_january_only(self):
        """Test that IAP is only in January (month 0)."""
        with patch('utils.utils.datetime') as mock_datetime:
            # January 31st should be IAP
            mock_datetime.now.return_value = datetime(2026, 1, 31)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 2  # Freshman IAP

    def test_boundary_spring_starts_february(self):
        """Test that Spring semester starts in February."""
        with patch('utils.utils.datetime') as mock_datetime:
            # February 1st should be Spring
            mock_datetime.now.return_value = datetime(2026, 2, 1)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 3  # Freshman Spring

    def test_summer_months_treated_as_spring(self):
        """Test that summer months (May, June, July) are treated as Spring semester."""
        planning_year_start = 2025

        # May (month 5)
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 5, 15)
            result = get_current_semester_index(planning_year_start)
            # May 2026 should still be Freshman Spring (semester 3)
            assert result == 3, f"May should be Spring semester, got {result}"

        # June (month 6)
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 6, 15)
            result = get_current_semester_index(planning_year_start)
            # June 2026 should still be Freshman Spring (semester 3)
            assert result == 3, f"June should be Spring semester, got {result}"

        # July (month 7)
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 7, 15)
            result = get_current_semester_index(planning_year_start)
            # July 2026 should still be Freshman Spring (semester 3)
            assert result == 3, f"July should be Spring semester, got {result}"

        # August (month 8)
        with patch('utils.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 8, 15)
            result = get_current_semester_index(planning_year_start)
            # August 2026 should still be Freshman Spring (semester 3)
            assert result == 3, f"August should be Spring semester, got {result}"

    def test_full_four_year_progression(self):
        """Test the complete progression through all 12 semesters."""
        planning_year_start = 2025

        test_cases = [
            (datetime(2025, 9, 15), 1),   # Freshman Fall
            (datetime(2026, 1, 15), 2),   # Freshman IAP
            (datetime(2026, 3, 15), 3),   # Freshman Spring
            (datetime(2026, 9, 15), 4),   # Sophomore Fall
            (datetime(2027, 1, 15), 5),   # Sophomore IAP
            (datetime(2027, 4, 15), 6),   # Sophomore Spring
            (datetime(2027, 9, 15), 7),   # Junior Fall
            (datetime(2028, 1, 15), 8),   # Junior IAP
            (datetime(2028, 5, 15), 9),   # Junior Spring
            (datetime(2028, 9, 15), 10),  # Senior Fall
            (datetime(2029, 1, 15), 11),  # Senior IAP
            (datetime(2029, 3, 15), 12),  # Senior Spring
        ]

        for test_date, expected_semester in test_cases:
            with patch('utils.utils.datetime') as mock_datetime:
                mock_datetime.now.return_value = test_date
                result = get_current_semester_index(planning_year_start)
                assert result == expected_semester, \
                    f"Date {test_date} should be semester {expected_semester}, got {result}"
