"""
Regression tests for prerequisite parser.

Focus: Tests that catch real bugs found in production.
Trivial tests removed - covered by property-based tests in test_prerequisites_parser_property.py.
"""

import pytest

from shared.courses.prerequisites.parser import (
    extract_course_ids,
    parse_fireroad,
)
from shared.courses.prerequisites.types import PrereqCourse, PrereqGroup


class TestFireroadParser:
    """Tests for Fireroad to PrereqNode conversion - real-world edge cases only."""

    def test_complex_nested(self):
        """Test parsing complex nested prerequisites."""
        result = parse_fireroad(
            "(18.06/18.700/18.701), (18.100A/18.100B/18.100P/18.100Q)"
        )
        expected = PrereqGroup(
            threshold=2,
            items=(
                PrereqGroup(
                    threshold=1,
                    items=(
                        PrereqCourse("18.06"),
                        PrereqCourse("18.700"),
                        PrereqCourse("18.701")
                    )
                ),
                PrereqGroup(
                    threshold=1,
                    items=(
                        PrereqCourse("18.100A"),
                        PrereqCourse("18.100B"),
                        PrereqCourse("18.100P"),
                        PrereqCourse("18.100Q")
                    )
                )
            )
        )
        assert result == expected

    def test_filter_permission_text(self):
        """Test that permission text is filtered out - real edge case from production."""
        result = parse_fireroad("18.01/''permission of instructor''")
        assert result == PrereqCourse("18.01")


class TestRealWorldExamples:
    """Tests using real examples from Fireroad."""

    def test_complex_nested_with_permission(self):
        """Test complex example from actual Fireroad data."""
        input_str = "(10.302, (2.671/5.310/7.003/12.335/20.109/(1.106, 1.107)/(5.351, 5.352, 5.353)))/''permission of instructor''"
        result = parse_fireroad(input_str)

        assert isinstance(result, PrereqGroup)
        assert result.threshold == 2  # Outer is AND

        # First item is a course
        assert result.items[0] == PrereqCourse("10.302")

        # Second item is a complex OR group
        or_group = result.items[1]
        assert isinstance(or_group, PrereqGroup)
        assert or_group.threshold == 1

    def test_6_1910_quoted_strings_with_operators(self):
        """Test 6.1910 case: quoted strings between operators causing parse errors."""
        input_str = "GIR:PHY2/6.100A/(''Coreq: 6.1903''/6.1904)/''permission of instructor''"

        # Should parse without raising an error
        result = parse_fireroad(input_str)

        # Should be an OR group
        assert isinstance(result, PrereqGroup)
        assert result.threshold == 1  # OR

        # Should contain GIR:PHY2, 6.100A, and 6.1904 (but not the quoted strings)
        course_ids = extract_course_ids(result)
        assert "GIR:PHY2" in course_ids
        assert "6.100A" in course_ids
        assert "6.1904" in course_ids
        assert len(course_ids) == 3  # Only these three courses


