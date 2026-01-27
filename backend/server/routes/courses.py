from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from shared.services.cache import get_courses_data

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# Virtual items for generic requirement markers
# These appear in search results and can be dragged to semesters
VIRTUAL_ITEMS: list[dict[str, Any]] = [
    {"subject_id": "HASS-A", "title": "Any HASS Arts", "total_units": 12, "virtual": True, "hass_attribute": "HASS-A"},
    {"subject_id": "HASS-H", "title": "Any HASS Humanities", "total_units": 12, "virtual": True, "hass_attribute": "HASS-H"},
    {"subject_id": "HASS-S", "title": "Any HASS Social Sciences", "total_units": 12, "virtual": True, "hass_attribute": "HASS-S"},
    {"subject_id": "HASS-E", "title": "Any HASS Elective", "total_units": 12, "virtual": True, "hass_attribute": "HASS-E"},
]


def _matches_filters(
    course: dict[str, Any],
    query_lower: str | None,
    search_type: str,
    department: str | None,
    gir: str | None,
    hass: str | None,
    ci: str | None,
    level_code: str | None,
    units: str | None,
    term_key: str | None,
) -> bool:
    """Single-pass filter check for a course."""
    # Search query filter
    if query_lower is not None:
        subject_id = (course.get("subject_id") or "").lower()
        title = (course.get("title") or "").lower()
        if search_type == "starts":
            if not (subject_id.startswith(query_lower) or title.startswith(query_lower)):
                return False
        else:
            if query_lower not in subject_id and query_lower not in title:
                return False

    # Department filter
    if department:
        subject_id = course.get("subject_id") or ""
        if not subject_id.startswith(f"{department}."):
            return False

    # GIR filter
    if gir:
        if gir not in (course.get("gir_attribute") or ""):
            return False

    # HASS filter
    if hass:
        if hass not in (course.get("hass_attribute") or ""):
            return False

    # CI filter
    if ci:
        comm_req = course.get("communication_requirement")
        if ci == "NONE":
            if comm_req:
                return False
        else:
            if ci not in (comm_req or ""):
                return False

    # Level filter
    if level_code:
        if course.get("level") != level_code:
            return False

    # Units filter
    if units:
        u = course.get("total_units") or 0
        match units:
            case "<6":
                if not u < 6:
                    return False
            case "6":
                if u != 6:
                    return False
            case "9":
                if u != 9:
                    return False
            case "12":
                if u != 12:
                    return False
            case "15":
                if u != 15:
                    return False
            case "6+":
                if not u >= 6:
                    return False
            case _:
                pass

    # Term filter
    if term_key:
        if not course.get(term_key):
            return False

    return True


@router.get("/courses/search")
@limiter.limit("60/minute")
async def search_courses(
    request: Request,
    q: str = Query(..., description="Search query, use '*' for all courses"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=2000),
    department: str | None = Query(None, description="Filter by department (e.g., '6', '18')"),
    search_type: Literal["contains", "starts"] = Query("contains"),
    sort: Literal[
        "imdb-rating-asc", "imdb-rating-desc",
        "units-asc", "units-desc",
        "enrollment-asc", "enrollment-desc"
    ] | None = Query(None),
    gir: Literal["LAB", "REST"] | None = Query(None),
    hass: Literal["HASS-A", "HASS-H", "HASS-S", "HASS-E"] | None = Query(None),
    ci: Literal["CI-H", "CI-HW", "NONE"] | None = Query(None),
    level: Literal["UG", "G"] | None = Query(None),
    units: Literal["<6", "6", "9", "12", "15", "6+"] | None = Query(None),
    term: Literal["FA", "IAP", "SP"] | None = Query(None),
):
    all_courses = await get_courses_data()

    # Find matching virtual items (always check before filtering)
    matching_virtual: list[dict[str, Any]] = []
    if q != "*":
        query_lower = q.lower()
        for item in VIRTUAL_ITEMS:
            if (query_lower in item["subject_id"].lower()
                or query_lower in item["title"].lower()):
                matching_virtual.append(item)

    # Pre-compute filter parameters
    query_lower = q.lower() if q != "*" else None
    dept_filter = department if department and department != "all" else None
    level_code = "U" if level == "UG" else ("G" if level == "G" else None)
    term_key = {"FA": "offered_fall", "IAP": "offered_IAP", "SP": "offered_spring"}.get(term) if term else None

    # Single-pass filtering
    filtered = [
        c for c in all_courses
        if _matches_filters(c, query_lower, search_type, dept_filter, gir, hass, ci, level_code, units, term_key)
    ]

    # Sort by relevance first (exact department match), then by explicit sort if provided
    # This ensures "6.100" shows 6.100A before 16.100
    if q != "*" and "." in q:
        query_dept = q.split(".")[0]
        def relevance_key(c: dict[str, Any]) -> tuple[int, str]:
            subject_id = c.get("subject_id") or ""
            course_dept = subject_id.split(".")[0] if "." in subject_id else ""
            # 0 = exact match (highest priority), 1 = no match
            exact_match = 0 if course_dept == query_dept else 1
            return (exact_match, subject_id)
        filtered.sort(key=relevance_key)

    # Apply explicit sort (overrides relevance sort)
    if sort:
        reverse = sort.endswith("-desc")
        if "imdb-rating" in sort:
            filtered.sort(key=lambda c: c.get("imdb_rating") or 0, reverse=reverse)
        elif "units" in sort:
            filtered.sort(key=lambda c: c.get("total_units") or 0, reverse=reverse)
        elif "enrollment" in sort:
            filtered.sort(key=lambda c: c.get("enrollment_number") or 0, reverse=reverse)

    # Prepend virtual items on first page
    if offset == 0 and matching_virtual:
        filtered = matching_virtual + filtered

    # Paginate
    total = len(filtered)
    paginated = filtered[offset:offset + limit]

    return {
        "courses": paginated,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


@router.get("/courses/lookup/{course_id:path}")
@limiter.limit("120/minute")
async def lookup_course(request: Request, course_id: str):
    # Check virtual items first
    for item in VIRTUAL_ITEMS:
        if item["subject_id"] == course_id:
            return item

    all_courses = await get_courses_data()

    for course in all_courses:
        if course.get("subject_id") == course_id:
            return course

    return {"error": "Course not found"}, 404


@router.get("/courses/dept/{dept}")
@limiter.limit("60/minute")
async def get_courses_by_department(
    request: Request,
    dept: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    all_courses = await get_courses_data()

    filtered = [
        c for c in all_courses
        if (c.get("subject_id") or "").startswith(f"{dept}.")
    ]

    total = len(filtered)
    paginated = filtered[offset:offset + limit]

    return {
        "courses": paginated,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }
