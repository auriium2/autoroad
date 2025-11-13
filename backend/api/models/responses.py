from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CourseNode(BaseModel):
    courseId: str
    semester: int
    title: Optional[str] = None


class OptimizationJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime = Field(default_factory=datetime.now)


class OptimizationResult(BaseModel):
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID"]
    nodes: List[CourseNode]
    semesterUnits: List[int]
    solutionCount: int
    groupVars: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class ProgressMessage(BaseModel):
    type: Literal["progress"]
    message: str
    step: int


class SolutionMessage(BaseModel):
    type: Literal["solution"]
    step: int
    nodes: List[CourseNode]
    semesterUnits: List[int]
    groupVars: Dict[str, Any]


class CompleteMessage(BaseModel):
    type: Literal["complete"]
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID"]
    solutionCount: int
    warnings: List[str] = Field(default_factory=list)


class ErrorMessage(BaseModel):
    type: Literal["error"]
    error: str
    details: Optional[str] = None


class JobStartedMessage(BaseModel):
    type: Literal["job_started"]
    job_id: str
