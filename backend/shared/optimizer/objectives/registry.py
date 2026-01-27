"""
Registry of available objectives with metadata and validation.
"""

from dataclasses import dataclass
from typing import Any

from .base import ObjectiveComponent
from .categories import CategoryRewards
from .equivalents import DiscourageEquivalentCourses
from .ratings import PenalizeLowRatings
from .scheduling import (
    AvoidIAP,
    AvoidSpecialClasses,
    MinimumClassesPerSemester,
)
from .units import AvoidSmallClasses
from .workload import (
    LimitClassesPerSemester,
    LimitUnitsPerSemester,
    MinimizeFinalsLoad,
    MinimizeMaxSemesterHours,
)


@dataclass
class ObjectiveMetadata:
    """Metadata for an objective."""
    key: str
    class_ref: type[ObjectiveComponent]
    name: str
    short_description: str  # Brief description for search results
    description: str  # Full description for the card
    has_parameters: bool
    default_parameters: dict[str, Any]
    parameter_types: dict[str, Any]
    category: str
    default_tier: int = 2  # Default tier for this objective
    unremovable: bool = False  # If True, user cannot remove this objective


OBJECTIVES_REGISTRY: dict[str, ObjectiveMetadata] = {
    "avoid_small_classes": ObjectiveMetadata(
        key="avoid_small_classes",
        class_ref=AvoidSmallClasses,
        name="Avoid Small Classes",
        short_description="Penalize classes with very few (<3) units",
        description="Penalize taking classes with very few units. This keeps the optimizer from taking hundreds of 0 or 3 unit classes in order to 'satisfy' degree requirements.",
        has_parameters=True,
        default_parameters={"min_units": 3},
        parameter_types={"min_units": int},
        category="units",
        default_tier=4,
    ),
    "minimize_max_semester_hours": ObjectiveMetadata(
        key="minimize_max_semester_hours",
        class_ref=MinimizeMaxSemesterHours,
        name="Limit Hours Per Semester",
        short_description="Penalize semesters with too many weekly hours",
        description="Penalize semesters exceeding a weekly hours threshold. Uses in-class + out-of-class hours from course data, or the fallback value for courses missing data.",
        has_parameters=True,
        default_parameters={"hours_threshold": 60.0, "fallback_hours": 12.0, "penalty_interval": 3},
        parameter_types={"hours_threshold": float, "fallback_hours": float, "penalty_interval": int},
        category="workload",
    ),
    "limit_classes_per_semester": ObjectiveMetadata(
        key="limit_classes_per_semester",
        class_ref=LimitClassesPerSemester,
        name="Limit Classes Per Semester",
        short_description="Penalize semesters with too many classes",
        description="Penalize semesters with too many classes. Semantically, applies tier penalty for each class taken over the threshold",
        has_parameters=True,
        default_parameters={"max_classes": 4},
        parameter_types={"max_classes": int},
        category="workload",
        default_tier=4,
    ),
    "limit_units_per_semester": ObjectiveMetadata(
        key="limit_units_per_semester",
        class_ref=LimitUnitsPerSemester,
        name="Limit Units Per Semester",
        short_description="Penalize semesters exceeding a unit threshold",
        description="Penalize semesters with too many units. Semantically, penalizes semesters for having more units than a parameter you specify.",
        has_parameters=True,
        default_parameters={"max_units": 60},
        parameter_types={"max_units": int},
        category="workload",
        default_tier=3,
    ),
    "minimize_finals_load": ObjectiveMetadata(
        key="minimize_finals_load",
        class_ref=MinimizeFinalsLoad,
        name="Minimize Finals Load",
        short_description="Penalize semesters with too many finals",
        description="Penalize semesters with too many finals. Semantically, penalizes semesters for having more finals than a parameter you specify.",
        has_parameters=True,
        default_parameters={"max_finals": 2},
        parameter_types={"max_finals": int},
        category="workload",
        default_tier=1,
    ),
    "avoid_iap": ObjectiveMetadata(
        key="avoid_iap",
        class_ref=AvoidIAP,
        name="Avoid IAP Classes",
        short_description="Penalize placing classes during IAP",
        description="Penalize the optimizer placing classes during IAP.",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
        default_tier=2,
    ),
    "avoid_special_classes": ObjectiveMetadata(
        key="avoid_special_classes",
        class_ref=AvoidSpecialClasses,
        name="Avoid Special Classes",
        short_description="Penalize Concourse/STS/ES classes",
        description="Penalize taking Concourse/STS/ES classes, since most students do not take these.",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
        default_tier=2,
    ),
    "minimum_classes_per_semester": ObjectiveMetadata(
        key="minimum_classes_per_semester",
        class_ref=MinimumClassesPerSemester,
        name="Minimum Classes Per Semester",
        short_description="Penalize semesters with too few classes",
        description="Penalize semesters with too few classes to prevent single-class semesters.",
        has_parameters=True,
        default_parameters={"min_classes": 2},
        parameter_types={"min_classes": int},
        category="workload",
        default_tier=2,
    ),
    "category_rewards": ObjectiveMetadata(
        key="category_rewards",
        class_ref=CategoryRewards,
        name="Category Rewards",
        short_description="Reward courses in priority categories",
        description="Reward taking courses in priority categories with diminishing returns. Built-in objective of autoroad for degree requirement rewards.",
        has_parameters=True,
        default_parameters={"max_courses_per_category": 20, "decay_rate": 0.70},
        parameter_types={"max_courses_per_category": int, "decay_rate": float},
        category="categories",
        default_tier=2,
        unremovable=True,
    ),
    "discourage_equivalent_courses": ObjectiveMetadata(
        key="discourage_equivalent_courses",
        class_ref=DiscourageEquivalentCourses,
        name="Discourage Equivalent Courses",
        short_description="Penalize taking multiple equivalent courses",
        description="Discourage taking multiple equivalent courses using tier-based penalties.",
        has_parameters=True,
        default_parameters={"custom_equivalencies": {"6.100A": ["6.100L"], "6.100L": ["6.100A"]}},
        parameter_types={"custom_equivalencies": dict},
        category="scheduling",
        default_tier=4,
        unremovable=True,
    ),
    "penalize_low_ratings": ObjectiveMetadata(
        key="penalize_low_ratings",
        class_ref=PenalizeLowRatings,
        name="Penalize Low Ratings",
        short_description="Penalize courses with low ratings",
        description="Penalize courses with ratings below a threshold.",
        has_parameters=True,
        default_parameters={"threshold": 5.5, "use_imdb": False},
        parameter_types={"threshold": float, "use_imdb": bool},
        category="ratings",
        default_tier=2,
    ),
}


