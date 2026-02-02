from typing import Literal

from pydantic import BaseModel, Field


# markers carry the same zero indexing that the frontend does! do not try to place 1 indexed semesters here!
class Marker(BaseModel):
    courseId: str = Field(..., description="Course subject ID (e.g., '6.1200', '18.01')")
    section: int = Field(..., ge=-2, le=11, description="Semester index (0-11 for regular, -1 for ASE, -2 for Must Take)")
    status: Literal["pin", "banish", "override"] = Field(default="pin", description="User preference for this course")


class ObjectiveConfig(BaseModel):
    key: str = Field(..., description="Objective key (e.g., 'minimize_units')")
    parameters: dict[str, object] = Field(default_factory=dict, description="Optional parameters for the objective")


class ConstraintConfig(BaseModel):
    key: str = Field(..., description="Constraint key (e.g., 'ban_prefix')")
    parameters: dict[str, object] = Field(default_factory=dict, description="Optional parameters for the constraint")


class OptimizationRequest(BaseModel):
    markers: list[Marker] = Field(default_factory=list, description="User-placed course markers")
    requirements: list[str] = Field(default=["major6-3new", "girs"], description="Requirement keys to satisfy")
    maxSemesters: int = Field(default=12, ge=1, le=12, description="Maximum number of semesters to plan")
    planningYear: str | None = Field(default=None, description="Planning year (e.g., '2024-2025')")
    objectives: list[ObjectiveConfig] | None = Field(default=None, description="Optimization objectives (if None, uses defaults)")
    hardConstraints: list[ConstraintConfig] = Field(default_factory=list, description="Hard constraints to enable")
    lockPastSemesters: bool = Field(default=False, description="Prevent optimizer from modifying semesters that have already passed")
    requirementTiers: dict[str, int] = Field(default_factory=dict, description="Tier priorities for requirement tree nodes (0-3)")
    objectiveTiers: dict[str, int] = Field(default_factory=dict, description="Tier priorities for objectives (1-4)")
    requirementSources: dict[str, Literal["canonical", "beta"]] = Field(default_factory=dict, description="Source preference for requirements with both versions")
    customEquivalencies: dict[str, list[str]] = Field(default_factory=dict, description="Custom course equivalencies (e.g., {'6.100A': ['6.100L']})")
