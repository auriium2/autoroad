"""
Unit tests for prerequisite parser.
"""

import pytest
from backend.prerequisites.parser import (
    fireroad_to_courseroad,
    prereq_to_string,
    is_valid_course_id,
    tokenize,
    filter_junk_tokens,
)


class TestCourseIDValidation:
    """Tests for course ID validation."""
    
    def test_valid_course_ids(self):
        """Test that valid course IDs are recognized."""
        assert is_valid_course_id("18.01")
        assert is_valid_course_id("6.100A")
        assert is_valid_course_id("14.01")
        assert is_valid_course_id("IDS.012")
        assert is_valid_course_id("18.C06")
    
    def test_gir_requirements(self):
        """Test that GIR requirements are recognized."""
        assert is_valid_course_id("GIR:BIOL")
        assert is_valid_course_id("GIR:CAL2")
        assert is_valid_course_id("GIR:PHY1")
    
    def test_invalid_course_ids(self):
        """Test that invalid strings are rejected."""
        assert not is_valid_course_id("permission of instructor")
        assert not is_valid_course_id("''quoted text''")
        assert not is_valid_course_id("")
        assert not is_valid_course_id("just text")


class TestTokenizer:
    """Tests for prerequisite string tokenization."""
    
    def test_simple_tokenize(self):
        """Test tokenization of simple prerequisites."""
        tokens = tokenize("18.01, 18.02")
        assert "18.01" in tokens
        assert "," in tokens
        assert "18.02" in tokens
    
    def test_tokenize_with_or(self):
        """Test tokenization with OR operator."""
        tokens = tokenize("18.01/18.02")
        assert "18.01" in tokens
        assert "/" in tokens
        assert "18.02" in tokens
    
    def test_tokenize_with_parens(self):
        """Test tokenization with parentheses."""
        tokens = tokenize("(18.01/18.02), 18.03")
        assert "(" in tokens
        assert "18.01" in tokens
        assert "/" in tokens
        assert "18.02" in tokens
        assert ")" in tokens
        assert "," in tokens
        assert "18.03" in tokens
    
    def test_tokenize_quoted_strings(self):
        """Test that quoted strings are tokenized."""
        tokens = tokenize("18.01/''permission of instructor''")
        assert "18.01" in tokens
        assert "/" in tokens
        assert "''permission of instructor''" in tokens
    
    def test_tokenize_gir(self):
        """Test tokenization of GIR requirements."""
        tokens = tokenize("GIR:BIOL, GIR:CAL2")
        assert "GIR:BIOL" in tokens
        assert "GIR:CAL2" in tokens


class TestFilterJunkTokens:
    """Tests for junk token filtering."""
    
    def test_filter_quoted_strings(self):
        """Test that quoted strings are filtered out."""
        tokens = ["18.01", "/", "''permission of instructor''"]
        filtered = filter_junk_tokens(tokens)
        assert "18.01" in filtered
        assert "''permission of instructor''" not in filtered
    
    def test_filter_invalid_course_ids(self):
        """Test that invalid course IDs are filtered out."""
        tokens = ["18.01", ",", "invalid", "18.02"]
        filtered = filter_junk_tokens(tokens)
        assert "18.01" in filtered
        assert "18.02" in filtered
        assert "invalid" not in filtered
    
    def test_filter_trailing_operators(self):
        """Test that trailing operators are removed."""
        tokens = ["18.01", "/"]
        filtered = filter_junk_tokens(tokens)
        assert "18.01" in filtered
        assert "/" not in filtered
    
    def test_filter_leading_operators(self):
        """Test that leading operators are removed."""
        tokens = ["/", "18.01"]
        filtered = filter_junk_tokens(tokens)
        assert "18.01" in filtered
        assert len(filtered) == 1


