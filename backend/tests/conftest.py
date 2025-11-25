"""
Shared pytest fixtures and configuration for optimizer tests.

This module provides standardized test configurations to ensure
all E2E tests use consistent, realistic parameters.
"""

from dataclasses import dataclass, field
from typing import Any

import polars as pl
import pytest

from courses.prerequisites.types import PrereqNode


@dataclass
class OptimizerTestConfig:
    """
    Standard configuration for optimizer E2E tests.

    These parameters mirror production settings and ensure tests
    validate realistic scenarios, not just edge cases.
    """
    start_year: int = 2025
    max_semesters: int = 12 # 4 years * 3 semesters
    max_courses_per_semester: int = 6
    min_expected_courses: int = 10
    max_expected_courses: int = 30
    solver_timeout_seconds: float = 20.0
    min_objective_value: int = -1000
    max_objective_value: int = 1000

    # Fixed seed for CI reproducibility
    solver_random_seed: int = 42

    def configure_solver(self, solver) -> None:
        """Apply settings to a CP-SAT solver."""
        solver.parameters.max_time_in_seconds = self.solver_timeout_seconds
        solver.parameters.random_seed = self.solver_random_seed

    degree_configs: dict[str, dict[str, int | str]] = field(default_factory=lambda: {
        'major6-3new': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Computer Science + Electrical Engineering',
        },
        'major6-2new': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Electrical Engineering and Computer Science',
        },
        'major6-4': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Artificial Intelligence and Decision Making',
        },
        'major6-7': {
            'min_expected_courses': 20,
            'max_expected_courses': 35,
            'description': 'Computer Science and Molecular Biology',
        },
        'major6-9': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Computation and Cognition',
        },

        'major6-14': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Computer Science, Economics, and Data Science',
        },
        'major7': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'max_semesters': 10,  # Override: 7.19 requires longer chain
            'description': 'Biology',
        },
        'major18pm': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Mathematics',
        },
        'major18c': {
            'min_expected_courses': 20,
            'max_expected_courses': 28,
            'description': 'Mathematics with Computer Science',
        },
        'major18am': {
            'min_expected_courses': 20,
            'max_expected_courses': 28,
            'description': 'Applied Mathematics',
        },
        'major1': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Civil and Environmental Engineering',
        },
        'major2': {
            'min_expected_courses': 20,
            'max_expected_courses': 35,
            'description': 'Mechanical Engineering',
        },
        'major3': {
            'min_expected_courses': 20,
            'max_expected_courses': 35,
            'description': 'Materials Science and Engineering',
        },
        'major3a': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Materials Science and Engineering (Flexible)',
        },
        'major3c': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Archaeology and Materials',
        },
        'major4': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Architecture',
        },
        'major8': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Physics',
        },
        'major9': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Brain and Cognitive Sciences',
        },
        'major11': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Urban Studies and Planning',
        },
        'major12': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Chemical Engineering',
        },
        'major15-1': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Management Science',
        },
        'major16': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Aerospace Engineering',
        },
        'major20': {
            'min_expected_courses': 20,
            'max_expected_courses': 34,
            'description': 'Biological Engineering',
        },
    })

    def get_config_for_degree(self, degree_id: str) -> dict[str, int | str]:
        """Get configuration overrides for a specific degree."""
        base_config: dict[str, int | str] = {
            'min_expected_courses': self.min_expected_courses,
            'max_expected_courses': self.max_expected_courses,
            'max_semesters': self.max_semesters,
            'min_objective_value': self.min_objective_value,
            'max_objective_value': self.max_objective_value,
            'description': degree_id,
        }

        degree_overrides = self.degree_configs.get(degree_id, {})
        base_config.update(degree_overrides)

        return base_config


@pytest.fixture
def optimizer_config():
    """Provide standard optimizer test configuration."""
    return OptimizerTestConfig()


@pytest.fixture
def test_timeout():
    """Standard timeout for test execution."""
    return 60.0


@dataclass
class CachedCourseData:
    """Cached course data to avoid reloading for every test."""
    courses_df: pl.DataFrame
    prereq_trees: dict[int, PrereqNode]

    _requirements_cache: dict[tuple[str, ...], dict[str, Any]] = field(default_factory=dict)

    def get_requirements(self, requirement_keys: tuple[str, ...]) -> dict[str, Any]:
        """Get requirements, caching results for repeated calls."""
        if requirement_keys not in self._requirements_cache:
            from api.services.cache import get_requirements
            self._requirements_cache[requirement_keys] = get_requirements(requirement_keys)
        return self._requirements_cache[requirement_keys]


@pytest.fixture(scope="session")
def cached_course_data() -> CachedCourseData:
    """
    Session-scoped fixture providing cached course data.
    
    This avoids reloading the ~6000 courses and ~2000 prereq trees
    for every single test, significantly speeding up test runs.
    
    Usage:
        def test_something(cached_course_data):
            courses_df = cached_course_data.courses_df
            prereq_trees = cached_course_data.prereq_trees
            requirements = cached_course_data.get_requirements(('major6-3new', 'girs'))
    """
    from api.services.cache import get_courses_data, get_parsed_prerequisites

    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    prereq_trees = get_parsed_prerequisites(courses_df)

    return CachedCourseData(
        courses_df=courses_df,
        prereq_trees=prereq_trees,
    )
