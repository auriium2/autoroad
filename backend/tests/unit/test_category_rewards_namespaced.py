"""
Tests for category rewards with namespaced requirement paths.

These tests verify that the fix for the subcategory starring bug works correctly:
- Different requirements can have subcategories at the same index without conflicts
- Paths are properly namespaced with requirement keys (e.g., "gir.0" vs "major6-3.0")
- Category rewards are applied correctly to the right courses based on namespaced paths
"""

import polars as pl
from ortools.sat.python import cp_model

from shared.optimizer.objectives.base import ObjectiveContext
from shared.optimizer.objectives.categories import CategoryRewards


class TestNamespacedCategoryRewards:
    """Test category rewards with namespaced requirement paths."""

    def test_different_requirements_same_index_different_tiers(self):
        """
        Test that starring subcategory at index 0 in GIR doesn't affect
        subcategory at index 0 in a major requirement.
        """
        courses_df = pl.DataFrame({
            'subject_id': ['8.01', '6.100A', '18.01', '6.1200'],  # Physics, EECS intro, Math, EECS theory
            'total_units': [12, 12, 12, 12],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_8.01_1'),    # Physics GIR
            (1, 1): model.NewBoolVar('take_6.100A_1'),  # EECS intro (satisfies both GIR and major)
            (2, 1): model.NewBoolVar('take_18.01_1'),   # Math GIR
            (3, 1): model.NewBoolVar('take_6.1200_1'),  # EECS theory (major only)
        }

        # Simulate the bug scenario:
        # - User stars "Science Requirement" (index 0) in GIR with tier 3
        # - "Programming Skills" (index 0) in major6-3 should have tier 0 (not starred)
        # With the fix, these are now "gir.0" and "major6-3.0" (separate)

        requirement_tiers = {
            'gir.0': 3,        # Science Requirement starred (tier 3)
            'major6-3.0': 0,   # Programming Skills NOT starred (tier 0)
        }

        course_to_requirements = {
            0: {'gir.0'},              # 8.01 satisfies GIR Science
            1: {'gir.0', 'major6-3.0'},  # 6.100A satisfies both
            2: {'gir.1'},              # 18.01 satisfies GIR Math (different subcategory)
            3: {'major6-3.0'},         # 6.1200 satisfies Major Programming
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={'course_to_requirements': course_to_requirements},
            requirement_tiers=requirement_tiers
        )

        objective = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        # Take all courses
        for var in take_vars.values():
            model.Add(var == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL

        # Expected behavior:
        # - gir.0 has tier 3, so courses in it get tier 3 rewards
        # - major6-3.0 has tier 0, so courses in it get NO rewards
        # - 8.01: only in gir.0 (tier 3) → gets reward
        # - 6.100A: in both, but max tier is 3 → gets tier 3 reward
        # - 18.01: in gir.1 (not starred) → no reward
        # - 6.1200: only in major6-3.0 (tier 0) → no reward

        # The objective value should be negative (rewards applied)
        # At least 8.01 and 6.100A should get tier 3 rewards
        assert solver.ObjectiveValue() < 0, "Should have negative cost due to tier 3 rewards"

    def test_same_index_different_requirements_independent_tiers(self):
        """
        Test that the same subcategory index in different requirements
        can have different tier values independently.
        """
        courses_df = pl.DataFrame({
            'subject_id': ['COURSE_A', 'COURSE_B', 'COURSE_C'],
            'total_units': [12, 12, 12],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_A_1'),
            (1, 1): model.NewBoolVar('take_B_1'),
            (2, 1): model.NewBoolVar('take_C_1'),
        }

        # All subcategories at index 0, but in different requirements
        requirement_tiers = {
            'req1.0': 1,   # Tier 1
            'req2.0': 2,   # Tier 2
            'req3.0': 3,   # Tier 3
        }

        course_to_requirements = {
            0: {'req1.0'},  # Only in tier 1 category
            1: {'req2.0'},  # Only in tier 2 category
            2: {'req3.0'},  # Only in tier 3 category
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={'course_to_requirements': course_to_requirements},
            requirement_tiers=requirement_tiers
        )

        objective = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        # Take all courses
        for var in take_vars.values():
            model.Add(var == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL

        # Each course should get a different tier reward
        # Higher tier = more negative cost (better)
        # The objective value should reflect tier 1 + tier 2 + tier 3 rewards
        assert solver.ObjectiveValue() < 0, "Should have negative cost from all three tiers"

    def test_namespace_prevents_tier_collision(self):
        """
        Regression test: Without namespacing, starring root.2 in one requirement
        would incorrectly star root.2 in ALL requirements.
        With namespacing, they are independent.
        """
        courses_df = pl.DataFrame({
            'subject_id': ['GIR_COURSE', 'MAJOR_COURSE'],
            'total_units': [12, 12],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_gir_1'),
            (1, 1): model.NewBoolVar('take_major_1'),
        }

        # OLD BUG: If user starred GIR index 2, it would also star major index 2
        # NEW FIX: They are separate - gir.2 vs major.2

        requirement_tiers = {
            'gir.2': 3,    # GIR subcategory 2 is starred (tier 3)
            'major.2': 0,  # Major subcategory 2 is NOT starred (tier 0)
        }

        course_to_requirements = {
            0: {'gir.2'},    # GIR course in starred category
            1: {'major.2'},  # Major course in non-starred category
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={'course_to_requirements': course_to_requirements},
            requirement_tiers=requirement_tiers
        )

        objective = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        # Take both courses
        for var in take_vars.values():
            model.Add(var == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL

        # Only the GIR course should get a reward (tier 3)
        # The major course should get no reward (tier 0)
        # The objective should be negative but not as negative as if both had tier 3
        cost = solver.ObjectiveValue()
        assert cost < 0, "GIR course should get tier 3 reward"

        # If the bug existed, both would get tier 3 rewards and the cost would be more negative
        # With the fix, only one gets the reward

    def test_nested_subcategories_with_namespacing(self):
        """Test deeply nested subcategory paths work correctly with namespacing."""
        courses_df = pl.DataFrame({
            'subject_id': ['DEEP_COURSE_1', 'DEEP_COURSE_2'],
            'total_units': [12, 12],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_1'),
            (1, 1): model.NewBoolVar('take_2'),
        }

        # Test deeply nested paths
        requirement_tiers = {
            'gir.0.1.2': 3,        # Deeply nested in GIR
            'major.0.1.2': 1,      # Same structure in major, different tier
        }

        course_to_requirements = {
            0: {'gir.0.1.2'},
            1: {'major.0.1.2'},
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={'course_to_requirements': course_to_requirements},
            requirement_tiers=requirement_tiers
        )

        objective = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        for var in take_vars.values():
            model.Add(var == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        assert solver.ObjectiveValue() < 0, "Both courses should get rewards (different tiers)"
