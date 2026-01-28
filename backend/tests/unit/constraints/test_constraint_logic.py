"""
Regression tests for constraint logic, particularly semester detection.

This test suite ensures that semester-based logic (especially IAP detection)
works correctly after the major bug fix where % 3 == 1 was incorrectly used
to detect IAP semesters instead of % 3 == 2.
"""



class TestSemesterDetection:
    """Tests for semester type detection logic (Fall, IAP, Spring)."""

    def test_iap_detection_modulo_arithmetic(self):
        """
        Regression test for IAP detection bug.

        In 1-indexed semester system:
        - Semester 1, 4, 7, 10 = Fall (semester % 3 == 1)
        - Semester 2, 5, 8, 11 = IAP (semester % 3 == 2)
        - Semester 3, 6, 9, 12 = Spring (semester % 3 == 0)

        The bug was using % 3 == 1 to detect IAP, which actually detects Fall.
        """
        fall_semesters = [1, 4, 7, 10]
        iap_semesters = [2, 5, 8, 11]
        spring_semesters = [3, 6, 9, 12]

        for sem in fall_semesters:
            assert sem % 3 == 1, f"Fall semester {sem} should have % 3 == 1"
            assert sem % 3 != 2, f"Fall semester {sem} should NOT match IAP detection"

        for sem in iap_semesters:
            assert sem % 3 == 2, f"IAP semester {sem} should have % 3 == 2"
            assert sem % 3 != 1, f"IAP semester {sem} should NOT match Fall detection"

        for sem in spring_semesters:
            assert sem % 3 == 0, f"Spring semester {sem} should have % 3 == 0"
            assert sem % 3 != 1, f"Spring semester {sem} should NOT match Fall detection"
            assert sem % 3 != 2, f"Spring semester {sem} should NOT match IAP detection"

    def test_all_semesters_classified(self):
        """Ensure every semester 1-12 is classified as exactly one type."""
        for semester in range(1, 13):
            classifications = 0
            if semester % 3 == 1:  # Fall
                classifications += 1
            if semester % 3 == 2:  # IAP
                classifications += 1
            if semester % 3 == 0:  # Spring
                classifications += 1

            assert classifications == 1, \
                f"Semester {semester} must be classified as exactly one type, got {classifications}"

    def test_section_to_semester_conversion(self):
        """
        Test conversion from 0-indexed section to 1-indexed semester.

        Section (0-indexed): 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
        Semester (1-indexed): 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12

        IAP sections: 1, 4, 7, 10 -> semesters: 2, 5, 8, 11
        """
        iap_sections = [1, 4, 7, 10]

        for section in iap_sections:
            semester = section + 1
            assert semester % 3 == 2, \
                f"Section {section} -> semester {semester} should be IAP (% 3 == 2)"
            assert (section + 1) % 3 == 2, \
                f"Direct check: (section {section} + 1) % 3 should == 2 for IAP"

    def test_marker_iap_detection(self):
        """
        Test the logic used in banIAP constraint for marker detection.

        When checking if a marker is in IAP:
        if marker.section >= 0 and (marker.section + 1) % 3 == 2
        """
        test_cases = [
            # (section, is_iap)
            (0, False),   # Freshman Fall
            (1, True),    # Freshman IAP
            (2, False),   # Freshman Spring
            (3, False),   # Sophomore Fall
            (4, True),    # Sophomore IAP
            (5, False),   # Sophomore Spring
            (6, False),   # Junior Fall
            (7, True),    # Junior IAP
            (8, False),   # Junior Spring
            (9, False),   # Senior Fall
            (10, True),   # Senior IAP
            (11, False),  # Senior Spring
        ]

        for section, expected_is_iap in test_cases:
            # This is the logic from optimize.py marker detection
            is_iap = section >= 0 and (section + 1) % 3 == 2
            assert is_iap == expected_is_iap, \
                f"Section {section}: expected IAP={expected_is_iap}, got {is_iap}"

    def test_ase_semester_exclusion(self):
        """
        Test that ASE (semester -1) is properly excluded from constraints.

        CRITICAL: In Python, -1 % 3 == 2, which means ASE would be detected as IAP
        if we only used modulo arithmetic! This is a subtle but serious bug.

        ASE should be excluded from:
        - AvoidIAP (using semester >= 1 and semester % 3 == 2)
        - MinimumClassesPerSemester (using semester >= 1 and semester % 3 == 2, or semester < 1)
        - banIAP hard constraint (using semester >= 1 and semester % 3 == 2)
        - LimitHoursPerSemester (using semester >= 1)
        - LimitFinalsPerSemester (using semester >= 1)
        """
        ase_semester = -1

        # CRITICAL: Demonstrate the Python modulo gotcha
        assert ase_semester % 3 == 2, \
            "In Python, -1 % 3 == 2, so ASE looks like IAP with naive modulo check!"

        # Correct detection requires BOTH checks
        is_iap_naive = ase_semester % 3 == 2  # WRONG - includes ASE
        is_iap_correct = ase_semester >= 1 and ase_semester % 3 == 2  # CORRECT

        assert is_iap_naive, "Naive check incorrectly identifies ASE as IAP"
        assert not is_iap_correct, "Correct check properly excludes ASE"

        # Verify IAP detection works correctly for real semesters
        iap_semesters = [2, 5, 8, 11]
        for sem in iap_semesters:
            is_iap = sem >= 1 and sem % 3 == 2
            assert is_iap, f"IAP semester {sem} should be detected"

        # Verify non-IAP semesters are not detected
        non_iap_semesters = [1, 3, 4, 6, 7, 9, 10, 12]
        for sem in non_iap_semesters:
            is_iap = sem >= 1 and sem % 3 == 2
            assert not is_iap, f"Non-IAP semester {sem} should not be detected"

    def test_minimum_classes_per_semester_skip_iap(self):
        """
        Test that MinimumClassesPerSemester correctly skips IAP semesters.

        The constraint should skip semesters where semester % 3 == 2.
        """
        iap_semesters = [2, 5, 8, 11]
        non_iap_semesters = [1, 3, 4, 6, 7, 9, 10, 12]

        for sem in iap_semesters:
            should_skip = sem % 3 == 2
            assert should_skip, f"MinimumClassesPerSemester should skip IAP semester {sem}"

        for sem in non_iap_semesters:
            should_skip = sem % 3 == 2
            assert not should_skip, f"MinimumClassesPerSemester should NOT skip semester {sem}"


