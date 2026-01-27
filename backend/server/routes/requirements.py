"""
Requirements API routes - provides parsed requirement trees and progress calculation.
"""

import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger("uvicorn.error")

from shared.optimizer.constraints.registry import get_all_constraints
from shared.optimizer.objectives.registry import get_all_objectives

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

REQUIREMENTS_DIR = Path(__file__).parent.parent.parent / "requirements"
FIREROAD_BASE_URL = "https://fireroad.mit.edu"


class SelectedSubject(BaseModel):
    subject_id: str
    title: str | None = None
    units: int | None = None
    semester: int | None = None


class ProgressRequest(BaseModel):
    selectedSubjects: list[SelectedSubject] = []
    coursesOfStudy: list[str] = []
    progressAssertions: dict[str, object] = {}


def _load_local_requirements() -> dict[str, dict[str, str]]:
    """Load requirements from local files."""
    local_reqs: dict[str, dict[str, str]] = {}
    if REQUIREMENTS_DIR.exists():
        for ext in [".fireroad", ".txt"]:
            for path in REQUIREMENTS_DIR.glob(f"*{ext}"):
                key = path.stem
                if key in local_reqs:
                    continue
                try:
                    content = path.read_text()
                    lines = content.split("\n")
                    if len(lines) >= 1:
                        header_parts = lines[0].split("#,#")
                        short = header_parts[0] if header_parts else key
                        medium = header_parts[1] if len(header_parts) > 1 else short
                        title = header_parts[2] if len(header_parts) > 2 else medium
                        local_reqs[key] = {
                            "short-title": short,
                            "medium-title": medium,
                            "title": title,
                            "title-no-degree": header_parts[3] if len(header_parts) > 3 else title,
                        }
                        # Find description: first non-empty line after header that doesn't look like a requirement definition
                        for line in lines[1:]:
                            stripped = line.strip()
                            if stripped and not stripped.startswith(('#', '/')) and ':=' not in stripped:
                                local_reqs[key]["description"] = stripped
                                break
                except Exception as e:
                    logger.warning("Failed to parse %s: %s", path, e)
    return local_reqs


async def _fetch_all_requirements() -> dict[str, Any]:
    """Fetch and merge requirements from Fireroad and local files."""
    fireroad_reqs: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(f"{FIREROAD_BASE_URL}/requirements/list_reqs")
            resp.raise_for_status()
            fireroad_reqs = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch Fireroad list: %s", e)

    local_reqs = _load_local_requirements()

    result: dict[str, Any] = {}
    for key, metadata in fireroad_reqs.items():
        result[key] = {
            **metadata,
            "source": "canonical",
            "hasBothVersions": key in local_reqs,
        }
    for key, metadata in local_reqs.items():
        if key not in fireroad_reqs:
            result[key] = {
                **metadata,
                "source": "beta",
                "hasBothVersions": False,
            }
    return result


@router.get("/requirements/list")
@limiter.limit("30/minute")
async def list_requirements(request: Request):
    """
    List all available requirements, merging Fireroad's list with local beta files.
    """
    return await _fetch_all_requirements()