def get_objective_metadata(key: str) -> ObjectiveMetadata | None:
    """Get metadata for an objective by key."""
    return OBJECTIVES_REGISTRY.get(key)


def get_all_objectives() -> list[ObjectiveMetadata]:
    """Get all available objectives."""
    return list(OBJECTIVES_REGISTRY.values())


def get_objectives_by_category(category: str) -> list[ObjectiveMetadata]:
    """Get objectives by category."""
    return [obj for obj in OBJECTIVES_REGISTRY.values() if obj.category == category]


def instantiate_objective(key: str, parameters: dict[str, Any] | None = None) -> ObjectiveComponent:
    """
    Create an instance of an objective by key.

    Args:
        key: Objective key (e.g., "minimize_units")
        parameters: Optional parameters to pass to constructor

    Returns:
        Instantiated objective

    Raises:
        ValueError: If key not found or parameters invalid
    """
    metadata = get_objective_metadata(key)
    if not metadata:
        raise ValueError(f"Unknown objective: {key}")

    # Use default parameters if not provided
    if parameters is None:
        parameters = metadata.default_parameters.copy()
    else:
        # Merge with defaults
        params = metadata.default_parameters.copy()
        params.update(parameters)
        parameters = params

    # Instantiate with parameters
    try:
        return metadata.class_ref(**parameters)
    except TypeError as e:
        raise ValueError(f"Invalid parameters for {key}: {e}")


def get_default_objectives() -> list[tuple[str, dict[str, Any]]]:
    """
    Get the default objective configuration.

    Returns:
        List of (key, parameters) tuples
    """
    return [
        ("limit_classes_per_semester", {"max_classes": 4}),
        ("avoid_small_classes", {"min_units": 3}),
        ("avoid_special_classes", {}),
        ("category_rewards", {"max_courses_per_category": 20, "decay_rate": 0.70}),
        ("discourage_equivalent_courses", {"custom_equivalencies": {"6.100A": ["6.100L"], "6.100L": ["6.100A"]}}),
    ]