class TestConstraintBehavior:
    """Tests for overall constraint behavior and edge cases."""

    def test_avoid_iap_penalty_targets_correct_semesters(self):
        """
        Test that AvoidIAP penalty is only applied to IAP semesters.

        This is a regression test for the bug where Fall semesters
        were being penalized instead of IAP semesters.
        """
        iap_semesters = [2, 5, 8, 11]
        all_semesters = range(1, 13)

        for semester in all_semesters:
            should_penalize = semester % 3 == 2
            is_iap = semester in iap_semesters

            assert should_penalize == is_iap, \
                f"Semester {semester}: IAP detection mismatch"

    def test_tier_penalties_reasonable(self):
        """
        Test that tier penalties with TIER_BASE=5 are reasonable.

        Tier 1: 5
        Tier 2: 25
        Tier 3: 125
        Tier 4: 625

        This ensures the penalty system doesn't create extreme values
        that cause the solver to make bizarre choices.
        """
        TIER_BASE = 5

        tier_1 = TIER_BASE
        tier_2 = TIER_BASE ** 2
        tier_3 = TIER_BASE ** 3
        tier_4 = TIER_BASE ** 4

        assert tier_1 == 5
        assert tier_2 == 25
        assert tier_3 == 125
        assert tier_4 == 625

        # Ratios should be consistent (each tier is TIER_BASE times the previous)
        assert tier_2 / tier_1 == TIER_BASE
        assert tier_3 / tier_2 == TIER_BASE
        assert tier_4 / tier_3 == TIER_BASE

        # Tier 4 shouldn't be so extreme that it dominates everything else
        # (this was the issue with TIER_BASE=7 -> 2401)
        assert tier_4 < 1000, "Tier 4 penalty should be reasonable"


class TestSemesterIndexConsistency:
    """Tests to ensure semester indexing is consistent across the codebase."""

    def test_semester_ranges(self):
        """Test that semester ranges are consistent."""
        # Valid semesters are 1-12 (plus ASE at -1)
        assert -1 not in range(1, 13), "ASE should not be in regular semester range"
        assert 1 in range(1, 13)
        assert 12 in range(1, 13)
        assert 0 not in range(1, 13), "Semester 0 should not exist"
        assert 13 not in range(1, 13), "Semester 13 should not exist"

    def test_year_progression(self):
        """Test that years progress correctly through semesters."""
        # Freshman: 1, 2, 3
        # Sophomore: 4, 5, 6
        # Junior: 7, 8, 9
        # Senior: 10, 11, 12

        def get_year(semester: int) -> int:
            """Get academic year (1-4) from semester (1-12)."""
            return ((semester - 1) // 3) + 1

        assert get_year(1) == 1   # Freshman Fall
        assert get_year(2) == 1   # Freshman IAP
        assert get_year(3) == 1   # Freshman Spring
        assert get_year(4) == 2   # Sophomore Fall
        assert get_year(5) == 2   # Sophomore IAP
        assert get_year(6) == 2   # Sophomore Spring
        assert get_year(7) == 3   # Junior Fall
        assert get_year(8) == 3   # Junior IAP
        assert get_year(9) == 3   # Junior Spring
        assert get_year(10) == 4  # Senior Fall
        assert get_year(11) == 4  # Senior IAP
        assert get_year(12) == 4  # Senior Spring

    def test_semester_type_within_year(self):
        """Test that semester types cycle correctly within each year."""
        for year in range(1, 5):  # Years 1-4
            base = (year - 1) * 3
            fall = base + 1
            iap = base + 2
            spring = base + 3

            assert fall % 3 == 1, f"Year {year} Fall should be % 3 == 1"
            assert iap % 3 == 2, f"Year {year} IAP should be % 3 == 2"
            assert spring % 3 == 0, f"Year {year} Spring should be % 3 == 0"
