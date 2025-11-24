"""
Tests for category rewards objective with geometric series diminishing returns.

These tests verify that:
1. Geometric series rewards are calculated correctly via tier configuration
2. Rewards are applied correctly based on course-to-requirement mappings
3. Tier scaling is applied correctly from requirement stars only
4. Decay rate affects reward diminishing returns appropriately
5. Rewards respect tier constraints and provide proper diminishing returns
"""

import polars as pl
from ortools.sat.python import cp_model

from optimizer.objectives.base import ObjectiveContext
from optimizer.objectives.categories import CategoryRewards


class TestCategoryRewardsTierConfiguration:
    """Test tier configuration and decay rate settings."""

    def test_default_decay_rate(self):
        """Default decay rate should be 0.70."""
        objective = CategoryRewards()
        assert objective.decay_rate == 0.70

    def test_custom_decay_rate(self):
        """Should accept custom decay rate."""
        objective = CategoryRewards(decay_rate=0.85)
        assert objective.decay_rate == 0.85

        # Tier 2 should use the custom decay
        assert objective.tier_config[2]['decay'] == 0.85

    def test_tier_scaling_from_requirement_stars(self):
        """Verify tier configuration scales by requirement tier."""
        objective = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)

        # Tier 1: base=10
        # Tier 2: base=20
        # Tier 3: base=30
        assert objective.tier_config[1]['base'] == 10
        assert objective.tier_config[2]['base'] == 20
        assert objective.tier_config[3]['base'] == 30

        # All use the same decay rate (or tier 1 uses slightly higher)
        assert objective.tier_config[2]['decay'] == 0.70
        assert objective.tier_config[3]['decay'] == 0.70

    def test_decay_rate_affects_tier_config(self):
        """Different decay rates should affect tier configuration."""
        fast = CategoryRewards(decay_rate=0.50)
        slow = CategoryRewards(decay_rate=0.90)

        # Same base for tier 2
        assert fast.tier_config[2]['base'] == slow.tier_config[2]['base']

        # Different decay rates
        assert fast.tier_config[2]['decay'] == 0.50
        assert slow.tier_config[2]['decay'] == 0.90


