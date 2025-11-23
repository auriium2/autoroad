"""
Category-based reward objective: reward taking classes in priority requirement categories.

Categories are subtrees within the degree requirements (e.g., "Architecture", "Programming Skills").
Users set tier priorities on requirement tree nodes, and this objective rewards taking courses
that fulfill those prioritized requirement subtrees.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from ortools.sat.python import cp_model

from .base import ObjectiveContext


class CategoryRewards:
    """
    Tier-based reward for taking courses in priority requirement categories.
    
    Uses geometric series with diminishing returns:
        reward(k) = base × (1 - decay^k) / (1 - decay)
    """


    def __init__(self, max_courses_per_category: int = 20, decay_rate: float = 0.70):
        """
        Args:
            max_courses_per_category: Maximum number of courses to consider per category
                                     (for precomputing reward table)
            decay_rate: Decay rate for geometric series (0-1). Lower = faster diminishing returns.
                       Default 0.70 provides good balance.
        """
        self.max_courses = max_courses_per_category
        self.decay_rate = decay_rate

        # Tier configuration with decay rate
        self.tier_config = {
            1: {"base": 10, "decay": min(decay_rate + 0.05, 0.95)},
            2: {"base": 20, "decay": decay_rate},
            3: {"base": 30, "decay": decay_rate},
        }

        # Store per-category terms for cost breakdown
        self.category_terms: dict[str, list[cp_model.LinearExpr]] = {}

    def get_name(self) -> str:
        return "Category Rewards"

    def get_description(self) -> str:
        return "Reward taking courses in priority requirement categories with diminishing returns"

    def preprocess(self, courses_df: pl.DataFrame) -> dict[str, Any]:
        """Extract category information from courses."""
        return {}

    def add_to_model(
        self,
        model: cp_model.CpModel,
        take_vars: dict[tuple[int, int], cp_model.IntVar],
        context: ObjectiveContext
    ) -> cp_model.LinearExpr:
        """
        Add category reward terms to the objective.
        
        For each requirement path with tier > 0, we reward taking courses that
        satisfy that requirement using a geometric series with diminishing returns.
        """
        # Get course-to-requirement mapping from context
        if context.extra is None:
            return cp_model.LinearExpr.constant(0)

        course_to_requirements = context.extra.get('course_to_requirements', {})
        if not course_to_requirements:
            return cp_model.LinearExpr.constant(0)

        # Get requirement tiers (which requirements are prioritized)
        requirement_tiers = context.requirement_tiers or {}
        if not requirement_tiers:
            return cp_model.LinearExpr.constant(0)

        reward_tables = self._precompute_reward_tables()

        self.category_terms = {}
        reward_terms = []

        # For each requirement path with a tier > 0
        for req_path, tier in requirement_tiers.items():
            if tier == 0:
                continue  # Tier 0 means no priority

            if tier not in reward_tables:
                continue  # Invalid tier

            # Find all courses that satisfy this requirement
            courses_for_req = []
            for course_idx, req_paths in course_to_requirements.items():
                if req_path in req_paths:
                    courses_for_req.append(course_idx)

            if not courses_for_req:
                continue

            # Count how many of these courses are taken (across all semesters)
            course_take_vars = []
            courses_with_vars = []
            for course_idx in courses_for_req:
                has_var = False
                # Check if this course is taken in any semester
                for semester in range(1, 13):
                    if (course_idx, semester) in take_vars:
                        course_take_vars.append(take_vars[(course_idx, semester)])
                        has_var = True
                # Also check special semesters (ASE = -1)
                if (course_idx, -1) in take_vars:
                    course_take_vars.append(take_vars[(course_idx, -1)])
                    has_var = True
                if has_var:
                    courses_with_vars.append(course_idx)

            if not course_take_vars:
                continue

            # Use the reward table for this tier to assign rewards based on count
            # Since we can't directly index with a sum, we'll create individual rewards
            # for each course taken in this category
            reward_table = reward_tables[tier]

            # Approximate the geometric reward by giving each course a marginal reward
            # The k-th course taken gets reward[k] - reward[k-1]
            # This is a linear approximation

            # Calculate marginal rewards
            marginal_rewards = [reward_table[0]]  # First course
            for k in range(1, len(reward_table)):
                marginal_rewards.append(reward_table[k] - reward_table[k-1])

            # Use geometric series with indicator variables (not element constraint)
            if len(course_take_vars) > 0:
                # Count how many courses in this category are taken
                max_count = min(len(courses_for_req), len(course_take_vars))
                count_var = model.NewIntVar(0, max_count, f"count_{req_path.replace('.', '_')}")
                model.Add(count_var == sum(course_take_vars))

                # Calculate marginal rewards (what each additional course adds)
                marginal_rewards = []
                for k in range(1, min(max_count + 1, len(reward_table))):
                    marginal = reward_table[k] - reward_table[k-1]
                    marginal_rewards.append(marginal)

                # Create indicator variables for each threshold
                # reward[k] = marginal_rewards[k-1] if count >= k
                reward_vars = []
                for k in range(1, len(marginal_rewards) + 1):
                    indicator = model.NewBoolVar(f"{req_path.replace('.', '_')}_ge_{k}")
                    model.Add(count_var >= k).OnlyEnforceIf(indicator)
                    model.Add(count_var < k).OnlyEnforceIf(indicator.Not())

                    # Reward for this level
                    reward = model.NewIntVar(-marginal_rewards[k-1], 0, f"{req_path.replace('.', '_')}_r_{k}")
                    model.Add(reward == -marginal_rewards[k-1]).OnlyEnforceIf(indicator)
                    model.Add(reward == 0).OnlyEnforceIf(indicator.Not())

                    reward_vars.append(reward)

                # Total reward is sum of all marginal rewards
                total_reward = cp_model.LinearExpr.Sum(reward_vars) if reward_vars else 0

                # Add to objective
                if reward_vars:
                    reward_terms.append(total_reward)
                    self.category_terms[req_path] = reward_vars

        if not reward_terms:
            return cp_model.LinearExpr.constant(0)

        return cp_model.LinearExpr.Sum(reward_terms)

    def _precompute_reward_tables(self) -> dict[int, list[int]]:
        """
        Precompute reward values for each tier.
        
        Returns a dict mapping tier -> list of reward values for k=0,1,2,...,max_courses
        
        Formula: reward(k) = base × (1 - decay^k) / (1 - decay)
        """
        tables = {}

        for tier, config in self.tier_config.items():
            base = config["base"]
            decay = config["decay"]

            rewards = []
            for k in range(self.max_courses + 1):
                if k == 0:
                    reward = 0
                else:
                    reward = base * (1 - decay**k) / (1 - decay)
                rewards.append(int(round(reward)))

            tables[tier] = rewards

        return tables
