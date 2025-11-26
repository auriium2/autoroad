from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CourseNode(BaseModel):
    courseId: str
    semester: int
    title: str | None = None


class OptimizationJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime = Field(default_factory=datetime.now)


class OptimizationResult(BaseModel):
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID"]
    nodes: list[CourseNode]
    semesterUnits: list[int]
    solutionCount: int
    groupVars: dict[str, object] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ProgressMessage(BaseModel):
    type: Literal["progress"]
    message: str
    step: int


class SolutionMessage(BaseModel):
    type: Literal["solution"]
    step: int
    nodes: list[CourseNode]
    semesterUnits: list[int]
    groupVars: dict[str, object]


class CompleteMessage(BaseModel):
    type: Literal["complete"]
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID"]
    solutionCount: int
    warnings: list[str] = Field(default_factory=list)


class ErrorMessage(BaseModel):
    type: Literal["error"]
    error: str
    details: str | None = None


class JobStartedMessage(BaseModel):
    type: Literal["job_started"]
    job_id: str
