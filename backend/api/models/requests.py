from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Marker(BaseModel):
    courseId: str = Field(..., description="Course subject ID (e.g., '6.1200', '18.01')")
    section: int = Field(..., ge=1, le=12, description="Semester number (1-12)")
    status: Literal["pin", "banish", "solo"] = Field(..., description="User preference for this course")


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
