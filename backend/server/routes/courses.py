from typing import Literal

from fastapi import APIRouter, Query

from shared.services.cache import get_courses_data

router = APIRouter()


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
    limit: int = Query(20, ge=1, le=100),
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
        def units_match(c: dict) -> bool:
            u = c.get("total_units") or 0
            if units == "<6":
                return u < 6
            elif units == "6":
                return u == 6
            elif units == "9":
                return u == 9
            elif units == "12":
                return u == 12
            elif units == "15":
                return u == 15
            elif units == "6+":
                return u >= 6
            return True
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

    # Sort
    if sort:
        reverse = sort.endswith("-desc")
        if "imdb-rating" in sort:
            all_courses.sort(key=lambda c: c.get("imdb_rating") or 0, reverse=reverse)
        elif "units" in sort:
            all_courses.sort(key=lambda c: c.get("total_units") or 0, reverse=reverse)
        elif "enrollment" in sort:
            all_courses.sort(key=lambda c: c.get("enrollment_number") or 0, reverse=reverse)

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
