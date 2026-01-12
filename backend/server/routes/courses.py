from typing import Any, Literal

from fastapi import APIRouter, Query

from shared.services.cache import get_courses_data

router = APIRouter()

# Virtual items for generic requirement markers
# These appear in search results and can be dragged to semesters
VIRTUAL_ITEMS: list[dict[str, Any]] = [
    {"subject_id": "HASS-A", "title": "Any HASS Arts", "total_units": 12, "virtual": True, "hass_attribute": "HASS-A"},
    {"subject_id": "HASS-H", "title": "Any HASS Humanities", "total_units": 12, "virtual": True, "hass_attribute": "HASS-H"},
    {"subject_id": "HASS-S", "title": "Any HASS Social Sciences", "total_units": 12, "virtual": True, "hass_attribute": "HASS-S"},
    {"subject_id": "HASS-E", "title": "Any HASS Elective", "total_units": 12, "virtual": True, "hass_attribute": "HASS-E"},
]


def calculate_imdb_rating(rating: float | None, enrollment: int | None) -> float | None:
    if rating is None or enrollment is None:
        return None
    m = 30
    c = 5.0
    weighted = (enrollment / (enrollment + m)) * rating + (m / (enrollment + m)) * c
    return round(weighted, 1)


@router.get("/courses/search")
async def search_courses(
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
    all_courses = get_courses_data()

    # Find matching virtual items (always check before filtering)
    matching_virtual: list[dict[str, Any]] = []
    if q != "*":
        query_lower = q.lower()
        for item in VIRTUAL_ITEMS:
            if (query_lower in item["subject_id"].lower()
                or query_lower in item["title"].lower()):
                matching_virtual.append(item)

    # Filter by search query (skip if wildcard)
    if q != "*":
        query_lower = q.lower()
        if search_type == "starts":
            all_courses = [
                c for c in all_courses
                if (c.get("subject_id") or "").lower().startswith(query_lower)
                or (c.get("title") or "").lower().startswith(query_lower)
            ]
        else:
            all_courses = [
                c for c in all_courses
                if query_lower in (c.get("subject_id") or "").lower()
                or query_lower in (c.get("title") or "").lower()
            ]

    # Filter by department
    if department and department != "all":
        all_courses = [
            c for c in all_courses
            if (c.get("subject_id") or "").startswith(f"{department}.")
        ]

    # Filter by GIR
    if gir:
        all_courses = [
            c for c in all_courses
            if gir in (c.get("gir_attribute") or "")
        ]

    # Filter by HASS
    if hass:
        all_courses = [
            c for c in all_courses
            if hass in (c.get("hass_attribute") or "")
        ]

    # Filter by CI
    if ci:
        if ci == "NONE":
            all_courses = [c for c in all_courses if not c.get("communication_requirement")]
        else:
            all_courses = [
                c for c in all_courses
                if ci in (c.get("communication_requirement") or "")
            ]

    # Filter by level
    if level:
        level_code = "U" if level == "UG" else "G"
        all_courses = [c for c in all_courses if c.get("level") == level_code]

    # Filter by units
    if units:
        def units_match(c: dict[str, Any]) -> bool:
            u = c.get("total_units") or 0
            match units:
                case "<6":
                    return u < 6
                case "6":
                    return u == 6
                case "9":
                    return u == 9
                case "12":
                    return u == 12
                case "15":
                    return u == 15
                case "6+":
                    return u >= 6
        all_courses = [c for c in all_courses if units_match(c)]

    # Filter by term
    if term:
        term_key = {
            "FA": "offered_fall",
            "IAP": "offered_IAP",
            "SP": "offered_spring",
        }[term]
        all_courses = [c for c in all_courses if c.get(term_key)]

    # Enrich with IMDB rating
    for course in all_courses:
        if course.get("imdb_rating") is None:
            course["imdb_rating"] = calculate_imdb_rating(
                course.get("rating"),  # type: ignore[arg-type]
                course.get("enrollment_number")  # type: ignore[arg-type]
            )

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
        all_courses.sort(key=relevance_key)

    # Apply explicit sort (overrides relevance sort)
    if sort:
        reverse = sort.endswith("-desc")
        if "imdb-rating" in sort:
            all_courses.sort(key=lambda c: c.get("imdb_rating") or 0, reverse=reverse)
        elif "units" in sort:
            all_courses.sort(key=lambda c: c.get("total_units") or 0, reverse=reverse)
        elif "enrollment" in sort:
            all_courses.sort(key=lambda c: c.get("enrollment_number") or 0, reverse=reverse)

    # Prepend virtual items on first page
    if offset == 0 and matching_virtual:
        all_courses = matching_virtual + all_courses

    # Paginate
    total = len(all_courses)
    paginated = all_courses[offset:offset + limit]

    return {
        "courses": paginated,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


@router.get("/courses/lookup/{course_id:path}")
async def lookup_course(course_id: str):
    # Check virtual items first
    for item in VIRTUAL_ITEMS:
        if item["subject_id"] == course_id:
            return item

    all_courses = get_courses_data()

    for course in all_courses:
        if course.get("subject_id") == course_id:
            if course.get("imdb_rating") is None:
                course["imdb_rating"] = calculate_imdb_rating(
                    course.get("rating"),  # type: ignore[arg-type]
                    course.get("enrollment_number")  # type: ignore[arg-type]
                )
            return course

    return {"error": "Course not found"}, 404


@router.get("/courses/dept/{dept}")
async def get_courses_by_department(
    dept: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    all_courses = get_courses_data()

    filtered = [
        c for c in all_courses
        if (c.get("subject_id") or "").startswith(f"{dept}.")
    ]

    # Enrich with IMDB rating
    for course in filtered:
        if course.get("imdb_rating") is None:
            course["imdb_rating"] = calculate_imdb_rating(
                course.get("rating"),  # type: ignore[arg-type]
                course.get("enrollment_number")  # type: ignore[arg-type]
            )

    total = len(filtered)
    paginated = filtered[offset:offset + limit]

    return {
        "courses": paginated,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }
