"""
Registry of available hard constraints with metadata and validation.
"""

from dataclasses import dataclass

from . import BanIAP
from .base import HardConstraint


@dataclass
class ConstraintMetadata:
    """Metadata for a hard constraint."""
    key: str
    class_ref: type[HardConstraint]
    name: str
    description: str
    category: str
    default_enabled: bool = False


CONSTRAINTS_REGISTRY: dict[str, ConstraintMetadata] = {
    "ban_iap": ConstraintMetadata(
        key="ban_iap",
        class_ref=BanIAP,
        name="Ban IAP Classes",
        description="Hard constraint: prevents optimizer from placing any classes in IAP. Your manual markers still work.",
        category="scheduling",
        default_enabled=False,
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


def instantiate_constraint(key: str) -> HardConstraint:
    """
    Create an instance of a constraint by key.

    Args:
        key: Constraint key (e.g., "ban_iap")

    Returns:
        Instantiated constraint

    Raises:
        ValueError: If key not found
    """
    metadata = get_constraint_metadata(key)
    if not metadata:
        raise ValueError(f"Unknown constraint: {key}")

    # Instantiate constraint (no parameters needed for now)
    return metadata.class_ref()


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