class TestFireroadParser:
    """Tests for Fireroad to CourseRoad conversion."""
    
    def test_simple_course(self):
        """Test parsing a single course."""
        result = fireroad_to_courseroad("18.01")
        assert result == [0, "18.01"]
    
    def test_and_prerequisites(self):
        """Test parsing AND prerequisites."""
        result = fireroad_to_courseroad("18.01, 18.02")
        assert result == [0, "18.01", "18.02"]
    
    def test_or_prerequisites(self):
        """Test parsing OR prerequisites."""
        result = fireroad_to_courseroad("18.01/18.02")
        assert result == [1, "18.01", "18.02"]
    
    def test_nested_prerequisites(self):
        """Test parsing nested prerequisites."""
        result = fireroad_to_courseroad("(18.01/18.02), 18.03")
        assert result == [0, [1, "18.01", "18.02"], "18.03"]
    
    def test_complex_nested(self):
        """Test parsing complex nested prerequisites."""
        result = fireroad_to_courseroad(
            "(18.06/18.700/18.701), (18.100A/18.100B/18.100P/18.100Q)"
        )
        expected = [
            0,
            [1, "18.06", "18.700", "18.701"],
            [1, "18.100A", "18.100B", "18.100P", "18.100Q"]
        ]
        assert result == expected
    
    def test_filter_permission_text(self):
        """Test that permission text is filtered out."""
        result = fireroad_to_courseroad("18.01/''permission of instructor''")
        assert result == [0, "18.01"]
    
    def test_gir_requirements(self):
        """Test parsing GIR requirements."""
        result = fireroad_to_courseroad("GIR:BIOL, GIR:CAL2")
        assert result == [0, "GIR:BIOL", "GIR:CAL2"]
    
    def test_empty_string(self):
        """Test parsing empty string."""
        result = fireroad_to_courseroad("")
        assert result == [0]
    
    def test_only_junk(self):
        """Test parsing string with only junk text."""
        result = fireroad_to_courseroad("''permission of instructor''")
        assert result == [0]


class TestPrereqToString:
    """Tests for converting prerequisite arrays to human-readable strings."""
    
    def test_simple_course(self):
        """Test converting simple course."""
        result = prereq_to_string([0, "18.01"])
        assert result == "18.01"
    
    def test_and_prerequisites(self):
        """Test converting AND prerequisites."""
        result = prereq_to_string([0, "18.01", "18.02"])
        assert result == "18.01 AND 18.02"
    
    def test_or_prerequisites(self):
        """Test converting OR prerequisites."""
        result = prereq_to_string([1, "18.01", "18.02"])
        assert result == "18.01 OR 18.02"
    
    def test_nested_prerequisites(self):
        """Test converting nested prerequisites."""
        result = prereq_to_string([0, [1, "18.01", "18.02"], "18.03"])
        assert result == "(18.01 OR 18.02) AND 18.03"
    
    def test_threshold_prerequisites(self):
        """Test converting threshold prerequisites."""
        result = prereq_to_string([2, "18.01", "18.02", "18.03", "18.04"])
        assert result == "2 of: [18.01, 18.02, 18.03, 18.04]"


class TestRealWorldExamples:
    """Tests using real examples from Fireroad."""
    
    def test_complex_nested_with_permission(self):
        """Test complex example from actual Fireroad data."""
        input_str = "(10.302, (2.671/5.310/7.003/12.335/20.109/(1.106, 1.107)/(5.351, 5.352, 5.353)))/''permission of instructor''"
        result = fireroad_to_courseroad(input_str)
        
        # Should have 10.302 AND a big OR group
        assert result[0] == 0  # AND
        assert result[1] == "10.302"
        assert isinstance(result[2], list)
        assert result[2][0] == 1  # OR
    
    def test_multiple_girs(self):
        """Test example with multiple GIR requirements."""
        input_str = "GIR:BIOL, GIR:CAL2, GIR:CHEM, GIR:PHY1"
        result = fireroad_to_courseroad(input_str)
        expected = [0, "GIR:BIOL", "GIR:CAL2", "GIR:CHEM", "GIR:PHY1"]
        assert result == expected
    
    def test_course_with_letter_in_number(self):
        """Test course with letter in the number part (e.g., 18.C06)."""
        input_str = "(18.03/18.06/18.C06)"
        result = fireroad_to_courseroad(input_str)
        assert result == [1, "18.03", "18.06", "18.C06"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
