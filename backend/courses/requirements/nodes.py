"""
Re-export all node types from types.py.

Import side effect: registers all dispatch handlers via the handlers module.
"""

from courses.requirements.types import (
    CI,
    GIR,
    HASS,
    AllGroup,
    AnyGroup,
    CIType,
    ConnectionType,
    Course,
    DistinctThreshold,
    GIRCode,
    Group,
    HASSCategory,
    Leaf,
    Node,
    PlainString,
    SubjectThresholdGroup,
    ThresholdType,
    UnitThresholdGroup,
)

# Import handlers to register them with the dispatch system
from optimizer.requirements import handlers as _handlers  # noqa: F401

__all__ = [
    "Node", "Leaf", "Group",
    "Course", "GIR", "GIRCode", "HASS", "HASSCategory", "CI", "CIType", "PlainString",
    "AllGroup", "AnyGroup", "SubjectThresholdGroup", "UnitThresholdGroup",
    "DistinctThreshold", "ThresholdType", "ConnectionType",
]
