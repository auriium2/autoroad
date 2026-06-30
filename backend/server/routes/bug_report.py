import json
from typing import Any

import sentry_sdk
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


class ConsoleLogEntry(BaseModel):
    message: str = Field(default="", max_length=1000)
    level: str = Field(default="info", max_length=50)
    timestamp: str | float | int | None = Field(default=None)


class DebugInfo(BaseModel):
    version: str | None = Field(default=None, max_length=100)
    userAgent: str | None = Field(default=None, max_length=1000)
    timestamp: str | float | int | None = Field(default=None)
    lastOptimizationStatus: str | None = Field(default=None, max_length=100)
    lastCostBreakdown: dict[str, Any] | None = Field(default=None)
    markers: list[Any] | None = Field(default=None)
    optimizerNodes: list[Any] | None = Field(default=None)
    consoleLogs: list[ConsoleLogEntry] | None = Field(default=None)
    aroadData: dict[str, Any] | None = Field(default=None)


class BugReportRequest(BaseModel):
    title: str = Field(default="Bug Report", min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=10000)
    debug_info: DebugInfo


class BugReportResponse(BaseModel):
    success: bool
    sentry_event_id: str | None = None
    error: str | None = None


@router.post("/bug-report", response_model=BugReportResponse)
@limiter.limit("5/minute")
async def create_bug_report(request: Request, body: BugReportRequest) -> BugReportResponse:
    """Capture bug report in Sentry with full context and attachments."""

    try:
        with sentry_sdk.push_scope() as scope:
            # User's description
            scope.set_context("bug_report", {
                "title": body.title,
                "description": body.description,
            })

            # App state
            scope.set_context("app_state", {
                "version": body.debug_info.version,
                "user_agent": body.debug_info.userAgent,
                "timestamp": body.debug_info.timestamp,
                "last_optimization_status": body.debug_info.lastOptimizationStatus,
                "last_cost_breakdown": body.debug_info.lastCostBreakdown,
            })

            # Markers and optimizer nodes as contexts
            if body.debug_info.markers:
                scope.set_context("markers", {"data": body.debug_info.markers})
            if body.debug_info.optimizerNodes:
                scope.set_context("optimizer_nodes", {"data": body.debug_info.optimizerNodes})

            # Console logs as breadcrumbs
            if body.debug_info.consoleLogs:
                for log in body.debug_info.consoleLogs[-50:]:
                    scope.add_breadcrumb(
                        category="console",
                        message=log.message[:500],
                        level=log.level,
                        timestamp=log.timestamp,
                    )

            # Attach full .aroad snapshot
            if body.debug_info.aroadData:
                scope.add_attachment(
                    bytes=json.dumps(body.debug_info.aroadData, indent=2).encode(),
                    filename="snapshot.aroad",
                    content_type="application/json",
                )

            sentry_event_id = sentry_sdk.capture_message(
                f"Bug Report: {body.title}",
                level="error",
            )

        return BugReportResponse(
            success=True,
            sentry_event_id=sentry_event_id,
        )

    except Exception as e:
        return BugReportResponse(
            success=False,
            error=f"Failed to submit bug report: {str(e)}",
        )
