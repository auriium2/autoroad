"""
Unit tests for semester utility functions.
"""

from datetime import datetime
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from shared.utils import (
    get_current_semester_index,
    hydrant_code_to_semester_idx,
    semester_idx_to_hydrant_code,
)

# ============ Property-Based Tests for Semester Conversion ============

@given(
    semester_idx=st.integers(min_value=1, max_value=12),
    planning_year_start=st.integers(min_value=2020, max_value=2040),
)
@settings(max_examples=500)
def test_roundtrip_semester_idx_to_code_and_back(semester_idx: int, planning_year_start: int):
    """Converting semester_idx -> code -> semester_idx should return the original."""
    code = semester_idx_to_hydrant_code(semester_idx, planning_year_start)
    result = hydrant_code_to_semester_idx(code, planning_year_start)

    assert result == semester_idx, (
        f"Roundtrip failed: {semester_idx} -> {code} -> {result} "
        f"(planning_year_start={planning_year_start})"
    )


@given(
    semester_idx=st.integers(min_value=1, max_value=12),
    planning_year_start=st.integers(min_value=2020, max_value=2040),
)
@settings(max_examples=500)
def test_semester_idx_produces_valid_hydrant_code(semester_idx: int, planning_year_start: int):
    """semester_idx_to_hydrant_code should always produce a valid code."""
    code = semester_idx_to_hydrant_code(semester_idx, planning_year_start)

    assert len(code) == 3, f"Code should be 3 chars, got {code}"
    assert code[0] in ("f", "i", "s"), f"Invalid term in code: {code}"
    assert code[1:].isdigit(), f"Invalid year in code: {code}"


@given(
    semester_idx=st.integers(min_value=1, max_value=12),
    planning_year_start=st.integers(min_value=2020, max_value=2040),
)
@settings(max_examples=500)
def test_semester_idx_term_matches_position(semester_idx: int, planning_year_start: int):
    """Fall should be semesters 1,4,7,10; IAP 2,5,8,11; Spring 3,6,9,12."""
    code = semester_idx_to_hydrant_code(semester_idx, planning_year_start)
    term = code[0]

    expected_term_idx = (semester_idx - 1) % 3  # 0=Fall, 1=IAP, 2=Spring
    expected_term = ["f", "i", "s"][expected_term_idx]

    assert term == expected_term, (
        f"Semester {semester_idx} should be {expected_term}, got {term}"
    )


@given(
    planning_year_start=st.integers(min_value=2020, max_value=2040),
)
@settings(max_examples=100)
def test_semester_progression_is_monotonic(planning_year_start: int):
    """Semester codes should progress chronologically."""
    codes = [semester_idx_to_hydrant_code(i, planning_year_start) for i in range(1, 13)]

    # Extract (year, term_order) for comparison
    # Fall=0 (starts academic year), IAP=1, Spring=2
    term_order = {"f": 0, "i": 1, "s": 2}

    def to_sortable(code: str) -> tuple[int, int]:
        term = code[0]
        year = int(code[1:]) + 2000
        # For sorting: Fall X starts academic year, IAP/Spring X are in that same academic year
        if term == "f":
            academic_year = year
        else:  # IAP or Spring
            academic_year = year - 1  # They're in the academic year that started previous fall
        return (academic_year, term_order[term])

    sortable = [to_sortable(c) for c in codes]

    for i in range(len(sortable) - 1):
        assert sortable[i] <= sortable[i + 1], (
            f"Codes not monotonic: {codes[i]} >= {codes[i+1]} "
            f"(semesters {i+1} and {i+2})"
        )


# ============ Specific Scenario Tests for Semester Conversion ============

