"""
Unit tests for FastAPI input validation across all routes.
"""

import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


# ============ Hydrant Route Validation Tests ============

def test_get_schedule_valid_semester():
    """Valid target_semester formats should pass validation (and reach handler, which might return empty/error but NOT 422)."""
    response = client.get("/api/hydrant/schedule/s24", params={"course_ids": "6.1200,18.01"})
    assert response.status_code != 422


def test_get_schedule_invalid_semester():
    """Invalid target_semester formats should fail with 422 Unprocessable Entity."""
    # Too short
    response = client.get("/api/hydrant/schedule/s", params={"course_ids": "6.1200"})
    assert response.status_code == 422

    # Wrong starting letter
    response = client.get("/api/hydrant/schedule/x24", params={"course_ids": "6.1200"})
    assert response.status_code == 422

    # Wrong year format (alphabetic)
    response = client.get("/api/hydrant/schedule/sab", params={"course_ids": "6.1200"})
    assert response.status_code == 422

    # Too long
    response = client.get("/api/hydrant/schedule/s2024", params={"course_ids": "6.1200"})
    assert response.status_code == 422


def test_get_schedule_course_ids_too_long():
    """Query parameter course_ids exceeding max_length of 1000 should fail with 422."""
    huge_ids = ",".join(["6.1200"] * 200)  # Length will be > 1200 characters
    response = client.get("/api/hydrant/schedule/s24", params={"course_ids": huge_ids})
    assert response.status_code == 422


# ============ Courses Route Validation Tests ============

def test_search_courses_validation():
    """Search courses endpoint should validate q and department length constraints."""
    # Valid
    response = client.get("/api/courses/search", params={"q": "6.1200"})
    assert response.status_code != 422

    # q empty should fail (min_length=1)
    response = client.get("/api/courses/search", params={"q": ""})
    assert response.status_code == 422

    # q too long should fail (max_length=100)
    response = client.get("/api/courses/search", params={"q": "a" * 101})
    assert response.status_code == 422

    # department too long should fail (max_length=20)
    response = client.get("/api/courses/search", params={"q": "6.1200", "department": "a" * 21})
    assert response.status_code == 422


def test_lookup_course_validation():
    """Lookup course endpoint should validate course_id path parameter constraints."""
    # Valid
    response = client.get("/api/courses/lookup/6.1200")
    assert response.status_code != 422

    # Too long (max_length=50)
    response = client.get(f"/api/courses/lookup/{'a' * 51}")
    assert response.status_code == 422

    # Invalid characters
    response = client.get("/api/courses/lookup/6.1200%")
    assert response.status_code == 422


def test_batch_lookup_validation():
    """Batch lookup should validate ids parameter length constraint."""
    # Too long (max_length=1000)
    response = client.get("/api/courses/batch-lookup", params={"ids": "6.1200," * 200})
    assert response.status_code == 422


def test_get_courses_by_department_validation():
    """Get courses by department should validate dept constraints."""
    # Valid
    response = client.get("/api/courses/dept/6")
    assert response.status_code != 422

    # Too long (max_length=20)
    response = client.get(f"/api/courses/dept/{'a' * 21}")
    assert response.status_code == 422

    # Invalid characters (dept is alphanumeric)
    response = client.get("/api/courses/dept/6-A")
    assert response.status_code == 422


def test_validate_prerequisites_validation():
    """Validate prerequisites endpoint should enforce schemas on placements."""
    # Valid
    payload = {
        "placements": [
            {"courseId": "6.1200", "section": 0, "status": "pin"}
        ]
    }
    response = client.post("/api/prerequisites/validate", json=payload)
    assert response.status_code != 422

    # Invalid courseId pattern
    payload_invalid_id = {
        "placements": [
            {"courseId": "6.1200%", "section": 0}
        ]
    }
    response = client.post("/api/prerequisites/validate", json=payload_invalid_id)
    assert response.status_code == 422

    # Invalid section
    payload_invalid_section = {
        "placements": [
            {"courseId": "6.1200", "section": 12}
        ]
    }
    response = client.post("/api/prerequisites/validate", json=payload_invalid_section)
    assert response.status_code == 422

    # Invalid status literal
    payload_invalid_status = {
        "placements": [
            {"courseId": "6.1200", "section": 0, "status": "invalid"}
        ]
    }
    response = client.post("/api/prerequisites/validate", json=payload_invalid_status)
    assert response.status_code == 422


# ============ Requirements Route Validation Tests ============

def test_get_requirement_json_validation():
    """Get requirement should validate key and source."""
    # Valid
    response = client.get("/api/requirements/get/major6-3new", params={"source": "canonical"})
    assert response.status_code != 422

    # Invalid source literal
    response = client.get("/api/requirements/get/major6-3new", params={"source": "invalid"})
    assert response.status_code == 422

    # Invalid key characters
    response = client.get("/api/requirements/get/major6-3new%", params={"source": "canonical"})
    assert response.status_code == 422


def test_get_requirement_progress_validation():
    """Get requirement progress should validate key, source, and payload."""
    # Valid empty payload
    payload = {"selectedSubjects": []}
    response = client.post("/api/requirements/progress/major6-3new", json=payload)
    assert response.status_code != 422

    # Invalid subject_id in SelectedSubject
    payload_invalid = {
        "selectedSubjects": [
            {"subject_id": "6.1200%"}
        ]
    }
    response = client.post("/api/requirements/progress/major6-3new", json=payload_invalid)
    assert response.status_code == 422


# ============ Optimize Route Validation Tests ============

def test_optimize_validation_planning_year():
    """Optimize endpoint should validate planningYear format."""
    # Valid planningYear format
    payload_valid = {
        "markers": [],
        "requirements": ["girs"],
        "maxSemesters": 8,
        "planningYear": "2024-2025"
    }
    # Note: /optimize starts streaming and may return 200 or 502/etc., but NOT 422.
    response = client.post("/api/optimize", json=payload_valid)
    assert response.status_code != 422

    # Invalid planningYear format (not matching regex)
    payload_invalid = {
        "markers": [],
        "requirements": ["girs"],
        "maxSemesters": 8,
        "planningYear": "20242025"
    }
    response = client.post("/api/optimize", json=payload_invalid)
    assert response.status_code == 422


def test_optimize_validation_marker_course_id():
    """Optimize endpoint should validate marker courseId."""
    payload_invalid = {
        "markers": [
            {"courseId": "6.1200%", "section": 0, "status": "pin"}
        ],
        "requirements": ["girs"],
        "maxSemesters": 8
    }
    response = client.post("/api/optimize", json=payload_invalid)
    assert response.status_code == 422


# ============ Bug Report Route Validation Tests ============

def test_create_bug_report_validation():
    """Create bug report endpoint should validate title and description constraints."""
    # Valid
    payload_valid = {
        "title": "Valid Title",
        "description": "Valid Description",
        "debug_info": {}
    }
    response = client.post("/api/bug-report", json=payload_valid)
    assert response.status_code != 422

    # Title too long (>256)
    payload_long_title = {
        "title": "a" * 257,
        "description": "Valid Description",
        "debug_info": {}
    }
    response = client.post("/api/bug-report", json=payload_long_title)
    assert response.status_code == 422

    # Description too long (>10000)
    payload_long_desc = {
        "title": "Valid Title",
        "description": "a" * 10001,
        "debug_info": {}
    }
    response = client.post("/api/bug-report", json=payload_long_desc)
    assert response.status_code == 422
