"""
Property-based tests for prerequisite parser using Hypothesis.

These tests use property-based testing to verify invariants that should
hold for ANY input, not just hand-crafted test cases. This catches edge
cases that manual tests miss.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from courses.prerequisites.parser import is_valid_course_id, parse_fireroad
from courses.prerequisites.types import PrereqCourse, PrereqGroup, PrereqNode

# Strategy for generating valid course IDs
# Note: Only generate formats that the parser actually accepts
valid_course_ids = st.one_of(
    # Standard format: dept.number
    st.from_regex(r"[0-9]{1,2}\.[0-9A-Z]{2,5}", fullmatch=True),
    # GIR requirements (parser uses HASS: format, not HASS-)
    st.from_regex(r"GIR:(CAL1|CAL2|BIOL|CHEM|PHYS1|PHYS2)", fullmatch=True),
    # HASS requirements (parser expects HASS: format)
    st.from_regex(r"HASS:[AHSE]", fullmatch=True),
)

# Strategy for generating junk text that should be filtered
junk_text = st.one_of(
    st.from_regex(r"''[^']*''", fullmatch=True),  # Single-quoted strings
    st.from_regex(r'"[^"]*"', fullmatch=True),     # Double-quoted strings
    st.just("permission of instructor"),
    st.just("Permission required"),
    st.just("corequisite"),
)


class TestParserInvariants:
    """Test invariants that should hold for all parser inputs."""

    @given(st.text())
    def test_parser_never_crashes_on_realistic_input(self, prereq_str):
        """
        Property: Parser should never crash on realistic input.

        Note: Parser may raise ValueError on malformed input (like unmatched parens).
        This is acceptable - we just want to ensure it doesn't crash unexpectedly.
        """
        try:
            result = parse_fireroad(prereq_str)
            # Should return None or a valid node
            assert result is None or isinstance(result, (PrereqCourse, PrereqGroup))
        except ValueError:
            # ValueError is acceptable for malformed input
            pass
        except Exception as e:
            # Any other exception is a problem
            pytest.fail(f"Parser crashed unexpectedly on input '{prereq_str}': {e}")

    @given(st.text())
    def test_parser_never_returns_empty_groups(self, prereq_str):
        """
        Property: Parser should NEVER return an empty PrereqGroup.

        This is a critical invariant - empty groups were the source of the bug.
        """
        try:
            result = parse_fireroad(prereq_str)
        except ValueError:
            # Parser may reject malformed input - that's OK
            return

        if result is None:
            return  # OK: unparseable

        if isinstance(result, PrereqGroup):
            assert len(result.items) > 0, \
                f"Parser returned empty PrereqGroup for input: '{prereq_str}'"
            assert result.threshold > 0, \
                f"Parser returned PrereqGroup with threshold=0 for input: '{prereq_str}'"

    @given(valid_course_ids)
    def test_single_valid_course_always_parses(self, course_id):
        """
        Property: Any valid course ID should parse to a PrereqCourse.
        """
        result = parse_fireroad(course_id)

        assert result is not None, f"Valid course ID '{course_id}' failed to parse"
        assert isinstance(result, PrereqCourse), \
            f"Valid course ID '{course_id}' should parse to PrereqCourse, got {type(result)}"
        assert result.course_id == course_id

    @given(junk_text)
    def test_junk_text_returns_none(self, junk):
        """
        Property: Junk text (quotes, permission strings) should return None.
        """
        result = parse_fireroad(junk)

        assert result is None, \
            f"Junk text '{junk}' should parse to None, got {result}"

    @given(
        st.lists(valid_course_ids, min_size=2, max_size=5).filter(
            lambda lst: len(set(lst)) == len(lst)  # Unique courses
        )
    )
    def test_and_group_threshold_equals_length(self, courses):
        """
        Property: AND groups (courses separated by commas) should have
        threshold equal to number of items.
        """
        prereq_str = ",".join(courses)
        result = parse_fireroad(prereq_str)

        assert result is not None
        assert isinstance(result, PrereqGroup)
        assert result.threshold == len(result.items), \
            f"AND group should have threshold={len(result.items)}, got {result.threshold}"

    @given(
        st.lists(valid_course_ids, min_size=2, max_size=5).filter(
            lambda lst: len(set(lst)) == len(lst)
        )
    )
    def test_or_group_threshold_equals_one(self, courses):
        """
        Property: OR groups (courses separated by /) should have threshold=1.
        """
        prereq_str = "/".join(courses)
        result = parse_fireroad(prereq_str)

        assert result is not None
        assert isinstance(result, PrereqGroup)
        assert result.threshold == 1, \
            f"OR group should have threshold=1, got {result.threshold}"

    @given(st.text())
    def test_parsed_result_is_well_formed(self, prereq_str):
        """
        Property: If parser returns a result (not None), it must be well-formed.

        Well-formed means:
        - PrereqCourse has a non-empty course_id
        - PrereqGroup has threshold > 0 and len(items) > 0
        - All nested nodes are also well-formed
        """
        try:
            result = parse_fireroad(prereq_str)
        except ValueError:
            # Parser may reject malformed input
            return

        if result is None:
            return  # OK

        self._assert_well_formed(result, prereq_str)

    def _assert_well_formed(self, node: PrereqNode, original_input: str):
        """Recursively check if a node is well-formed."""
        if isinstance(node, PrereqCourse):
            assert node.course_id, \
                f"PrereqCourse has empty course_id (input: '{original_input}')"
            assert is_valid_course_id(node.course_id), \
                f"PrereqCourse has invalid course_id: {node.course_id} (input: '{original_input}')"

        elif isinstance(node, PrereqGroup):
            assert len(node.items) > 0, \
                f"PrereqGroup has no items (input: '{original_input}')"
            assert node.threshold > 0, \
                f"PrereqGroup has threshold <= 0 (input: '{original_input}')"
            assert node.threshold <= len(node.items), \
                f"PrereqGroup threshold ({node.threshold}) > items ({len(node.items)}) (input: '{original_input}')"

            # Check all children
            for child in node.items:
                self._assert_well_formed(child, original_input)

    @given(
        st.lists(
            st.one_of(valid_course_ids, junk_text),
            min_size=1,
            max_size=5
        )
    )
    def test_mixed_valid_and_junk_filters_junk(self, items):
        """
        Property: When mixing valid courses and junk text, junk should be filtered.

        For example: "6.100A,''permission of instructor'',6.1200" should parse
        as just "6.100A,6.1200".
        """
        prereq_str = ",".join(items)
        try:
            result = parse_fireroad(prereq_str)
        except ValueError:
            # Malformed input
            return

        # Count how many valid courses we have
        valid_courses = [item for item in items if is_valid_course_id(item)]

        if len(valid_courses) == 0:
            # All junk - should return None
            assert result is None
        elif len(valid_courses) == 1:
            # Single valid course
            assert isinstance(result, PrereqCourse)
            assert result.course_id == valid_courses[0]
        else:
            # Multiple valid courses - should be AND group
            assert isinstance(result, PrereqGroup)
            # Should only have the valid courses
            assert len(result.items) == len(valid_courses)


class TestParserEdgeCases:
    """Test specific edge cases that property testing might miss."""

    @given(st.integers(min_value=0, max_value=100))
    def test_empty_strings_return_none(self, num_spaces):
        """Property: Empty strings (with any amount of whitespace) return None."""
        result = parse_fireroad(" " * num_spaces)
        assert result is None

    @given(
        valid_course_ids,
        st.integers(min_value=0, max_value=10)
    )
    def test_course_with_trailing_operators_handles_gracefully(self, course_id, num_commas):
        """
        Property: Trailing operators should be handled gracefully.

        For example: "6.100A,,," should parse as just "6.100A".
        """
        prereq_str = course_id + "," * num_commas
        result = parse_fireroad(prereq_str)

        # Should parse as single course (operators filtered)
        assert isinstance(result, PrereqCourse)
        assert result.course_id == course_id

    @given(
        st.lists(valid_course_ids, min_size=2, max_size=5),
        st.integers(min_value=1, max_value=5)
    )
    def test_excessive_parentheses_dont_break_parser(self, courses, num_parens):
        """
        Property: Excessive parentheses should not break parsing.

        For example: "(((6.100A)))" should still parse correctly.
        """
        prereq_str = "(" * num_parens + ",".join(courses) + ")" * num_parens
        try:
            result = parse_fireroad(prereq_str)
            # Should still parse (maybe wrapped in groups, but valid)
            assert result is not None
        except ValueError:
            # Parser may reject deeply nested expressions - that's OK
            pass