class TestSemesterIdxToHydrantCode:
    """Tests for semester_idx_to_hydrant_code."""

    def test_freshman_fall(self):
        """Semester 1 = Freshman Fall = f{planning_year_start}."""
        assert semester_idx_to_hydrant_code(1, 2025) == "f25"
        assert semester_idx_to_hydrant_code(1, 2024) == "f24"

    def test_freshman_iap(self):
        """Semester 2 = Freshman IAP = i{planning_year_start + 1}."""
        assert semester_idx_to_hydrant_code(2, 2025) == "i26"
        assert semester_idx_to_hydrant_code(2, 2024) == "i25"

    def test_freshman_spring(self):
        """Semester 3 = Freshman Spring = s{planning_year_start + 1}."""
        assert semester_idx_to_hydrant_code(3, 2025) == "s26"
        assert semester_idx_to_hydrant_code(3, 2024) == "s25"

    def test_sophomore_fall(self):
        """Semester 4 = Sophomore Fall = f{planning_year_start + 1}."""
        assert semester_idx_to_hydrant_code(4, 2025) == "f26"

    def test_sophomore_iap(self):
        """Semester 5 = Sophomore IAP = i{planning_year_start + 2}."""
        assert semester_idx_to_hydrant_code(5, 2025) == "i27"

    def test_sophomore_spring(self):
        """Semester 6 = Sophomore Spring = s{planning_year_start + 2}."""
        assert semester_idx_to_hydrant_code(6, 2025) == "s27"

    def test_senior_spring(self):
        """Semester 12 = Senior Spring = s{planning_year_start + 4}."""
        assert semester_idx_to_hydrant_code(12, 2025) == "s29"

    def test_full_progression_class_of_2029(self):
        """Test all 12 semesters for class of 2029 (planning_year_start=2025)."""
        expected = [
            (1, "f25"),   # Freshman Fall
            (2, "i26"),   # Freshman IAP
            (3, "s26"),   # Freshman Spring
            (4, "f26"),   # Sophomore Fall
            (5, "i27"),   # Sophomore IAP
            (6, "s27"),   # Sophomore Spring
            (7, "f27"),   # Junior Fall
            (8, "i28"),   # Junior IAP
            (9, "s28"),   # Junior Spring
            (10, "f28"),  # Senior Fall
            (11, "i29"),  # Senior IAP
            (12, "s29"),  # Senior Spring
        ]

        for semester_idx, expected_code in expected:
            result = semester_idx_to_hydrant_code(semester_idx, 2025)
            assert result == expected_code, (
                f"Semester {semester_idx} should be {expected_code}, got {result}"
            )


class TestHydrantCodeToSemesterIdx:
    """Tests for hydrant_code_to_semester_idx."""

    def test_freshman_fall(self):
        """f{planning_year_start} = Semester 1."""
        assert hydrant_code_to_semester_idx("f25", 2025) == 1
        assert hydrant_code_to_semester_idx("f24", 2024) == 1

    def test_freshman_iap(self):
        """i{planning_year_start + 1} = Semester 2."""
        assert hydrant_code_to_semester_idx("i26", 2025) == 2

    def test_freshman_spring(self):
        """s{planning_year_start + 1} = Semester 3."""
        assert hydrant_code_to_semester_idx("s26", 2025) == 3

    def test_sophomore_fall(self):
        """f{planning_year_start + 1} = Semester 4."""
        assert hydrant_code_to_semester_idx("f26", 2025) == 4

    def test_senior_spring(self):
        """s{planning_year_start + 4} = Semester 12."""
        assert hydrant_code_to_semester_idx("s29", 2025) == 12

    def test_semester_before_planning_year(self):
        """Codes before planning year should give semester <= 0."""
        result = hydrant_code_to_semester_idx("f24", 2025)
        assert result < 1, f"f24 with planning_year_start=2025 should be < 1, got {result}"

    def test_semester_after_graduation(self):
        """Codes after graduation should give semester > 12."""
        result = hydrant_code_to_semester_idx("f29", 2025)
        assert result > 12, f"f29 with planning_year_start=2025 should be > 12, got {result}"


