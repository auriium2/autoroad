"""
Unit tests for requirements parser.
"""

import pytest

from courses.requirements.parser import (
    RequirementParseError,
    parse_requirement,
    parse_requirement_list,
    requirement_to_string,
)
from courses.requirements.types import (
    RequirementCourse,
    RequirementGroup,
    RequirementPlainString,
    RequirementThreshold,
)


class TestBasicParsing:
    """Tests for basic requirement parsing."""

    def test_simple_course(self):
        """Test parsing a simple course requirement."""
        req_data = {"req": "6.100A"}
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementCourse)
        assert result.course_id == "6.100A"
        assert not result.was_pruned

    def test_course_with_title(self):
        """Test parsing a course with a title."""
        req_data = {"req": "6.100A", "title": "Introduction to CS"}
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementCourse)
        assert result.course_id == "6.100A"
        assert result.title == "Introduction to CS"

    def test_gir_requirement(self):
        """Test parsing a GIR requirement."""
        req_data = {"req": "GIR:CAL1"}
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementCourse)
        assert result.course_id == "GIR:CAL1"

    def test_plain_string(self):
        """Test parsing a plain-string requirement."""
        req_data = {
            "req": "2 math subjects",
            "plain-string": True,
            "title": "Math Requirement"
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementPlainString)
        assert result.description == "2 math subjects"
        assert result.title == "Math Requirement"

    def test_plain_string_with_threshold(self):
        """Test parsing a plain-string with threshold."""
        req_data = {
            "req": "2 math subjects",
            "plain-string": True,
            "threshold": {"cutoff": 2, "criterion": "subjects", "type": "GTE"}
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementPlainString)
        assert result.threshold is not None
        assert result.threshold.cutoff == 2
        assert result.threshold.criterion == "subjects"


class TestGroupParsing:
    """Tests for group requirement parsing."""

    def test_simple_all_group(self):
        """Test parsing a simple 'all' group."""
        req_data = {
            "connection-type": "all",
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"}
            ]
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementGroup)
        assert result.connection_type == "all"
        assert len(result.items) == 2
        assert all(isinstance(item, RequirementCourse) for item in result.items)

    def test_simple_any_group(self):
        """Test parsing a simple 'any' group."""
        req_data = {
            "connection-type": "any",
            "reqs": [
                {"req": "18.05"},
                {"req": "18.06"}
            ]
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementGroup)
        assert result.connection_type == "any"
        assert len(result.items) == 2

    def test_group_with_threshold(self):
        """Test parsing a group with threshold."""
        req_data = {
            "connection-type": "any",
            "threshold": {"cutoff": 2, "criterion": "subjects", "type": "GTE"},
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"},
                {"req": "6.1010"}
            ]
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementGroup)
        assert result.threshold is not None
        assert result.threshold.cutoff == 2
        assert result.threshold.criterion == "subjects"
        assert result.threshold.type == "GTE"

    def test_nested_groups(self):
        """Test parsing nested groups."""
        req_data = {
            "connection-type": "all",
            "reqs": [
                {"req": "6.100A"},
                {
                    "connection-type": "any",
                    "reqs": [
                        {"req": "18.05"},
                        {"req": "18.06"}
                    ]
                }
            ]
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementGroup)
        assert result.connection_type == "all"
        assert len(result.items) == 2
        assert isinstance(result.items[0], RequirementCourse)
        assert isinstance(result.items[1], RequirementGroup)
        assert result.items[1].connection_type == "any"

    def test_group_with_title(self):
        """Test parsing a group with a title."""
        req_data = {
            "connection-type": "all",
            "title": "Core Requirements",
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"}
            ]
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementGroup)
        assert result.title == "Core Requirements"


class TestIDGeneration:
    """Tests for req_id generation."""

    def test_course_id_from_title(self):
        """Test that course IDs are generated from titles."""
        req_data = {"req": "6.100A", "title": "Intro to CS"}
        result = parse_requirement(req_data)

        assert result.req_id == "intro_to_cs"

    def test_group_id_from_title(self):
        """Test that group IDs are generated from titles."""
        req_data = {
            "connection-type": "all",
            "title": "Core Requirements",
            "reqs": [{"req": "6.100A"}]
        }
        result = parse_requirement(req_data)

        assert result.req_id == "core_requirements"

    def test_nested_id_generation(self):
        """Test that nested groups have hierarchical IDs."""
        req_data = {
            "connection-type": "all",
            "title": "Parent",
            "reqs": [
                {
                    "connection-type": "any",
                    "title": "Child",
                    "reqs": [{"req": "6.100A"}]
                }
            ]
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementGroup)
        assert result.req_id == "parent"
        assert isinstance(result.items[0], RequirementGroup)
        assert result.items[0].req_id == "parent/child"


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_req_field(self):
        """Test that missing 'req' field raises error."""
        req_data = {"title": "Something"}

        with pytest.raises(RequirementParseError, match="must have 'req'"):
            parse_requirement(req_data)

    def test_invalid_connection_type(self):
        """Test that invalid connection-type raises error."""
        req_data = {
            "connection-type": "invalid",
            "reqs": [{"req": "6.100A"}]
        }

        with pytest.raises(RequirementParseError, match="must be 'all' or 'any'"):
            parse_requirement(req_data)

    def test_invalid_threshold_format(self):
        """Test that invalid threshold format raises error."""
        req_data = {
            "connection-type": "any",
            "threshold": {"invalid": "format"},
            "reqs": [{"req": "6.100A"}]
        }

        with pytest.raises(RequirementParseError):
            parse_requirement(req_data)

    def test_reqs_not_list(self):
        """Test that non-list 'reqs' raises error."""
        req_data = {
            "connection-type": "all",
            "reqs": "not a list"
        }

        with pytest.raises(RequirementParseError, match="must be a list"):
            parse_requirement(req_data)


