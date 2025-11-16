"""
Composable objective functions for course schedule optimization.

This module provides a flexible system for building optimization objectives
by combining different components with weights.
"""

from .base import ObjectiveComponent, ObjectiveContext
from .builder import ObjectiveBuilder
from .ratings import MaximizeRating, MaximizeWeightedRating
from .scheduling import BackloadCourses, ClusterCourses, FrontloadCourses, MinimizeFridayClasses
from .social import MaximizeCohortOverlap
from .units import MinimizeUnits
from .workload import MinimizeFinalsLoad, MinimizeMaxSemesterHours, MinimizeTotalHours

__all__ = [
    # Base classes
    'ObjectiveComponent',
    'ObjectiveContext',
    'ObjectiveBuilder',

    # Objectives
    'MinimizeUnits',
    'MaximizeRating',
    'MaximizeWeightedRating',
    'MinimizeTotalHours',
    'MinimizeMaxSemesterHours',
    'MinimizeFinalsLoad',
    'FrontloadCourses',
    'BackloadCourses',
    'MinimizeFridayClasses',
    'ClusterCourses',
    'MaximizeCohortOverlap',
]
