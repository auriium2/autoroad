"""
Hydrant API routes for schedule data.
"""

from fastapi import APIRouter, Query

from shared.services.hydrant import ScheduleResponse, get_schedule_blocks

router = APIRouter()


@router.get("/hydrant/schedule/{target_semester}", response_model=ScheduleResponse)
async def get_schedule(
    target_semester: str,
    course_ids: str = Query(..., description="Comma-separated list of course IDs"),
):
    """
    Get parsed schedule blocks for courses in a semester.
    
    Returns data_semester (actual source) and target_semester so frontend
    can show a warning when they differ.
    """
    ids = [id.strip() for id in course_ids.split(",") if id.strip()]
    return await get_schedule_blocks(target_semester, ids)
