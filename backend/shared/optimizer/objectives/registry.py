"""
Registry of available objectives with metadata and validation.
"""

from dataclasses import dataclass
from typing import Any

from .base import ObjectiveComponent
from .categories import CategoryRewards
from .equivalents import DiscourageEquivalentCourses
from .scheduling import AvoidIAP, MinimizeFridayClasses, MinimumClassesPerSemester
from .units import AvoidSmallClasses, MinimizeUnits
from .workload import LimitClassesPerSemester, LimitUnitsPerSemester, MinimizeFinalsLoad, MinimizeMaxSemesterHours


@dataclass
class ObjectiveMetadata:
    """Metadata for an objective."""
    key: str
    class_ref: type[ObjectiveComponent]
    name: str
    description: str
    has_parameters: bool
    default_parameters: dict[str, Any]
    parameter_types: dict[str, Any]
    category: str
    default_tier: int = 2  # Default tier for this objective
    unremovable: bool = False  # If True, user cannot remove this objective


OBJECTIVES_REGISTRY: dict[str, ObjectiveMetadata] = {
    # Note: minimize_units is the core objective and is NOT user-selectable
    # It is always active and forms the base of the optimization
    "avoid_small_classes": ObjectiveMetadata(
        key="avoid_small_classes",
        class_ref=AvoidSmallClasses,
        name="Avoid Small Classes",
        description="Penalize taking classes with very few units. This is used to stop the optimizer from taking hundreds of 0 or 3 unit classes in order to 'satisfy' degree requirements",
        has_parameters=True,
        default_parameters={"min_units": 3},
        parameter_types={"min_units": int},
        category="units",
        default_tier=4,
    ),
    "minimize_max_semester_hours": ObjectiveMetadata(
        key="minimize_max_semester_hours",
        class_ref=MinimizeMaxSemesterHours,
        name="Limit Semester Hours",
        description="Penalize semesters with excessive hours per week (tier-based, per 3 hours)",
        has_parameters=True,
        default_parameters={"max_hours": 60.0, "default_hours": 12.0},
        parameter_types={"max_hours": float, "default_hours": float},
        category="workload",
    ),
    "limit_classes_per_semester": ObjectiveMetadata(
        key="limit_classes_per_semester",
        class_ref=LimitClassesPerSemester,
        name="Limit Classes Per Semester",
        description="Penalize semesters with too many classes. This keeps the optimizer from stacking hundreds of classes in one semester.",
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
        description="Penalize semesters with too many units (tier-based, per 3 units)",
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
        description="Penalize semesters with too many finals",
        has_parameters=True,
        default_parameters={"max_finals": 4},
        parameter_types={"max_finals": int},
        category="workload",
        default_tier=1,
    ),
    "minimize_friday_classes": ObjectiveMetadata(
        key="minimize_friday_classes",
        class_ref=MinimizeFridayClasses,
        name="Minimize Friday Classes",
        description="Give yourself a three day weekend",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
        default_tier=1,
    ),
    "avoid_iap": ObjectiveMetadata(
        key="avoid_iap",
        class_ref=AvoidIAP,
        name="Avoid IAP Classes",
        description="Penalize the optimizer placing classes during IAP. This does not penalize any classes that you place yourself inside of iap.",
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
        description="Penalize semesters with too few classes to prevent single-class semesters (Autoroad likes producing these, and some students like having these. Remove as needed)",
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
        description="Reward taking courses in priority categories with diminishing returns. Built in feature of autoroad/degree requirement rewards",
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
        description="Discourage taking multiple equivalent courses (e.g., 18.01 and ES.1801) using tier-based penalties",
        has_parameters=True,
        default_parameters={"custom_equivalencies": {"6.100A": ["6.100L"], "6.100L": ["6.100A"]}},
        parameter_types={"custom_equivalencies": dict},
        category="scheduling",
        default_tier=4,
        unremovable=True,
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
        ("minimum_classes_per_semester", {"min_classes": 2}),
        ("category_rewards", {"max_courses_per_category": 20, "decay_rate": 0.70}),
        ("discourage_equivalent_courses", {"custom_equivalencies": {"6.100A": ["6.100L"], "6.100L": ["6.100A"]}}),
    ]