class TestRequirementToString:
    """Tests for requirement_to_string conversion."""

    def test_simple_course_string(self):
        """Test converting a simple course to string."""
        course = RequirementCourse(course_id="6.100A")
        result = requirement_to_string(course)

        assert result == "6.100A"

    def test_all_group_string(self):
        """Test converting an 'all' group to string."""
        group = RequirementGroup(
            items=(
                RequirementCourse(course_id="6.100A"),
                RequirementCourse(course_id="6.1200")
            ),
            connection_type="all"
        )
        result = requirement_to_string(group)

        assert "ALL" in result
        assert "6.100A" in result
        assert "6.1200" in result

    def test_any_group_string(self):
        """Test converting an 'any' group to string."""
        group = RequirementGroup(
            items=(
                RequirementCourse(course_id="18.05"),
                RequirementCourse(course_id="18.06")
            ),
            connection_type="any"
        )
        result = requirement_to_string(group)

        assert "ANY" in result

    def test_threshold_string(self):
        """Test converting a threshold group to string."""
        group = RequirementGroup(
            items=(
                RequirementCourse(course_id="6.100A"),
                RequirementCourse(course_id="6.1200")
            ),
            threshold=RequirementThreshold(cutoff=2, criterion="subjects", type="GTE")
        )
        result = requirement_to_string(group)

        assert "GTE 2 subjects" in result

    def test_with_ids(self):
        """Test converting with show_ids=True."""
        course = RequirementCourse(course_id="6.100A", req_id="test_id")
        result = requirement_to_string(course, show_ids=True)

        assert "[ID: test_id]" in result


class TestParseRequirementList:
    """Tests for parse_requirement_list."""

    def test_parse_list_of_requirements(self):
        """Test parsing a list of requirements."""
        reqs_data = [
            {"req": "6.100A"},
            {"req": "6.1200"},
            {
                "connection-type": "any",
                "reqs": [{"req": "18.05"}, {"req": "18.06"}]
            }
        ]
        result = parse_requirement_list(reqs_data)

        assert len(result) == 3
        assert isinstance(result[0], RequirementCourse)
        assert isinstance(result[1], RequirementCourse)
        assert isinstance(result[2], RequirementGroup)

    def test_parse_empty_list(self):
        """Test parsing an empty list."""
        result = parse_requirement_list([])

        assert result == []

    def test_parse_list_with_error(self):
        """Test that errors in list items are caught."""
        reqs_data = [
            {"req": "6.100A"},
            {"invalid": "data"}
        ]

        with pytest.raises(RequirementParseError, match="Error parsing requirement 1"):
            parse_requirement_list(reqs_data)


class TestRealWorldStructures:
    """Tests based on real FireRoad requirement structures."""

    def test_eecs_style_requirement(self):
        """Test parsing an EECS-style requirement with thresholds."""
        req_data = {
            "connection-type": "any",
            "title": "Advanced Subjects",
            "threshold": {"cutoff": 2, "criterion": "subjects", "type": "GTE"},
            "threshold-desc": "at least 2",
            "reqs": [
                {"req": "6.4100"},
                {"req": "6.4200"},
                {"req": "6.4300"},
                {"req": "6.4400"}
            ]
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementGroup)
        assert result.threshold is not None
        assert result.threshold.cutoff == 2
        assert result.threshold_desc == "at least 2"
        assert len(result.items) == 4

    def test_units_threshold(self):
        """Test parsing a units-based threshold."""
        req_data = {
            "connection-type": "all",
            "title": "Electives",
            "threshold": {"cutoff": 27, "criterion": "units", "type": "GTE"},
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"}
            ]
        }
        result = parse_requirement(req_data)

        assert isinstance(result, RequirementGroup)
        assert result.threshold is not None
        assert result.threshold.criterion == "units"
        assert result.threshold.cutoff == 27
