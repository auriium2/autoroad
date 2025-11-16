from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Marker(BaseModel):
    courseId: str = Field(..., description="Course subject ID (e.g., '6.1200', '18.01')")
    section: int = Field(..., ge=-2, le=11, description="Semester index (0-11 for regular, -1 for ASE, -2 for Must Take)")
    status: Literal["pin", "banish", "solo"] = Field(default="pin", description="User preference for this course")


class ObjectiveConfig(BaseModel):
    key: str = Field(..., description="Objective key (e.g., 'minimize_units')")
    weight: float = Field(..., ge=0, le=1, description="Weight for this objective (0-1)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Optional parameters for the objective")


class OptimizationConstraints(BaseModel):
    maxSemesters: int = Field(default=12, ge=1, le=12, description="Maximum number of semesters")
    maxUnitsPerSemester: int = Field(default=60, ge=1, le=100, description="Maximum units per regular semester")
    maxUnitsIAP: int = Field(default=12, ge=0, le=50, description="Maximum units for IAP semesters")
    maxHoursPerSemester: int = Field(default=60, ge=0, le=100, description="Maximum hours per semester")


class OptimizationRequest(BaseModel):
    markers: List[Marker] = Field(default_factory=list, description="User-placed course markers")
    requirements: List[str] = Field(default=["major6-3new", "girs"], description="Requirement keys to satisfy")
    constraints: OptimizationConstraints = Field(default_factory=OptimizationConstraints)
    planningYear: Optional[str] = Field(default=None, description="Planning year (e.g., '2024-2025')")
    objectives: Optional[List[ObjectiveConfig]] = Field(default=None, description="Optimization objectives (if None, uses defaults)")
