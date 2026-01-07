"""
Requirements API routes - provides parsed requirement trees and progress calculation.
"""

import asyncio
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

REQUIREMENTS_DIR = Path(__file__).parent.parent.parent / "requirements"


class SelectedSubject(BaseModel):
    subject_id: str
    title: str | None = None
    units: int | None = None
    semester: int | None = None


class ProgressRequest(BaseModel):
    selectedSubjects: list[SelectedSubject] = []
    coursesOfStudy: list[str] = []
    progressAssertions: dict[str, object] = {}


@router.get("/requirements/list")
async def list_requirements():
    """
    List all available requirements, merging Fireroad's list with local beta files.
    """
    loop = asyncio.get_event_loop()

    def fetch_all() -> dict[str, Any]:
        fireroad_reqs: dict[str, Any] = {}
        try:
            resp = requests.get("https://fireroad.mit.edu/requirements/list_reqs", timeout=10)
            resp.raise_for_status()
            fireroad_reqs = resp.json()
        except Exception as e:
            print(f"[REQUIREMENTS] Failed to fetch Fireroad list: {e}")

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
                    except Exception as e:
                        print(f"[REQUIREMENTS] Failed to parse {path}: {e}")

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

    return await loop.run_in_executor(None, fetch_all)


@router.get("/requirements/get/{key}")
async def get_requirement_json(key: str, source: str = "canonical"):
    """Get a parsed requirement definition."""
    loop = asyncio.get_event_loop()
    from shared.services.cache import fetch_requirement

    try:
        data = await loop.run_in_executor(None, fetch_requirement, key, source)
        return data
    except Exception as e:
        return {"error": str(e), "details": type(e).__name__}


@router.post("/requirements/progress/{key}")
async def get_requirement_progress(key: str, request: ProgressRequest, source: str = "canonical"):
    """
    Get requirement progress for a list of selected subjects.
    
    Uses our own progress calculator with the distinct_threshold bug fixed.
    """
    loop = asyncio.get_event_loop()

    def compute() -> dict[str, Any]:
        from shared.courses.requirements.parser import parse_fireroad_response
        from shared.courses.requirements.progress import compute_progress, progress_to_json
        from shared.services.cache import fetch_requirement, get_courses_data

        # Get requirement data and parse into nodes
        req_data = fetch_requirement(key, source)
        root_node = parse_fireroad_response(req_data)

        # Get course data for satisfaction checking
        courses_data = get_courses_data()
        id2course = {c["subject_id"]: c for c in courses_data}

        # Compute progress - extract subject_ids from the objects
        selected_set = {s.subject_id for s in request.selectedSubjects}
        result = compute_progress(root_node, selected_set, id2course)

        # Convert to JSON format
        output = progress_to_json(result, root_node)

        # Add top-level metadata
        for field in ["title", "medium-title", "short-title", "title-no-degree", "description"]:
            if field in req_data:
                output[field] = req_data[field]
        output["list-id"] = key

        return output

    try:
        return await loop.run_in_executor(None, compute)
    except Exception as e:
        return {"error": str(e), "details": type(e).__name__}
