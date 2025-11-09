"""
MIT AutoRoad Course Analyzer Module

A module for analyzing and optimizing course selections based on degree requirements
using constraint programming.
"""

from .core import setup_and_solve, export_take_blocks_to_road
from .data_fetcher import fetch_course_data, fetch_requirement
from .requirement_handler import add_requirement_constraints, generic_satisfied
from .prerequisite_handler import add_prerequisite_constraints