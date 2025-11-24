"""
Shared pytest fixtures and configuration for optimizer tests.

This module provides standardized test configurations to ensure
all E2E tests use consistent, realistic parameters.
"""

from dataclasses import dataclass, field

import pytest


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
    min_expected_courses: int = 30  # Minimum for any degree (includes GIRs ~17 courses)
    max_expected_courses: int = 60  # Maximum reasonable (major + GIRs)
    solver_timeout_seconds: float = 60.0

    # Degree-specific overrides for expected course counts
    # Note: These include GIRs (~17 courses) + major requirements
    degree_configs: dict[str, dict] = field(default_factory=lambda: {
        'major6-3new': {
            'min_expected_courses': 20,
            'max_expected_courses': 30,
            'description': 'Computer Science + Electrical Engineering',
        },
        'major6-2': {
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
            'max_expected_courses': 25,
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
            'max_expected_courses': 30,
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
            'max_expected_courses': 30,
            'description': 'Biological Engineering',
        },
    })

    def get_config_for_degree(self, degree_id: str) -> dict:
        """Get configuration overrides for a specific degree."""
        base_config = {
            'min_expected_courses': self.min_expected_courses,
            'max_expected_courses': self.max_expected_courses,
            'max_semesters': self.max_semesters,
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