class TestRegressionFireroadBugs:
    """
    Regression tests for bugs found by fuzzing against real Fireroad data.
    These were all failing before the fixes applied in 2025.
    """

    def test_empty_parentheses_after_quoted_strings(self):
        """
        Regression: Quoted strings inside parentheses left empty () after filtering.
        Pattern: course/(''text'', ''text'')
        Examples: 21G.501-506, 21G.551-552, 21L.609, 21L.613
        """
        test_cases = [
            ("21G.501/(''placement test'', ''permission of instructor'')", ["21G.501"]),
            ("21G.502/(''placement test'', ''permission of instructor'')", ["21G.502"]),
            ("21L.609/(''placement exam'', ''permission of instructor'')", ["21L.609"]),
        ]

        for input_str, expected_courses in test_cases:
            result = parse_fireroad(input_str)
            course_ids = extract_course_ids(result)
            assert course_ids == expected_courses, f"Failed for: {input_str}"

    def test_text_and_operator(self):
        """
        Regression: Text 'AND' operator was not recognized, only comma.
        Pattern: (course1 AND course2)
        Example: ''Prereq: 10.213''/10.40/(5.601 AND 5.602)
        """
        input_str = "''Prereq: 10.213''/10.40/(5.601 AND 5.602)"
        result = parse_fireroad(input_str)

        course_ids = extract_course_ids(result)
        assert "10.40" in course_ids
        assert "5.601" in course_ids
        assert "5.602" in course_ids

        # Verify structure: should be OR at top level
        assert isinstance(result, PrereqGroup)
        assert result.threshold == 1  # OR

        # Second item should be a group with AND (threshold=2)
        and_group = result.items[1]
        assert isinstance(and_group, PrereqGroup)
        assert and_group.threshold == 2  # AND

    def test_complex_corequisite_with_multiple_quoted(self):
        """
        Regression: Complex prerequisite with multiple quoted strings and coreqs.
        Pattern: course1/course2/(''Coreq: X''/course3, ''text'')
        Example: 5.310/7.002/(''Coreq: 12 units UROP''/''other approved laboratory subject'', ''permission of instructor'')
        """
        input_str = "5.310/7.002/(''Coreq: 12 units UROP''/''other approved laboratory subject'', ''permission of instructor'')"
        result = parse_fireroad(input_str)

        course_ids = extract_course_ids(result)
        assert "5.310" in course_ids
        assert "7.002" in course_ids
        assert len(course_ids) == 2  # No quoted strings should be parsed as courses

    def test_operator_after_opening_paren(self):
        """
        Regression: Operator directly after opening paren caused parse error.
        Pattern: (/course) or (,course)
        This happened when quoted strings were removed from (''text''/course).
        """
        # This would be the result after filtering quoted strings
        # The filter should clean this up automatically
        input_str = "GIR:PHY2/6.100A/(''quoted''/6.1904)"
        result = parse_fireroad(input_str)

        course_ids = extract_course_ids(result)
        assert "GIR:PHY2" in course_ids
        assert "6.100A" in course_ids
        assert "6.1904" in course_ids

    def test_operator_before_closing_paren(self):
        """
        Regression: Operator directly before closing paren caused parse error.
        Pattern: (course/) or (course,)
        This happened when trailing quoted strings were removed.
        """
        input_str = "21G.504/(''Placement test'', ''permission of instructor'')"
        result = parse_fireroad(input_str)

        course_ids = extract_course_ids(result)
        assert course_ids == ["21G.504"]

    def test_all_12_original_failures(self):
        """
        Regression: Test all 12 cases that were failing before the fix.
        This ensures we don't regress on any of them.
        """
        original_failures = [
            "''Prereq: 10.213''/10.40/(5.601 AND 5.602)",
            "21G.501/(''placement test'', ''permission of instructor'')",
            "21G.502/(''placement test'', ''permission of instructor'')",
            "21G.503/(''placement test'', ''permission of instructor'')",
            "21G.504/(''Placement test'', ''permission of instructor'')",
            "21G.505/(''Placement test'', ''permission of instructor'')",
            "21G.506/(''Placement test'', ''permission of instructor'')",
            "21G.551/(''placement test'', ''permission of instructor'')",
            "21G.552/(''placement test'', ''permission of instructor'')",
            "21L.609/(''placement exam'', ''permission of instructor'')",
            "21L.613/(''placement exam'', ''permission of instructor'')",
            "5.310/7.002/(''Coreq: 12 units UROP''/''other approved laboratory subject'', ''permission of instructor'')",
        ]

        for input_str in original_failures:
            # All of these should parse without raising an exception
            result = parse_fireroad(input_str)
            assert result is not None, f"Failed to parse: {input_str}"

            # All should extract at least one valid course
            course_ids = extract_course_ids(result)
            assert len(course_ids) > 0, f"No courses found in: {input_str}"

            # None should contain quoted strings
            for course_id in course_ids:
                assert not course_id.startswith("''"), f"Quoted string in result: {course_id}"
                assert not course_id.startswith('"'), f"Quoted string in result: {course_id}"

    def test_multiple_girs(self):
        """Test example with multiple GIR requirements."""
        input_str = "GIR:BIOL, GIR:CAL2, GIR:CHEM, GIR:PHY1"
        result = parse_fireroad(input_str)
        expected = PrereqGroup(
            threshold=4,
            items=(
                PrereqCourse("GIR:BIOL"),
                PrereqCourse("GIR:CAL2"),
                PrereqCourse("GIR:CHEM"),
                PrereqCourse("GIR:PHY1")
            )
        )
        assert result == expected

    def test_course_with_letter_in_number(self):
        """Test course with letter in the number part (e.g., 18.C06)."""
        input_str = "(18.03/18.06/18.C06)"
        result = parse_fireroad(input_str)
        expected = PrereqGroup(
            threshold=1,
            items=(
                PrereqCourse("18.03"),
                PrereqCourse("18.06"),
                PrereqCourse("18.C06")
            )
        )
        assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
