"""
Registry of available objectives with metadata and validation.
"""

from dataclasses import dataclass
from typing import Any

from .base import ObjectiveComponent
from .categories import CategoryRewards
from .equivalents import DiscourageEquivalentCourses
from .ratings import AvoidLowRatings
from .scheduling import (
    AvoidClassesWithPrefix,
    AvoidHASSClasses,
    AvoidIAP,
    AvoidSpecialClasses,
    AvoidSpecialTopics,
    MinimumClassesPerSemester,
)
from .workload import (
    LimitClassesPerSemester,
    LimitFinalsPerSemester,
    LimitHoursPerSemester,
    LimitUnitsPerSemester,
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
    "limit_hours_per_semester": ObjectiveMetadata(
        key="limit_hours_per_semester",
        class_ref=LimitHoursPerSemester,
        name="Limit Hours Per Semester",
        short_description="Discourages semesters with more than n sum weekly hours",
        description="Discourages semesters with more than n sum weekly hours. Applies a fractional penalty for every x hours over the threshold.",
        has_parameters=True,
        default_parameters={"hours_threshold": 60.0, "fallback_hours": 12.0, "penalty_interval": 3},
        parameter_types={"hours_threshold": float, "fallback_hours": float, "penalty_interval": int},
        category="workload",
    ),
    "limit_classes_per_semester": ObjectiveMetadata(
        key="limit_classes_per_semester",
        class_ref=LimitClassesPerSemester,
        name="Average Classes Per Semester",
        short_description="Discourages taking more than n classes per semester",
        description="Discourages taking more than n classes per semester. Tells the optimizer what a normal semester should look like, though the optimizer can and wil exceed this number to achieve your degree. Not recommended to set this higher than 4 or 5.",
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
        short_description="Discourages semesters with more than n units per semester",
        description="Discourages semesters with more than n units per semester. Applies a fractional penalty for every 3 units over the threshold.",
        has_parameters=True,
        default_parameters={"max_units": 60},
        parameter_types={"max_units": int},
        category="workload",
        default_tier=3,
    ),
    "limit_finals_per_semester": ObjectiveMetadata(
        key="limit_finals_per_semester",
        class_ref=LimitFinalsPerSemester,
        name="Limit Finals Per Semester",
        short_description="Discourages taking more than n finals per semester",
        description="Discourages taking more than n finals per semester. Applies a penalty for each final over the threshold.",
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
        short_description="Discourages the optimizer from placing classes in IAP",
        description="Discourages the optimizer from placing classes in IAP. Applies a penalty for each class in IAP.",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
        default_tier=2,
    ),
    "avoid_special_classes": ObjectiveMetadata(
        key="avoid_special_classes",
        class_ref=AvoidSpecialClasses,
        name="Avoid Placing Special Classes",
        short_description="Discourages automatic placement of Concourse/STS/ES/Research/Thesis classes",
        description="Discourages automatic placement of Concourse/STS/ES/Research/Thesis classes. These should be added manually (use markers).",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
        default_tier=2,
    ),
    "avoid_special_topics": ObjectiveMetadata(
        key="avoid_special_topics",
        class_ref=AvoidSpecialTopics,
        name="Avoid Placing Special Topics",
        short_description="Discourages automatic placement of special topics courses (X.SYYY)",
        description="Discourages automatic placement of special topics courses like 6.S040 or 18.S097. These should be added manually (use markers).",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
        default_tier=2,
    ),
    "avoid_hass_classes": ObjectiveMetadata(
        key="avoid_hass_classes",
        class_ref=AvoidHASSClasses,
        name="Avoid HASS Classes",
        short_description="Discourages placing HASS classes",
        description="Discourages placing HASS classes. Applies a penalty for every hass class on the board. If you live in Simmons or Next, you'll like this one.",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
        default_tier=2,
    ),
    "avoid_classes_with_prefix": ObjectiveMetadata(
        key="avoid_classes_with_prefix",
        class_ref=AvoidClassesWithPrefix,
        name="Avoid Classes with Prefix",
        short_description="Discourages taking classes matching specified prefixes",
        description="Penalize classes that start with specified prefixes. Use this to avoid entire departments or course types (e.g., ['21M', '21W'] to avoid music and writing classes).",
        has_parameters=True,
        default_parameters={"prefixes": ['21T']},
        parameter_types={"prefixes": list},
        category="scheduling",
        default_tier=2,
    ),
    "minimum_classes_per_semester": ObjectiveMetadata(
        key="minimum_classes_per_semester",
        class_ref=MinimumClassesPerSemester,
        name="Minimum Classes Per Semester",
        short_description="(Legacy) Balances your workload, counterweighs Limit Classes",
        description="Discourages semesters with too few classes to prevent single-class semesters. Debatably useful and a holdover from earlier formulations of the backend code.",
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
        description="Discourage taking multiple equivalent courses using tier-based penalties. Functionally causes classes to behave equivalently as prerequisites. Built-in objective of autoroad to allow the user to handle petitions.",
        has_parameters=True,
        default_parameters={"custom_equivalencies": {"6.100A": ["6.100L"], "6.100L": ["6.100A"]}},
        parameter_types={"custom_equivalencies": dict},
        category="scheduling",
        default_tier=4,
        unremovable=True,
    ),
    "avoid_low_ratings": ObjectiveMetadata(
        key="avoid_low_ratings",
        class_ref=AvoidLowRatings,
        name="Avoid Low Ratings",
        short_description="Discourages taking courses with less than n rating.",
        description="Discourages taking courses with less than n rating. Applies a fractional penalty for every 0.1 rating below the threshold you specify. IMDB mode weights the ratings by users taking them before applying penalties.",
        has_parameters=True,
        default_parameters={"threshold": 5.5, "use_imdb": False},
        parameter_types={"threshold": float, "use_imdb": bool},
        category="ratings",
        default_tier=2,
    ),
}


def get_objective_metadata(key: str) -> ObjectiveMetadata | None:
    return OBJECTIVES_REGISTRY.get(key)


def get_all_objectives() -> list[ObjectiveMetadata]:
    return list(OBJECTIVES_REGISTRY.values())


def get_objectives_by_category(category: str) -> list[ObjectiveMetadata]:
    return [obj for obj in OBJECTIVES_REGISTRY.values() if obj.category == category]


def instantiate_objective(key: str, parameters: dict[str, Any] | None = None) -> ObjectiveComponent:
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
        ("avoid_special_classes", {}),
        ("category_rewards", {"max_courses_per_category": 20, "decay_rate": 0.70}),
        ("discourage_equivalent_courses", {"custom_equivalencies": {"6.100A": ["6.100L"], "6.100L": ["6.100A"]}}),
    ]
