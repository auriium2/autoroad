"""
Registry of available objectives with metadata and validation.
"""

from dataclasses import dataclass
from typing import Any

from . import (
    AvoidSmallClasses,
    BackloadCourses,
    ClusterCourses,
    FrontloadCourses,
    LimitClassesPerSemester,
    MaximizeCohortOverlap,
    MaximizeRating,
    MaximizeWeightedRating,
    MinimizeFinalsLoad,
    MinimizeFridayClasses,
    MinimizeMaxSemesterHours,
    MinimizeTotalHours,
    MinimizeUnits,
)
from .base import ObjectiveComponent


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


OBJECTIVES_REGISTRY: dict[str, ObjectiveMetadata] = {
    "minimize_units": ObjectiveMetadata(
        key="minimize_units",
        class_ref=MinimizeUnits,
        name="Minimize Units",
        description="Minimize the total number of units taken across all semesters",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="units",
    ),
    "avoid_small_classes": ObjectiveMetadata(
        key="avoid_small_classes",
        class_ref=AvoidSmallClasses,
        name="Avoid Small Classes",
        description="Penalize classes with very few units (e.g., seminars)",
        has_parameters=True,
        default_parameters={"min_units": 3, "penalty": 1000},
        parameter_types={"min_units": int, "penalty": int},
        category="units",
    ),
    "maximize_rating": ObjectiveMetadata(
        key="maximize_rating",
        class_ref=MaximizeRating,
        name="Maximize Rating",
        description="Prefer courses with higher ratings (penalize low-rated courses)",
        has_parameters=True,
        default_parameters={"target_rating": 6.0},
        parameter_types={"target_rating": float},
        category="ratings",
    ),
    "maximize_weighted_rating": ObjectiveMetadata(
        key="maximize_weighted_rating",
        class_ref=MaximizeWeightedRating,
        name="Maximize Weighted Rating",
        description="Prefer courses with high Bayesian-weighted ratings",
        has_parameters=True,
        default_parameters={"target_rating": 6.0, "min_votes": 10, "global_mean": None},
        parameter_types={"target_rating": float, "min_votes": int, "global_mean": (float, type(None))},
        category="ratings",
    ),
    "minimize_total_hours": ObjectiveMetadata(
        key="minimize_total_hours",
        class_ref=MinimizeTotalHours,
        name="Minimize Total Hours",
        description="Minimize total weekly hours across all semesters",
        has_parameters=True,
        default_parameters={"default_hours": 12.0},
        parameter_types={"default_hours": float},
        category="workload",
    ),
    "minimize_max_semester_hours": ObjectiveMetadata(
        key="minimize_max_semester_hours",
        class_ref=MinimizeMaxSemesterHours,
        name="Limit Semester Hours",
        description="Penalize semesters with excessive hours per week",
        has_parameters=True,
        default_parameters={"max_hours": 60.0, "penalty": 100, "default_hours": 12.0},
        parameter_types={"max_hours": float, "penalty": int, "default_hours": float},
        category="workload",
    ),
    "limit_classes_per_semester": ObjectiveMetadata(
        key="limit_classes_per_semester",
        class_ref=LimitClassesPerSemester,
        name="Limit Classes Per Semester",
        description="Penalize semesters with too many classes. Not recommended to disable this objective.",
        has_parameters=True,
        default_parameters={"max_classes": 4, "penalty": 1000},
        parameter_types={"max_classes": int, "penalty": int},
        category="workload",
    ),
    "minimize_finals_load": ObjectiveMetadata(
        key="minimize_finals_load",
        class_ref=MinimizeFinalsLoad,
        name="Minimize Finals Load",
        description="Penalize semesters with too many finals",
        has_parameters=True,
        default_parameters={"max_finals": 4, "penalty": 1000},
        parameter_types={"max_finals": int, "penalty": int},
        category="workload",
    ),
    "frontload_courses": ObjectiveMetadata(
        key="frontload_courses",
        class_ref=FrontloadCourses,
        name="Frontload Courses",
        description="Prefer taking courses in earlier semesters",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
    ),
    "backload_courses": ObjectiveMetadata(
        key="backload_courses",
        class_ref=BackloadCourses,
        name="Backload Courses",
        description="Prefer taking courses in later semesters",
        has_parameters=False,
        default_parameters={},
        parameter_types={},
        category="scheduling",
    ),
    "minimize_friday_classes": ObjectiveMetadata(
        key="minimize_friday_classes",
        class_ref=MinimizeFridayClasses,
        name="Minimize Friday Classes",
        description="Avoid courses that meet on Fridays",
        has_parameters=True,
        default_parameters={"penalty": 100},
        parameter_types={"penalty": int},
        category="scheduling",
    ),
    "cluster_courses": ObjectiveMetadata(
        key="cluster_courses",
        class_ref=ClusterCourses,
        name="Cluster Courses",
        description="Minimize time gaps between classes",
        has_parameters=True,
        default_parameters={"gap_penalty_per_hour": 50},
        parameter_types={"gap_penalty_per_hour": int},
        category="scheduling",
    ),
    "maximize_cohort_overlap": ObjectiveMetadata(
        key="maximize_cohort_overlap",
        class_ref=MaximizeCohortOverlap,
        name="Maximize Cohort Overlap",
        description="Prefer courses with higher enrollment",
        has_parameters=True,
        default_parameters={"target_enrollment": 50},
        parameter_types={"target_enrollment": int},
        category="social",
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


def get_default_objectives() -> list[tuple[str, float, dict[str, Any]]]:
    """
    Get the default objective configuration.

    Returns:
        List of (key, weight, parameters) tuples
    """
    return [
        ("minimize_units", 0.5, {}),
        ("limit_classes_per_semester", 0.3, {"max_classes": 4, "penalty": 1000}),
        ("avoid_small_classes", 0.2, {"min_units": 3, "penalty": 1000}),
    ]
