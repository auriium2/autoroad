"""
MIT AutoRoad Course Analyzer Module

A module for analyzing and optimizing course selections based on degree requirements
using constraint programming.
"""

from .core import export_take_blocks_to_road, setup_and_solve
from .data_fetcher import fetch_course_data, fetch_requirement
from .prerequisite_handler import add_prerequisite_constraints
from .requirement_handler import add_requirement_constraints, generic_satisfied