@router.get("/requirements/get/{key}")
@limiter.limit("60/minute")
async def get_requirement_json(request: Request, key: str, source: str = "canonical"):
    """Get a parsed requirement definition."""
    from shared.services.cache import fetch_requirement

    try:
        data = await fetch_requirement(key, source)
        return data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Requirement '{key}' not found")
        logger.exception("Error fetching requirement %s: %s", key, e)
        raise HTTPException(status_code=502, detail="Failed to fetch requirement from upstream")
    except Exception as e:
        logger.exception("Error fetching requirement %s: %s", key, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/requirements/progress/{key}")
@limiter.limit("30/minute")
async def get_requirement_progress(request: Request, key: str, body: ProgressRequest, source: str = "canonical"):
    """
    Get requirement progress for a list of selected subjects.

    Uses our own progress calculator with the distinct_threshold bug fixed.
    """
    from shared.courses.requirements.parser import parse_fireroad_response
    from shared.courses.requirements.progress import compute_progress, progress_to_json
    from shared.services.cache import fetch_requirement, get_courses_data

    try:
        # Get requirement data and parse into nodes
        req_data = await fetch_requirement(key, source)
        root_node = parse_fireroad_response(req_data)

        # Get course data for satisfaction checking
        courses_data = await get_courses_data()
        id2course = {c["subject_id"]: c for c in courses_data}

        # Compute progress - extract subject_ids from the objects
        selected_set = {s.subject_id for s in body.selectedSubjects}
        result = compute_progress(root_node, selected_set, id2course)

        # Convert to JSON format
        output = progress_to_json(result, root_node)

        # Add top-level metadata
        for field in ["title", "medium-title", "short-title", "title-no-degree", "description"]:
            if field in req_data:
                output[field] = req_data[field]
        output["list-id"] = key

        return output
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Requirement '{key}' not found")
        logger.exception("Error calculating progress for %s: %s", key, e)
        raise HTTPException(status_code=502, detail="Failed to fetch requirement from upstream")
    except Exception as e:
        logger.exception("Error calculating progress for %s: %s", key, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parameters/search")
@limiter.limit("60/minute")
async def search_parameters(
    request: Request,
    q: str = Query("", description="Search query"),
    limit: int = Query(30, ge=1, le=100),
    exclude_requirements: str = Query("", description="Comma-separated requirement keys to exclude"),
    exclude_objectives: str = Query("", description="Comma-separated objective keys to exclude"),
    exclude_constraints: str = Query("", description="Comma-separated constraint keys to exclude"),
):
    """
    Unified search across requirements, objectives, and constraints.
    """
    query = q.lower()
    excluded_reqs = set(exclude_requirements.split(",")) if exclude_requirements else set()
    excluded_objs = set(exclude_objectives.split(",")) if exclude_objectives else set()
    excluded_cons = set(exclude_constraints.split(",")) if exclude_constraints else set()

    # Fetch requirements list
    all_requirements = await _fetch_all_requirements()

    # Get objectives and constraints
    all_objectives = get_all_objectives()
    all_constraints = get_all_constraints()

    objectives: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []
    concentrations: list[dict[str, Any]] = []
    degrees: list[dict[str, Any]] = []

    # Process objectives
    for obj in all_objectives:
        if obj.key in excluded_objs:
            continue
        searchable = f"{obj.key} {obj.name} {obj.description} {obj.category}".lower()
        if not query or query in searchable:
            objectives.append({
                "type": "objective",
                "key": obj.key,
                "displayName": obj.name,
                "metadata": {
                    "key": obj.key,
                    "name": obj.name,
                    "shortDescription": obj.short_description,
                    "description": obj.description,
                    "category": obj.category,
                    "hasParameters": obj.has_parameters,
                    "defaultParameters": obj.default_parameters,
                    "defaultTier": obj.default_tier,
                    "unremovable": obj.unremovable,
                },
            })

    # Process constraints
    for con in all_constraints:
        if con.key in excluded_cons:
            continue
        searchable = f"{con.key} {con.name} {con.description} {con.category}".lower()
        if not query or query in searchable:
            constraints.append({
                "type": "constraint",
                "key": con.key,
                "displayName": con.name,
                "metadata": {
                    "key": con.key,
                    "name": con.name,
                    "shortDescription": con.short_description,
                    "description": con.description,
                    "category": con.category,
                },
            })

    # Process requirements
    for key, metadata in all_requirements.items():
        if key in excluded_reqs:
            continue
        display_name = (
            metadata.get("medium-title")
            or metadata.get("title-no-degree")
            or metadata.get("short-title")
            or key
        )
        searchable = " ".join(
            str(v) for v in [
                key,
                metadata.get("title"),
                metadata.get("title-no-degree"),
                metadata.get("medium-title"),
                metadata.get("short-title"),
            ]
            if v
        ).lower()

        if not query or query in searchable:
            item = {
                "type": "degree",
                "key": key,
                "displayName": display_name,
                "metadata": metadata,
            }
            # Concentrations are beta-only requirements
            is_concentration = metadata.get("source") == "beta" and not metadata.get("hasBothVersions")
            if is_concentration:
                concentrations.append(item)
            else:
                degrees.append(item)

    return {
        "objectives": objectives[:limit],
        "constraints": constraints[:limit],
        "concentrations": concentrations[:limit],
        "degrees": degrees[:limit],
        "totalCounts": {
            "objectives": len(objectives),
            "constraints": len(constraints),
            "concentrations": len(concentrations),
            "degrees": len(degrees),
        },
    }
