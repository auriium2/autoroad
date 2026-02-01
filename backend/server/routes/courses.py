from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from shared.courses.prerequisites.types import PrereqCourse, PrereqGroup, PrereqNode
from shared.services.cache import get_courses_data, get_parsed_prerequisites

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

_course_map_cache: dict[str, dict[str, Any]] | None = None
_course_map_source_id: int | None = None


async def _get_course_map() -> dict[str, dict[str, Any]]:
    """Get a cached subject_id -> course dict, rebuilt only when course data changes."""
    global _course_map_cache, _course_map_source_id
    all_courses = await get_courses_data()
    source_id = id(all_courses)
    if _course_map_cache is None or _course_map_source_id != source_id:
        _course_map_cache = {c.get("subject_id"): c for c in all_courses}
        _course_map_source_id = source_id
    return _course_map_cache


def _prereq_to_dict(node: PrereqNode) -> dict[str, Any]:
    """Convert a PrereqNode to a JSON-serializable dict."""
    if isinstance(node, PrereqCourse):
        return {"type": "course", "courseId": node.course_id}
    elif isinstance(node, PrereqGroup):
        return {
            "type": "group",
            "threshold": node.threshold,
            "items": [_prereq_to_dict(item) for item in node.items]
        }
    return {}

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
    parsed_prereqs = await get_parsed_prerequisites()

    for course in all_courses:
        if course.get("subject_id") == course_id:
            # Add parsed prereq tree with equivalencies injected
            result = dict(course)
            prereq_tree = parsed_prereqs.get(course_id)
            if prereq_tree:
                result["prereqTree"] = _prereq_to_dict(prereq_tree)
            return result

    raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found")


@router.get("/courses/batch-lookup")
@limiter.limit("30/minute")
async def batch_lookup_courses(
    request: Request,
    ids: str = Query(..., description="Comma-separated course IDs"),
):
    """Batch lookup multiple courses by ID. Returns a dict mapping course_id -> course data."""
    course_ids = [cid.strip() for cid in ids.split(",") if cid.strip()]

    if len(course_ids) > 200:
        raise HTTPException(status_code=400, detail="Maximum 200 courses per batch request")

    course_map = await _get_course_map()
    parsed_prereqs = await get_parsed_prerequisites()

    virtual_map = {item["subject_id"]: item for item in VIRTUAL_ITEMS}

    results: dict[str, dict[str, Any]] = {}
    for course_id in course_ids:
        # Check virtual items first
        if course_id in virtual_map:
            results[course_id] = virtual_map[course_id]
            continue

        course = course_map.get(course_id)
        if course:
            result = dict(course)
            prereq_tree = parsed_prereqs.get(course_id)
            if prereq_tree:
                result["prereqTree"] = _prereq_to_dict(prereq_tree)
            results[course_id] = result

    return results


class CoursePlacement(BaseModel):
    courseId: str
    section: int
    status: str | None = None  # "pin", "override", etc.


class ValidatePrerequisitesRequest(BaseModel):
    placements: list[CoursePlacement]


class PrereqEdge(BaseModel):
    fromCourseId: str
    toCourseId: str


class ValidatePrerequisitesResponse(BaseModel):
    missing: dict[str, list[str]]  # courseId -> list of missing prereq course IDs
    edges: list[PrereqEdge]  # prerequisite edges for drawing arrows
    tags: dict[str, list[str]]  # courseId -> list of tags like ["GIR:CAL1", "HASS:A"]