class TestCategoryRewardsBasicFunctionality:
    """Test basic reward application."""

    def test_no_reward_without_course_to_requirements(self):
        """Should return zero if no course_to_requirements mapping provided."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.1010', '6.1020'],
            'total_units': [12, 12],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_0_1'),
            (1, 1): model.NewBoolVar('take_1_1'),
        }

        # No course_to_requirements in context
        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={},
            requirement_tiers={'root.category1': 2}
        )

        objective = CategoryRewards(max_courses_per_category=3, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        model.Add(take_vars[(0, 1)] == 1)
        model.Add(take_vars[(1, 1)] == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        # No rewards should be applied
        assert solver.ObjectiveValue() == 0

    def test_no_reward_without_requirement_tiers(self):
        """Should return zero if no requirement tiers provided."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.1010', '6.1020'],
            'total_units': [12, 12],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_0_1'),
            (1, 1): model.NewBoolVar('take_1_1'),
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={
                'course_to_requirements': {
                    0: {'root.category1'},
                    1: {'root.category1'}
                }
            },
            requirement_tiers={}
        )

        objective = CategoryRewards(max_courses_per_category=3, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        model.Add(take_vars[(0, 1)] == 1)
        model.Add(take_vars[(1, 1)] == 1)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        # No rewards (no tiers set)
        assert solver.ObjectiveValue() == 0

    def test_basic_category_reward(self):
        """Should apply rewards for courses in starred categories."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.1010', '6.1020', '6.1200'],
            'total_units': [12, 12, 12],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_0_1'),
            (1, 1): model.NewBoolVar('take_1_1'),
            (2, 1): model.NewBoolVar('take_2_1'),
        }

        # Map course indices to requirement paths
        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={
                'course_to_requirements': {
                    0: {'root.category1'},  # 6.1010 in category1
                    1: {'root.category1'},  # 6.1020 in category1
                }
            },
            requirement_tiers={'root.category1': 2}  # tier 2
        )

        objective = CategoryRewards(max_courses_per_category=3, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        # Take first two courses (both in category)
        model.Add(take_vars[(0, 1)] == 1)
        model.Add(take_vars[(1, 1)] == 1)
        model.Add(take_vars[(2, 1)] == 0)

        model.Minimize(expr)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        # Should have negative cost (reward)
        assert solver.ObjectiveValue() < 0


class TestCategoryRewardsDiminishingReturns:
    """Test diminishing returns behavior."""

    def test_diminishing_returns_in_practice(self):
        """Verify marginal reward decreases for each additional course."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.1010', '6.1020', '6.1030'],
            'total_units': [12, 12, 12],
        })

        # Test taking 1, 2, and 3 courses
        costs = []
        for num_courses in [1, 2, 3]:
            model = cp_model.CpModel()
            take_vars = {
                (0, 1): model.NewBoolVar('take_0_1'),
                (1, 1): model.NewBoolVar('take_1_1'),
                (2, 1): model.NewBoolVar('take_2_1'),
            }

            context = ObjectiveContext(
                planning_year_start=2024,
                courses_df=courses_df,
                extra={
                    'course_to_requirements': {
                        0: {'root.category1'},
                        1: {'root.category1'},
                        2: {'root.category1'},
                    }
                },
                requirement_tiers={'root.category1': 2}
            )

            objective = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
            expr = objective.add_to_model(model, take_vars, context)

            # Take specified number of courses
            for i in range(num_courses):
                model.Add(take_vars[(i, 1)] == 1)
            for i in range(num_courses, 3):
                model.Add(take_vars[(i, 1)] == 0)

            model.Minimize(expr)
            solver = cp_model.CpSolver()
            status = solver.Solve(model)
            assert status == cp_model.OPTIMAL
            costs.append(solver.ObjectiveValue())

        # All costs should be negative (rewards)
        assert all(c < 0 for c in costs)

        # Marginal reward should decrease
        marginal_1_to_2 = costs[0] - costs[1]  # reward for 2nd course
        marginal_2_to_3 = costs[1] - costs[2]  # reward for 3rd course
        assert marginal_1_to_2 > marginal_2_to_3 > 0

    def test_decay_rate_affects_diminishing_returns(self):
        """Higher decay rate = slower diminishing returns."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.1010', '6.1020', '6.1030', '6.1040', '6.1050'],
            'total_units': [12, 12, 12, 12, 12],
        })

        # Test with fast decay
        model_fast = cp_model.CpModel()
        take_vars_fast = {(i, 1): model_fast.NewBoolVar(f'take_{i}_1') for i in range(5)}

        context_fast = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={
                'course_to_requirements': {i: {'root.category1'} for i in range(5)}
            },
            requirement_tiers={'root.category1': 2}
        )

        objective_fast = CategoryRewards(max_courses_per_category=10, decay_rate=0.50)
        expr_fast = objective_fast.add_to_model(model_fast, take_vars_fast, context_fast)

        for var in take_vars_fast.values():
            model_fast.Add(var == 1)

        model_fast.Minimize(expr_fast)
        solver_fast = cp_model.CpSolver()
        solver_fast.Solve(model_fast)
        cost_fast = solver_fast.ObjectiveValue()

        # Test with slow decay
        model_slow = cp_model.CpModel()
        take_vars_slow = {(i, 1): model_slow.NewBoolVar(f'take_{i}_1') for i in range(5)}

        context_slow = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={
                'course_to_requirements': {i: {'root.category1'} for i in range(5)}
            },
            requirement_tiers={'root.category1': 2}
        )

        objective_slow = CategoryRewards(max_courses_per_category=10, decay_rate=0.85)
        expr_slow = objective_slow.add_to_model(model_slow, take_vars_slow, context_slow)

        for var in take_vars_slow.values():
            model_slow.Add(var == 1)

        model_slow.Minimize(expr_slow)
        solver_slow = cp_model.CpSolver()
        solver_slow.Solve(model_slow)
        cost_slow = solver_slow.ObjectiveValue()

        # Slower decay should give higher total reward (more negative cost)
        assert cost_slow < cost_fast


class TestCategoryRewardsTiers:
    """Test tier-based reward scaling."""

    def test_higher_tier_gives_higher_reward(self):
        """Tier 3 should give higher rewards than tier 2."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.1010', '6.1020'],
            'total_units': [12, 12],
        })

        # Test tier 2
        model_t2 = cp_model.CpModel()
        take_vars_t2 = {
            (0, 1): model_t2.NewBoolVar('take_0_1'),
            (1, 1): model_t2.NewBoolVar('take_1_1'),
        }

        context_t2 = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={
                'course_to_requirements': {0: {'root.cat'}, 1: {'root.cat'}}
            },
            requirement_tiers={'root.cat': 2}
        )

        objective_t2 = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
        expr_t2 = objective_t2.add_to_model(model_t2, take_vars_t2, context_t2)

        model_t2.Add(take_vars_t2[(0, 1)] == 1)
        model_t2.Add(take_vars_t2[(1, 1)] == 1)
        model_t2.Minimize(expr_t2)

        solver_t2 = cp_model.CpSolver()
        solver_t2.Solve(model_t2)
        cost_t2 = solver_t2.ObjectiveValue()

        # Test tier 3
        model_t3 = cp_model.CpModel()
        take_vars_t3 = {
            (0, 1): model_t3.NewBoolVar('take_0_1'),
            (1, 1): model_t3.NewBoolVar('take_1_1'),
        }

        context_t3 = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={
                'course_to_requirements': {0: {'root.cat'}, 1: {'root.cat'}}
            },
            requirement_tiers={'root.cat': 3}
        )

        objective_t3 = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
        expr_t3 = objective_t3.add_to_model(model_t3, take_vars_t3, context_t3)

        model_t3.Add(take_vars_t3[(0, 1)] == 1)
        model_t3.Add(take_vars_t3[(1, 1)] == 1)
        model_t3.Minimize(expr_t3)

        solver_t3 = cp_model.CpSolver()
        solver_t3.Solve(model_t3)
        cost_t3 = solver_t3.ObjectiveValue()

        # Tier 3 should give higher reward (more negative)
        assert cost_t3 < cost_t2

    def test_tier_zero_gives_no_reward(self):
        """Tier 0 categories should not receive rewards."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.1010'],
            'total_units': [12],
        })

        model = cp_model.CpModel()
        take_vars = {(0, 1): model.NewBoolVar('take_0_1')}

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={
                'course_to_requirements': {0: {'root.cat'}}
            },
            requirement_tiers={'root.cat': 0}
        )

        objective = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        model.Add(take_vars[(0, 1)] == 1)
        model.Minimize(expr)

        solver = cp_model.CpSolver()
        solver.Solve(model)

        # No reward for tier 0
        assert solver.ObjectiveValue() == 0


class TestCategoryRewardsMultipleSemesters:
    """Test reward behavior across multiple semesters."""

    def test_rewards_across_semesters(self):
        """Should count courses taken in different semesters."""
        courses_df = pl.DataFrame({
            'subject_id': ['6.1010', '6.1020'],
            'total_units': [12, 12],
        })

        model = cp_model.CpModel()
        take_vars = {
            (0, 1): model.NewBoolVar('take_0_1'),  # 6.1010 in semester 1
            (1, 2): model.NewBoolVar('take_1_2'),  # 6.1020 in semester 2
        }

        context = ObjectiveContext(
            planning_year_start=2024,
            courses_df=courses_df,
            extra={
                'course_to_requirements': {0: {'root.cat'}, 1: {'root.cat'}}
            },
            requirement_tiers={'root.cat': 2}
        )

        objective = CategoryRewards(max_courses_per_category=5, decay_rate=0.70)
        expr = objective.add_to_model(model, take_vars, context)

        model.Add(take_vars[(0, 1)] == 1)
        model.Add(take_vars[(1, 2)] == 1)
        model.Minimize(expr)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.OPTIMAL
        # Should count both courses for reward
        assert solver.ObjectiveValue() < 0
