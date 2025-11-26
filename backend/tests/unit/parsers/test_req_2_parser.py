"""
Unit tests for req_2 parser.

These tests verify that the new parser correctly converts Fireroad JSON
into req_2 typed nodes.
"""

import pytest

from shared.courses.requirements.parser import (
    ParseError,
    node_to_string,
    parse,
    parse_fireroad_response,
    parse_requirement_list,
)
from shared.courses.requirements.types import (
    CI,
    GIR,
    HASS,
    AllGroup,
    AnyGroup,
    Course,
    PlainString,
    SubjectThresholdGroup,
    UnitThresholdGroup,
)


class TestBasicParsing:
    """Tests for basic requirement parsing."""

    def test_simple_course(self):
        """Test parsing a simple course requirement."""
        req_data = {"req": "6.100A"}
        result = parse(req_data)

        assert isinstance(result, Course)
        assert result.subject_id == "6.100A"
        assert not result.was_pruned

    def test_course_with_title(self):
        """Test parsing a course with a title."""
        req_data = {"req": "6.100A", "title": "Introduction to CS"}
        result = parse(req_data)

        assert isinstance(result, Course)
        assert result.subject_id == "6.100A"
        assert result.title == "Introduction to CS"

    def test_gir_requirement(self):
        """Test parsing a GIR requirement."""
        req_data = {"req": "GIR:CAL1"}
        result = parse(req_data)

        assert isinstance(result, GIR)
        assert result.gir_code == "CAL1"

    def test_gir_all_codes(self):
        """Test parsing all valid GIR codes."""
        gir_codes = ["CAL1", "CAL2", "PHY1", "PHY2", "CHEM", "BIOL", "REST", "LAB", "LAB2"]
        for code in gir_codes:
            result = parse({"req": f"GIR:{code}"})
            assert isinstance(result, GIR)
            assert result.gir_code == code

    def test_unknown_gir_becomes_plain_string(self):
        """Test that unknown GIR codes become PlainString."""
        result = parse({"req": "GIR:UNKNOWN"})
        assert isinstance(result, PlainString)
        assert result.description == "GIR:UNKNOWN"

    def test_hass_generic(self):
        """Test parsing generic HASS requirement."""
        result = parse({"req": "HASS"})
        assert isinstance(result, HASS)
        assert result.category == "HASS"

    def test_hass_categories(self):
        """Test parsing specific HASS categories."""
        for cat in ["HASS-A", "HASS-H", "HASS-S", "HASS-E"]:
            result = parse({"req": cat})
            assert isinstance(result, HASS)
            assert result.category == cat

    def test_ci_requirements(self):
        """Test parsing CI requirements."""
        for ci_type in ["CI-H", "CI-HW"]:
            result = parse({"req": ci_type})
            assert isinstance(result, CI)
            assert result.ci_type == ci_type

    def test_plain_string(self):
        """Test parsing a plain-string requirement."""
        req_data = {
            "req": "2 math subjects",
            "plain-string": True,
            "title": "Math Requirement"
        }
        result = parse(req_data)

        assert isinstance(result, PlainString)
        assert result.description == "2 math subjects"
        assert result.title == "Math Requirement"


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
        result = parse(req_data)

        assert isinstance(result, AllGroup)
        assert len(result.children) == 2
        assert all(isinstance(child, Course) for child in result.children)

    def test_simple_any_group(self):
        """Test parsing a simple 'any' group."""
        req_data = {
            "connection-type": "any",
            "reqs": [
                {"req": "18.05"},
                {"req": "18.06"}
            ]
        }
        result = parse(req_data)

        assert isinstance(result, AnyGroup)
        assert len(result.children) == 2

    def test_group_with_threshold_becomes_subject_threshold(self):
        """Test parsing a group with subject threshold."""
        req_data = {
            "connection-type": "any",
            "threshold": {"cutoff": 2, "criterion": "subjects", "type": "GTE"},
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"},
                {"req": "6.1010"}
            ]
        }
        result = parse(req_data)

        assert isinstance(result, SubjectThresholdGroup)
        assert result.cutoff == 2
        assert result.threshold_type == "GTE"
        assert result.connection_type == "any"

    def test_group_with_unit_threshold(self):
        """Test parsing a group with units threshold."""
        req_data = {
            "connection-type": "all",
            "threshold": {"cutoff": 27, "criterion": "units", "type": "GTE"},
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"}
            ]
        }
        result = parse(req_data)

        assert isinstance(result, UnitThresholdGroup)
        assert result.cutoff == 27
        assert result.threshold_type == "GTE"

    def test_group_with_distinct_threshold(self):
        """Test parsing a group with distinct threshold."""
        req_data = {
            "connection-type": "any",
            "threshold": {"cutoff": 5, "criterion": "subjects", "type": "GTE"},
            "distinct-threshold": {"cutoff": 3, "criterion": "subjects", "type": "GTE"},
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"}
            ]
        }
        result = parse(req_data)

        assert isinstance(result, SubjectThresholdGroup)
        assert result.distinct_threshold is not None
        assert result.distinct_threshold.cutoff == 3
        assert result.distinct_threshold.comparison == "GTE"

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
        result = parse(req_data)

        assert isinstance(result, AllGroup)
        assert len(result.children) == 2
        assert isinstance(result.children[0], Course)
        assert isinstance(result.children[1], AnyGroup)

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
        result = parse(req_data)

        assert isinstance(result, AllGroup)
        assert result.title == "Core Requirements"

    def test_group_no_connection_defaults_to_all(self):
        """Test that groups without connection-type default to AllGroup."""
        req_data = {
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"}
            ]
        }
        result = parse(req_data)

        assert isinstance(result, AllGroup)


class TestIDGeneration:
    """Tests for req_id generation."""

    def test_course_id_from_title(self):
        """Test that course IDs are generated from titles."""
        req_data = {"req": "6.100A", "title": "Intro to CS"}
        result = parse(req_data)

        assert result.req_id == "intro_to_cs"

    def test_group_id_from_title(self):
        """Test that group IDs are generated from titles."""
        req_data = {
            "connection-type": "all",
            "title": "Core Requirements",
            "reqs": [{"req": "6.100A"}]
        }
        result = parse(req_data)

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
        result = parse(req_data)

        assert isinstance(result, AllGroup)
        assert result.req_id == "parent"
        assert isinstance(result.children[0], AnyGroup)
        assert result.children[0].req_id == "parent/child"


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_req_field(self):
        """Test that missing 'req' field raises error."""
        req_data = {"title": "Something"}

        with pytest.raises(ParseError, match="must have 'req' or 'reqs'"):
            parse(req_data)

    def test_invalid_threshold_format(self):
        """Test that invalid threshold format raises error."""
        req_data = {
            "connection-type": "any",
            "threshold": {"invalid": "format"},
            "reqs": [{"req": "6.100A"}]
        }

        with pytest.raises(ParseError, match="Invalid threshold"):
            parse(req_data)

    def test_reqs_not_list(self):
        """Test that non-list 'reqs' raises error."""
        req_data = {
            "connection-type": "all",
            "reqs": "not a list"
        }

        with pytest.raises(ParseError, match="must be a list"):
            parse(req_data)


class TestNodeToString:
    """Tests for node_to_string conversion."""

    def test_simple_course_string(self):
        """Test converting a simple course to string."""
        course = Course(subject_id="6.100A")
        result = node_to_string(course)

        assert "6.100A" in result

    def test_gir_string(self):
        """Test converting a GIR to string."""
        gir = GIR(gir_code="CAL1")
        result = node_to_string(gir)

        assert "GIR" in result
        assert "CAL1" in result

    def test_hass_string(self):
        """Test converting a HASS to string."""
        hass = HASS(category="HASS-A")
        result = node_to_string(hass)

        assert "HASS" in result
        assert "HASS-A" in result

    def test_all_group_string(self):
        """Test converting an AllGroup to string."""
        group = AllGroup(
            children=(
                Course(subject_id="6.100A"),
                Course(subject_id="6.1200")
            )
        )
        result = node_to_string(group)

        assert "AllGroup" in result
        assert "6.100A" in result
        assert "6.1200" in result

    def test_any_group_string(self):
        """Test converting an AnyGroup to string."""
        group = AnyGroup(
            children=(
                Course(subject_id="18.05"),
                Course(subject_id="18.06")
            )
        )
        result = node_to_string(group)

        assert "AnyGroup" in result

    def test_threshold_string(self):
        """Test converting a threshold group to string."""
        group = SubjectThresholdGroup(
            children=(
                Course(subject_id="6.100A"),
                Course(subject_id="6.1200")
            ),
            cutoff=2,
            threshold_type="GTE"
        )
        result = node_to_string(group)

        assert "SubjectThreshold" in result
        assert ">=2" in result

    def test_with_ids(self):
        """Test converting with show_ids=True."""
        course = Course(subject_id="6.100A", req_id="test_id")
        result = node_to_string(course, show_ids=True)

        assert "[ID: test_id]" in result