def _evaluate_prereq(
    node: PrereqNode,
    available_courses: set[str],
    course_tags: dict[str, list[str]],
    allow_reuse: bool = True,
    minimal: bool = True,
    used_courses: set[str] | None = None
) -> tuple[bool, list[str], list[str]]:
    """
    Evaluate a prerequisite tree against available courses.
    Returns (satisfied, unsatisfied_reasons, matched_courses)
    """
    if used_courses is None:
        used_courses = set()

    if isinstance(node, PrereqCourse):
        course_id = node.course_id

        # Check if this is a tag requirement (GIR:XXX or HASS:XXX)
        if course_id.startswith("GIR:") or course_id.startswith("HASS:"):
            for available_course in available_courses:
                tags = course_tags.get(available_course, [])
                can_use = allow_reuse or available_course not in used_courses
                if course_id in tags and can_use:
                    used_courses.add(available_course)
                    return (True, [], [available_course])
            return (False, [course_id], [])

        can_use = allow_reuse or course_id not in used_courses
        if course_id in available_courses and can_use:
            used_courses.add(course_id)
            return (True, [], [course_id])

        return (False, [course_id], [])

    elif isinstance(node, PrereqGroup):
        if not node.items:
            return (True, [], [])

        satisfied_count = 0
        all_matched: list[str] = []
        item_results: list[tuple[bool, list[str], list[str]]] = []

        for item in node.items:
            result = _evaluate_prereq(item, available_courses, course_tags, allow_reuse, minimal, used_courses)
            item_results.append(result)
            all_matched.extend(result[2])

            if result[0]:  # satisfied
                satisfied_count += 1

            if satisfied_count >= node.threshold:
                return (True, [], all_matched)

        if satisfied_count >= node.threshold:
            return (True, [], all_matched)

        # Not satisfied - collect unsatisfied reasons
        if minimal:
            if node.threshold == 1:
                # OR group: return the option with fewest missing prerequisites
                unsatisfied_results = [r for r in item_results if not r[0]]
                if not unsatisfied_results:
                    return (False, [], all_matched)
                minimal_option = min(unsatisfied_results, key=lambda r: len(r[1]))
                return (False, minimal_option[1], all_matched)
            elif node.threshold == len(node.items):
                # AND group: return all unsatisfied
                all_unsatisfied: list[str] = []
                for result in item_results:
                    if not result[0]:
                        all_unsatisfied.extend(result[1])
                return (False, all_unsatisfied, all_matched)
            else:
                # k-of-n group
                unsatisfied_results = [r for r in item_results if not r[0]]
                needed = node.threshold - satisfied_count
                sorted_unsatisfied = sorted(unsatisfied_results, key=lambda r: len(r[1]))
                minimal_options = sorted_unsatisfied[:needed]
                all_unsatisfied = []
                for result in minimal_options:
                    all_unsatisfied.extend(result[1])
                return (False, all_unsatisfied, all_matched)
        else:
            # Complete mode: return all unsatisfied reasons
            all_unsatisfied = []
            for result in item_results:
                if not result[0]:
                    all_unsatisfied.extend(result[1])
            return (False, all_unsatisfied, all_matched)

    return (False, [], [])


@router.post("/prerequisites/validate")
@limiter.limit("60/minute")
async def validate_prerequisites(
    request: Request,
    body: ValidatePrerequisitesRequest,
) -> ValidatePrerequisitesResponse:
    """
    Validate prerequisites for a set of course placements.
    Returns missing prerequisites, edges for drawing arrows, and course tags.
    """
    if len(body.placements) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 placements per request")

    course_map = await _get_course_map()
    parsed_prereqs = await get_parsed_prerequisites()

    tags: dict[str, list[str]] = {}
    for placement in body.placements:
        course = course_map.get(placement.courseId)
        if course:
            course_tags: list[str] = []
            if gir := course.get("gir_attribute"):
                course_tags.append(f"GIR:{gir}")
            if hass := course.get("hass_attribute"):
                course_tags.append(f"HASS:{hass}")
            if course_tags:
                tags[placement.courseId] = course_tags

    # Group placements by section for efficient lookup
    section2courses: dict[int, set[str]] = {}
    for placement in body.placements:
        if placement.section not in section2courses:
            section2courses[placement.section] = set()
        section2courses[placement.section].add(placement.courseId)

    # Compute courses available before each section
    all_sections = sorted(section2courses.keys())
    courses_before_section: dict[int, set[str]] = {}
    cumulative: set[str] = set()
    for section in all_sections:
        courses_before_section[section] = cumulative.copy()
        cumulative.update(section2courses[section])

    # Evaluate prerequisites and build edges
    missing: dict[str, list[str]] = {}
    edges: list[PrereqEdge] = []

    for placement in body.placements:
        # Skip prerequisite checking for Must Take (-2), ASEs (-1), and override nodes
        if placement.section == -2 or placement.section == -1 or placement.status == "override":
            missing[placement.courseId] = []
            continue

        prereq_tree = parsed_prereqs.get(placement.courseId)
        if not prereq_tree:
            missing[placement.courseId] = []
            continue

        available = courses_before_section.get(placement.section, set())
        satisfied, unsatisfied_reasons, matched_courses = _evaluate_prereq(
            prereq_tree, available, tags, allow_reuse=True, minimal=True
        )

        if satisfied:
            missing[placement.courseId] = []
        else:
            missing[placement.courseId] = list(set(unsatisfied_reasons))

        # Add edges for matched prerequisites
        for matched_course in matched_courses:
            if matched_course in available:
                edges.append(PrereqEdge(fromCourseId=matched_course, toCourseId=placement.courseId))

    return ValidatePrerequisitesResponse(missing=missing, edges=edges, tags=tags)


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
