"""
Hydrant API routes for schedule data.
"""

from fastapi import APIRouter, Path, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from shared.services.hydrant import ScheduleResponse, get_schedule_blocks

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/hydrant/schedule/{target_semester}", response_model=ScheduleResponse)
@limiter.limit("60/minute")
async def get_schedule(
    request: Request,
    target_semester: str = Path(..., pattern=r"^[sfi]\d{2}$", description="Semester code (e.g., 's24', 'f23', 'i25')"),
    course_ids: str = Query(..., min_length=1, max_length=1000, description="Comma-separated list of course IDs"),
):
    """
    Get parsed schedule blocks for courses in a semester.

    Returns data_semester (actual source) and target_semester so frontend
    can show a warning when they differ.
    """
    ids = [id.strip() for id in course_ids.split(",") if id.strip()]
    return await get_schedule_blocks(target_semester, ids)
