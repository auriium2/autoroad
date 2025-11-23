"""
Composable objective functions for course schedule optimization.

This module provides a flexible system for building optimization objectives
by combining different components with weights.
"""

from .base import ObjectiveComponent, ObjectiveContext
from .builder import ObjectiveBuilder
from .scheduling import AvoidIAP, MinimizeFridayClasses, MinimumClassesPerSemester
from .units import AvoidSmallClasses, MinimizeUnits
from .workload import (
    LimitClassesPerSemester,
    LimitUnitsPerSemester,
    MinimizeFinalsLoad,
    MinimizeMaxSemesterHours,
)

__all__ = [
    # Base classes
    'ObjectiveComponent',
    'ObjectiveContext',
    'ObjectiveBuilder',

    # Objectives
    'MinimizeUnits',
    'AvoidSmallClasses',
    'MinimizeMaxSemesterHours',
    'LimitClassesPerSemester',
    'LimitUnitsPerSemester',
    'MinimizeFinalsLoad',
    'MinimizeFridayClasses',
    'AvoidIAP',
    'MinimumClassesPerSemester',
]
