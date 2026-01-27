"""
Registry of available hard constraints with metadata and validation.
"""

from dataclasses import dataclass, field
from typing import Any

from .base import HardConstraint
from .conflicts import NoScheduleConflicts
from .scheduling import BanIAP, BanPrefix, ScheduleFreeTime


@dataclass
class ConstraintMetadata:
    """Metadata for a hard constraint."""
    key: str
    class_ref: type[HardConstraint]
    name: str
    short_description: str  # Brief description for search results
    description: str  # Full description for the card
    category: str
    default_enabled: bool = False
    has_parameters: bool = False
    default_parameters: dict[str, Any] = field(default_factory=dict)
    parameter_types: dict[str, Any] = field(default_factory=dict)
    beta: bool = False


CONSTRAINTS_REGISTRY: dict[str, ConstraintMetadata] = {
    "ban_iap": ConstraintMetadata(
        key="ban_iap",
        class_ref=BanIAP,
        name="Ban IAP Classes",
        short_description="Prevent classes during IAP",
        description="Hard constraint: prevents optimizer from placing any classes in IAP. Your manual markers still work.",
        category="scheduling",
        default_enabled=False,
    ),
    "no_schedule_conflicts": ConstraintMetadata(
        key="no_schedule_conflicts",
        class_ref=NoScheduleConflicts,
        name="No Schedule Conflicts",
        short_description="Prevent overlapping lecture times",
        description="Hard constraint: prevents taking courses with overlapping lecture times. Uses Hydrant schedule data.",
        category="scheduling",
        default_enabled=True,
        has_parameters=True,
        default_parameters={"extrapolate": False},
        parameter_types={"extrapolate": bool},
        beta=True,
    ),
    "ban_prefix": ConstraintMetadata(
        key="ban_prefix",
        class_ref=BanPrefix,
        name="Ban Classes by Prefix",
        short_description="Prevent classes with a course number prefix",
        description="Hard constraint: prevents taking any classes with a specific course number prefix.",
        category="scheduling",
        default_enabled=False,
        has_parameters=True,
        default_parameters={"prefix": "21M"},
        parameter_types={"prefix": str},
    ),
    "schedule_free_time": ConstraintMetadata(
        key="schedule_free_time",
        class_ref=ScheduleFreeTime,
        name="Schedule Free Time",
        short_description="Block off time slots for no classes",
        description="Block off time slots where you don't want classes. Courses with required sections during blocked times will be excluded.",
        category="scheduling",
        default_enabled=False,
        has_parameters=True,
        default_parameters={"blocked_slots": [], "extrapolate": False},
        parameter_types={"blocked_slots": list, "extrapolate": bool},
        beta=True,
    ),
}


def get_constraint_metadata(key: str) -> ConstraintMetadata | None:
    """Get metadata for a constraint by key."""
    return CONSTRAINTS_REGISTRY.get(key)


def get_all_constraints() -> list[ConstraintMetadata]:
    """Get all available constraints."""
    return list(CONSTRAINTS_REGISTRY.values())


def get_constraints_by_category(category: str) -> list[ConstraintMetadata]:
    """Get constraints by category."""
    return [c for c in CONSTRAINTS_REGISTRY.values() if c.category == category]


def instantiate_constraint(key: str, parameters: dict[str, Any] | None = None) -> HardConstraint:
    """
    Create an instance of a constraint by key.

    Args:
        key: Constraint key (e.g., "ban_iap")
        parameters: Optional parameters to pass to constructor

    Returns:
        Instantiated constraint

    Raises:
        ValueError: If key not found or parameters invalid
    """
    metadata = get_constraint_metadata(key)
    if not metadata:
        raise ValueError(f"Unknown constraint: {key}")

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
        if metadata.has_parameters:
            return metadata.class_ref(**parameters)
        else:
            return metadata.class_ref()
    except TypeError as e:
        raise ValueError(f"Invalid parameters for {key}: {e}")


def get_default_constraints() -> list[str]:
    """
    Get the default constraint configuration.

    Returns:
        List of constraint keys that are enabled by default
    """
    return [
        key for key, meta in CONSTRAINTS_REGISTRY.items()
        if meta.default_enabled
    ]
