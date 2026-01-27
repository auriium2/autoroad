import json
from typing import Any

import sentry_sdk
from fastapi import APIRouter, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


class BugReportRequest(BaseModel):
    title: str = "Bug Report"
    description: str
    debug_info: dict[str, Any]


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
                "version": body.debug_info.get("version"),
                "user_agent": body.debug_info.get("userAgent"),
                "timestamp": body.debug_info.get("timestamp"),
                "requirements": body.debug_info.get("requirements"),
                "requirement_sources": body.debug_info.get("requirementSources"),
                "last_optimization_status": body.debug_info.get("lastOptimizationStatus"),
                "last_cost_breakdown": body.debug_info.get("lastCostBreakdown"),
            })

            # Markers and objectives as contexts
            if body.debug_info.get("markers"):
                scope.set_context("markers", {"data": body.debug_info["markers"]})
            if body.debug_info.get("objectives"):
                scope.set_context("objectives", {"data": body.debug_info["objectives"]})

            # Console logs as breadcrumbs
            if body.debug_info.get("consoleLogs"):
                for log in body.debug_info["consoleLogs"][-50:]:
                    scope.add_breadcrumb(
                        category="console",
                        message=log.get("message", "")[:500],
                        level=log.get("level", "info"),
                        timestamp=log.get("timestamp"),
                    )

            # Attach road data as JSON files
            if body.debug_info.get("markersRoadData"):
                scope.add_attachment(
                    bytes=json.dumps(body.debug_info["markersRoadData"], indent=2).encode(),
                    filename="markers.road.json",
                    content_type="application/json",
                )
            if body.debug_info.get("optimizerRoadData"):
                scope.add_attachment(
                    bytes=json.dumps(body.debug_info["optimizerRoadData"], indent=2).encode(),
                    filename="generated.road.json",
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
