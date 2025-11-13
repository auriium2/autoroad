"""
Unit tests for prerequisite evaluator.
"""

import pytest
from backend.prerequisites.evaluator import PrerequisiteEvaluator
from backend.prerequisites.types import EvaluationResult


class TestBasicEvaluation:
    """Tests for basic prerequisite evaluation."""
    
    def test_simple_course_satisfied(self):
        """Test that a single course prerequisite is satisfied."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        result = evaluator.evaluate([0, "18.01"])
        assert result.satisfied
        assert "18.01" in result.matched_courses
    
    def test_simple_course_not_satisfied(self):
        """Test that a missing course is not satisfied."""
        evaluator = PrerequisiteEvaluator(["18.02"])
        result = evaluator.evaluate([0, "18.01"])
        assert not result.satisfied
        assert "18.01" in result.unsatisfied_reasons[0]
    
    def test_and_all_satisfied(self):
        """Test AND when all courses are present."""
        evaluator = PrerequisiteEvaluator(["18.01", "18.02"])
        result = evaluator.evaluate([0, "18.01", "18.02"])
        assert result.satisfied
        assert "18.01" in result.matched_courses
        assert "18.02" in result.matched_courses
    
    def test_and_partial_satisfied(self):
        """Test AND when only some courses are present."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        result = evaluator.evaluate([0, "18.01", "18.02"])
        assert not result.satisfied
        assert "18.02" in result.unsatisfied_reasons[0]
    
    def test_or_one_satisfied(self):
        """Test OR when one course is present."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        result = evaluator.evaluate([1, "18.01", "18.02"])
        assert result.satisfied
        assert "18.01" in result.matched_courses
    
    def test_or_none_satisfied(self):
        """Test OR when no courses are present."""
        evaluator = PrerequisiteEvaluator(["18.03"])
        result = evaluator.evaluate([1, "18.01", "18.02"])
        assert not result.satisfied


class TestNestedEvaluation:
    """Tests for nested prerequisite evaluation."""
    
    def test_nested_and_or(self):
        """Test (A OR B) AND C."""
        evaluator = PrerequisiteEvaluator(["18.01", "18.03"])
        result = evaluator.evaluate([0, [1, "18.01", "18.02"], "18.03"])
        assert result.satisfied
        assert "18.01" in result.matched_courses
        assert "18.03" in result.matched_courses
    
    def test_nested_and_or_missing(self):
        """Test (A OR B) AND C when C is missing."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        result = evaluator.evaluate([0, [1, "18.01", "18.02"], "18.03"])
        assert not result.satisfied
        assert "18.03" in result.unsatisfied_reasons[0]
    
    def test_complex_nested(self):
        """Test complex nested prerequisites."""
        evaluator = PrerequisiteEvaluator([
            "18.06", "18.100A"
        ])
        result = evaluator.evaluate([
            0,
            [1, "18.06", "18.700", "18.701"],
            [1, "18.100A", "18.100B", "18.100P", "18.100Q"]
        ])
        assert result.satisfied


class TestCourseReuse:
    """Tests for course reuse behavior."""
    
    def test_no_reuse_by_default(self):
        """Test that courses can't be reused by default."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        # Try to use 18.01 for two different requirements
        result1 = evaluator.evaluate([0, "18.01"])
        result2 = evaluator.evaluate([0, "18.01"])
        
        assert result1.satisfied
        assert not result2.satisfied  # Can't reuse 18.01
    
    def test_reuse_when_allowed(self):
        """Test that courses can be reused when explicitly allowed."""
        evaluator = PrerequisiteEvaluator(
            ["18.01"],
            allow_reuse_across_requirements=True
        )
        result1 = evaluator.evaluate([0, "18.01"])
        result2 = evaluator.evaluate([0, "18.01"])
        
        assert result1.satisfied
        assert result2.satisfied  # Can reuse 18.01
    
    def test_reset_clears_used_courses(self):
        """Test that reset() clears the used courses set."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        result1 = evaluator.evaluate([0, "18.01"])
        evaluator.reset()
        result2 = evaluator.evaluate([0, "18.01"])
        
        assert result1.satisfied
        assert result2.satisfied  # Can use again after reset


class TestThresholdRequirements:
    """Tests for threshold-based requirements (N of M)."""
    
    def test_two_of_four_satisfied(self):
        """Test '2 of 4' when we have 2."""
        evaluator = PrerequisiteEvaluator(["18.01", "18.03"])
        result = evaluator.evaluate([2, "18.01", "18.02", "18.03", "18.04"])
        assert result.satisfied
    
    def test_two_of_four_not_satisfied(self):
        """Test '2 of 4' when we only have 1."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        result = evaluator.evaluate([2, "18.01", "18.02", "18.03", "18.04"])
        assert not result.satisfied
    
    def test_threshold_early_exit(self):
        """Test that evaluation stops early when threshold is met."""
        evaluator = PrerequisiteEvaluator(["18.01", "18.02"])
        result = evaluator.evaluate([2, "18.01", "18.02", "18.03", "18.04"])
        # Should only match the first 2, not try the rest
        assert result.satisfied
        assert len(result.matched_courses) == 2


class TestGIRRequirements:
    """Tests for GIR requirement evaluation."""
    
    def test_gir_requirement_satisfied(self):
        """Test that GIR requirements can be satisfied."""
        evaluator = PrerequisiteEvaluator(["GIR:BIOL"])
        result = evaluator.evaluate([0, "GIR:BIOL"])
        assert result.satisfied
    
    def test_multiple_girs(self):
        """Test multiple GIR requirements."""
        evaluator = PrerequisiteEvaluator(["GIR:BIOL", "GIR:CAL2", "GIR:CHEM"])
        result = evaluator.evaluate([0, "GIR:BIOL", "GIR:CAL2", "GIR:CHEM"])
        assert result.satisfied


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_prereq_array(self):
        """Test evaluation of empty prerequisite."""
        evaluator = PrerequisiteEvaluator([])
        result = evaluator.evaluate([0])
        # Empty AND is vacuously true
        assert result.satisfied
    
    def test_invalid_prereq_format(self):
        """Test that invalid format raises error."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        with pytest.raises(ValueError):
            evaluator.evaluate([])  # Empty list
    
    def test_unknown_item_type(self):
        """Test that unknown item types raise error."""
        evaluator = PrerequisiteEvaluator(["18.01"])
        with pytest.raises(ValueError):
            evaluator.evaluate([0, 12345])  # Number instead of string


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