class TestGetCurrentSemesterIndex:
    """Tests for get_current_semester_index function."""

    def test_freshman_fall_september(self):
        """Test that September of planning year start is semester 1 (Freshman Fall)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 1

    def test_freshman_iap_january(self):
        """Test that January is semester 2 (Freshman IAP)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 2

    def test_freshman_spring_march(self):
        """Test that March is semester 3 (Freshman Spring)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 3

    def test_sophomore_fall_september(self):
        """Test that September one year later is semester 4 (Sophomore Fall)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 9, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 4

    def test_sophomore_iap_january(self):
        """Test that January one year later is semester 5 (Sophomore IAP)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2027, 1, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 5

    def test_sophomore_spring_april(self):
        """Test that April one year later is semester 6 (Sophomore Spring)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2027, 4, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 6

    def test_junior_fall(self):
        """Test Junior Fall (semester 7)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2027, 9, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 7

    def test_junior_iap(self):
        """Test Junior IAP (semester 8)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2028, 1, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 8

    def test_junior_spring(self):
        """Test Junior Spring (semester 9)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2028, 5, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 9

    def test_senior_fall(self):
        """Test Senior Fall (semester 10)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2028, 10, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 10

    def test_senior_iap(self):
        """Test Senior IAP (semester 11)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2029, 1, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 11

    def test_senior_spring(self):
        """Test Senior Spring (semester 12)."""
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2029, 2, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 12

    def test_before_planning_year_returns_zero(self):
        """Test that dates before planning year start return 0."""
        with patch('shared.utils.datetime') as mock_datetime:
            # August 2024 is before planning year 2025-2026
            mock_datetime.now.return_value = datetime(2024, 8, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 0

    def test_after_graduation_returns_twelve(self):
        """Test that dates after graduation are clamped to 12."""
        with patch('shared.utils.datetime') as mock_datetime:
            # September 2029 is after graduation (May 2029)
            mock_datetime.now.return_value = datetime(2029, 9, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 12

    def test_august_before_fall_semester(self):
        """Test that August is still counted as Spring semester (Fall starts in September)."""
        with patch('shared.utils.datetime') as mock_datetime:
            # August 2026 is still Freshman Spring (summer before Sophomore Fall)
            mock_datetime.now.return_value = datetime(2026, 8, 15)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            # August is before Fall semester starts (September)
            # Still counted as Freshman Spring (semester 3)
            assert result == 3

    def test_boundary_fall_starts_september(self):
        """Test that Fall semester starts in September (month 9)."""
        with patch('shared.utils.datetime') as mock_datetime:
            # September 1st should be Fall
            mock_datetime.now.return_value = datetime(2025, 9, 1)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 1  # Freshman Fall

    def test_boundary_iap_january_only(self):
        """Test that IAP is only in January (month 0)."""
        with patch('shared.utils.datetime') as mock_datetime:
            # January 31st should be IAP
            mock_datetime.now.return_value = datetime(2026, 1, 31)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 2  # Freshman IAP

    def test_boundary_spring_starts_february(self):
        """Test that Spring semester starts in February."""
        with patch('shared.utils.datetime') as mock_datetime:
            # February 1st should be Spring
            mock_datetime.now.return_value = datetime(2026, 2, 1)
            planning_year_start = 2025

            result = get_current_semester_index(planning_year_start)
            assert result == 3  # Freshman Spring

    def test_summer_months_treated_as_spring(self):
        """Test that summer months (May, June, July) are treated as Spring semester."""
        planning_year_start = 2025

        # May (month 5)
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 5, 15)
            result = get_current_semester_index(planning_year_start)
            # May 2026 should still be Freshman Spring (semester 3)
            assert result == 3, f"May should be Spring semester, got {result}"

        # June (month 6)
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 6, 15)
            result = get_current_semester_index(planning_year_start)
            # June 2026 should still be Freshman Spring (semester 3)
            assert result == 3, f"June should be Spring semester, got {result}"

        # July (month 7)
        with patch('shared.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 7, 15)
            result = get_current_semester_index(planning_year_start)
            # July 2026 should still be Freshman Spring (semester 3)
            assert result == 3, f"July should be Spring semester, got {result}"

        # August (month 8)
        with patch('shared.utils.datetime') as mock_datetime:
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
            with patch('shared.utils.datetime') as mock_datetime:
                mock_datetime.now.return_value = test_date
                result = get_current_semester_index(planning_year_start)
                assert result == expected_semester, \
                    f"Date {test_date} should be semester {expected_semester}, got {result}"