class TestParseRequirementList:
    """Tests for parse_requirement_list."""

    def test_parse_list_wraps_in_allgroup(self):
        """Test that parse_requirement_list wraps results in AllGroup."""
        reqs_data = [
            {"req": "6.100A"},
            {"req": "6.1200"}
        ]
        result = parse_requirement_list(reqs_data)

        assert isinstance(result, AllGroup)
        assert len(result.children) == 2

    def test_parse_empty_list(self):
        """Test parsing an empty list."""
        result = parse_requirement_list([])

        assert isinstance(result, AllGroup)
        assert len(result.children) == 0

    def test_parse_list_with_error(self):
        """Test that errors in list items are caught."""
        reqs_data = [
            {"req": "6.100A"},
            {"invalid": "data"}
        ]

        with pytest.raises(ParseError, match="Error parsing requirement 1"):
            parse_requirement_list(reqs_data)


class TestParseFireroadResponse:
    """Tests for parse_fireroad_response."""

    def test_parse_full_response(self):
        """Test parsing a complete Fireroad response."""
        data = {
            "title": "Test Major",
            "reqs": [
                {"req": "6.100A"},
                {"req": "6.1200"}
            ]
        }
        result = parse_fireroad_response(data)

        assert isinstance(result, AllGroup)
        assert result.req_id == "test_major"

    def test_parse_response_missing_reqs(self):
        """Test that missing 'reqs' raises error."""
        data = {"title": "Test Major"}

        with pytest.raises(ParseError, match="missing 'reqs' field"):
            parse_fireroad_response(data)


class TestRealWorldStructures:
    """Tests based on real Fireroad requirement structures."""

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
        result = parse(req_data)

        assert isinstance(result, SubjectThresholdGroup)
        assert result.cutoff == 2
        assert len(result.children) == 4

    def test_distinct_threshold_structure(self):
        """Test parsing a distinct threshold structure like 6-4 Centers."""
        req_data = {
            "connection-type": "any",
            "title": "Centers",
            "threshold": {"cutoff": 5, "criterion": "subjects", "type": "GTE"},
            "distinct-threshold": {"cutoff": 5, "criterion": "subjects", "type": "GTE"},
            "reqs": [
                {
                    "threshold": {"cutoff": 1, "criterion": "subjects", "type": "GTE"},
                    "connection-type": "any",
                    "title": "Category A",
                    "reqs": [{"req": "6.100A"}, {"req": "6.100B"}]
                },
                {
                    "threshold": {"cutoff": 1, "criterion": "subjects", "type": "GTE"},
                    "connection-type": "any",
                    "title": "Category B",
                    "reqs": [{"req": "6.200A"}, {"req": "6.200B"}]
                }
            ]
        }
        result = parse(req_data)

        assert isinstance(result, SubjectThresholdGroup)
        assert result.cutoff == 5
        assert result.distinct_threshold is not None
        assert result.distinct_threshold.cutoff == 5
        assert len(result.children) == 2
        assert all(isinstance(c, SubjectThresholdGroup) for c in result.children)

    def test_nested_all_any_groups(self):
        """Test parsing nested all/any groups like requirement alternatives."""
        req_data = {
            "connection-type": "all",
            "title": "Fundamentals",
            "reqs": [
                {
                    "connection-type": "any",
                    "reqs": [{"req": "6.100A"}, {"req": "6.100L"}]
                },
                {"req": "6.1200"},
                {
                    "connection-type": "any",
                    "reqs": [{"req": "18.06"}, {"req": "18.C06"}]
                }
            ]
        }
        result = parse(req_data)

        assert isinstance(result, AllGroup)
        assert len(result.children) == 3
        assert isinstance(result.children[0], AnyGroup)
        assert isinstance(result.children[1], Course)
        assert isinstance(result.children[2], AnyGroup)

    def test_mixed_leaf_types(self):
        """Test parsing requirements with mixed leaf types."""
        req_data = {
            "connection-type": "all",
            "reqs": [
                {"req": "6.100A"},
                {"req": "GIR:CAL1"},
                {"req": "HASS-A"},
                {"req": "CI-H"},
                {"req": "Some description", "plain-string": True}
            ]
        }
        result = parse(req_data)

        assert isinstance(result, AllGroup)
        assert isinstance(result.children[0], Course)
        assert isinstance(result.children[1], GIR)
        assert isinstance(result.children[2], HASS)
        assert isinstance(result.children[3], CI)
        assert isinstance(result.children[4], PlainString)
