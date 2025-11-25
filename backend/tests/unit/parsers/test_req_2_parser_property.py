"""
Property-based tests for req_2 parser using Hypothesis.

These tests verify invariants that should hold for ANY valid input,
catching edge cases that manual tests miss.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from courses.requirements.parser import (
    parse,
    parse_requirement_list,
    parse_fireroad_response,
    ParseError,
)
from courses.requirements.types import (
    AllGroup,
    AnyGroup,
    CI,
    Course,
    GIR,
    HASS,
    Node,
    PlainString,
    SubjectThresholdGroup,
    UnitThresholdGroup,
    Group,
    Leaf,
)


# ============================================================================
# Strategies for generating valid Fireroad-like requirement structures
# ============================================================================

# Valid course IDs (MIT format: dept.number)
valid_course_ids = st.from_regex(r"[0-9]{1,2}\.[0-9A-Z]{2,5}", fullmatch=True)


# GIR codes
valid_gir_codes = st.sampled_from(["CAL1", "CAL2", "PHY1", "PHY2", "CHEM", "BIOL", "REST", "LAB", "LAB2"])
gir_course_ids = valid_gir_codes.map(lambda code: f"GIR:{code}")

# HASS categories
valid_hass_categories = st.sampled_from(["HASS", "HASS-A", "HASS-H", "HASS-S", "HASS-E"])

# CI types
valid_ci_types = st.sampled_from(["CI-H", "CI-HW"])

# Any valid leaf course ID (course, GIR, HASS, or CI)
any_leaf_course_id = st.one_of(
    valid_course_ids,
    gir_course_ids,
    valid_hass_categories,
    valid_ci_types,
)

# Title strings (optional)
optional_title = st.one_of(st.none(), st.text(min_size=1, max_size=50))

# Plain string descriptions
plain_string_descriptions = st.text(min_size=1, max_size=100)


def leaf_req_dict(course_id_strategy=any_leaf_course_id, is_plain_string: bool = False):
    """Generate a leaf requirement dictionary."""
    @st.composite
    def _strategy(draw):
        course_id = draw(course_id_strategy)
        title = draw(optional_title)
        result = {"req": course_id}
        if title:
            result["title"] = title
        if is_plain_string:
            result["plain-string"] = True
        return result
    return _strategy()


# Plain string leaf
plain_string_req_dict = st.builds(
    lambda desc, title: {"req": desc, "plain-string": True} | ({"title": title} if title else {}),
    desc=plain_string_descriptions,
    title=optional_title,
)


# Recursive strategy for nested requirement structures
@st.composite
def requirement_dict(draw, max_depth: int = 3) -> dict:
    """Generate a valid Fireroad requirement dictionary (leaf or group)."""
    if max_depth <= 0:
        # At max depth, always return a leaf
        return draw(leaf_req_dict())

    # Choose between leaf and group
    is_group = draw(st.booleans())

    if not is_group:
        # Leaf node
        is_plain = draw(st.booleans())
        if is_plain:
            return draw(plain_string_req_dict)
        return draw(leaf_req_dict())

    # Group node
    num_children = draw(st.integers(min_value=1, max_value=4))
    children = [draw(requirement_dict(max_depth=max_depth - 1)) for _ in range(num_children)]

    title = draw(optional_title)
    connection_type = draw(st.sampled_from(["all", "any", None]))

    # Optionally add a threshold
    has_threshold = draw(st.booleans())

    result: dict = {"reqs": children}
    if title:
        result["title"] = title
    if connection_type:
        result["connection-type"] = connection_type

    if has_threshold:
        cutoff = draw(st.integers(min_value=1, max_value=max(len(children), 1)))
        criterion = draw(st.sampled_from(["subjects", "units"]))
        threshold_type = draw(st.sampled_from(["GTE", "LTE"]))
        result["threshold"] = {
            "cutoff": cutoff,
            "criterion": criterion,
            "type": threshold_type,
        }

        # Optionally add distinct threshold (only for subjects)
        if criterion == "subjects" and draw(st.booleans()):
            distinct_cutoff = draw(st.integers(min_value=1, max_value=max(len(children), 1)))
            result["distinct-threshold"] = {
                "cutoff": distinct_cutoff,
                "type": draw(st.sampled_from(["GTE", "LTE"])),
            }

    return result


@st.composite
def fireroad_response(draw, max_depth: int = 3) -> dict:
    """Generate a full Fireroad API response structure."""
    num_reqs = draw(st.integers(min_value=1, max_value=5))
    reqs = [draw(requirement_dict(max_depth=max_depth - 1)) for _ in range(num_reqs)]
    title = draw(st.text(min_size=1, max_size=50))
    return {"reqs": reqs, "title": title}


# ============================================================================
# Helper functions
# ============================================================================

def collect_all_nodes(node: Node) -> list[Node]:
    """Recursively collect all nodes in a tree."""
    nodes = [node]
    if isinstance(node, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
        for child in node.children:
            nodes.extend(collect_all_nodes(child))
    return nodes


def count_leaves(node: Node) -> int:
    """Count leaf nodes in a tree."""
    if isinstance(node, (Course, GIR, HASS, CI, PlainString)):
        return 1
    if isinstance(node, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
        return sum(count_leaves(child) for child in node.children)
    return 0


def count_groups(node: Node) -> int:
    """Count group nodes in a tree."""
    if isinstance(node, (Course, GIR, HASS, CI, PlainString)):
        return 0
    if isinstance(node, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
        return 1 + sum(count_groups(child) for child in node.children)
    return 0


# ============================================================================
# Property-based tests
# ============================================================================

class TestParserInvariants:
    """Test invariants that should hold for all parser inputs."""

    @given(requirement_dict())
    @settings(max_examples=200)
    def test_parser_always_returns_valid_node(self, req_dict):
        """Property: Parser should always return a valid Node type for valid input."""
        result = parse(req_dict)
        assert isinstance(result, (Course, GIR, HASS, CI, PlainString, AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup))

    @given(requirement_dict())
    @settings(max_examples=200)
    def test_parsed_node_has_req_id(self, req_dict):
        """Property: Every parsed node should have a non-empty req_id."""
        result = parse(req_dict)
        assert result.req_id is not None
        assert len(result.req_id) > 0

    @given(fireroad_response())
    @settings(max_examples=100)
    def test_fireroad_response_always_returns_allgroup(self, response_dict):
        """Property: parse_fireroad_response always returns an AllGroup at root."""
        result = parse_fireroad_response(response_dict)
        assert isinstance(result, AllGroup)

    @given(requirement_dict())
    @settings(max_examples=200)
    def test_groups_have_at_least_one_child(self, req_dict):
        """Property: All groups should have at least one child."""
        result = parse(req_dict)
        for node in collect_all_nodes(result):
            if isinstance(node, (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)):
                assert len(node.children) >= 1, \
                    f"Group {type(node).__name__} has no children"

    @given(requirement_dict())
    @settings(max_examples=200)
    def test_threshold_groups_have_valid_cutoffs(self, req_dict):
        """Property: Threshold groups should have cutoff >= 1."""
        result = parse(req_dict)
        for node in collect_all_nodes(result):
            if isinstance(node, SubjectThresholdGroup):
                assert node.cutoff >= 1, f"SubjectThresholdGroup cutoff is {node.cutoff}"
                assert node.threshold_type in ("GTE", "LTE")
                assert node.connection_type in ("all", "any")
                if node.distinct_threshold:
                    assert node.distinct_threshold.cutoff >= 1
            elif isinstance(node, UnitThresholdGroup):
                assert node.cutoff >= 1, f"UnitThresholdGroup cutoff is {node.cutoff}"
                assert node.threshold_type in ("GTE", "LTE")

    @given(requirement_dict())
    @settings(max_examples=200)
    def test_all_nodes_are_well_formed(self, req_dict):
        """Property: All nodes should be well-formed (correct types, valid fields)."""
        result = parse(req_dict)
        for node in collect_all_nodes(result):
            # Every node has was_pruned field
            assert hasattr(node, 'was_pruned')
            assert node.was_pruned is False  # Parser never sets was_pruned

            # Every node has req_id
            assert node.req_id is not None

            # Type-specific checks
            if isinstance(node, Course):
                assert isinstance(node.subject_id, str)
                assert len(node.subject_id) > 0
            elif isinstance(node, GIR):
                assert node.gir_code in ("CAL1", "CAL2", "PHY1", "PHY2", "CHEM", "BIOL", "REST", "LAB", "LAB2")
            elif isinstance(node, HASS):
                assert node.category in ("HASS", "HASS-A", "HASS-H", "HASS-S", "HASS-E", None)
            elif isinstance(node, CI):
                assert node.ci_type in ("CI-H", "CI-HW")
            elif isinstance(node, PlainString):
                assert isinstance(node.description, str)


class TestLeafParsing:
    """Test leaf node parsing properties."""

    @given(valid_course_ids, optional_title)
    @settings(max_examples=100)
    def test_course_ids_parse_to_course(self, course_id, title):
        """Property: Standard course IDs parse to Course nodes."""
        req_dict = {"req": course_id}
        if title:
            req_dict["title"] = title
        result = parse(req_dict)
        assert isinstance(result, Course)
        assert result.subject_id == course_id
        assert result.title == title

    @given(valid_gir_codes, optional_title)
    @settings(max_examples=50)
    def test_gir_codes_parse_to_gir(self, gir_code, title):
        """Property: GIR codes parse to GIR nodes."""
        req_dict = {"req": f"GIR:{gir_code}"}
        if title:
            req_dict["title"] = title
        result = parse(req_dict)
        assert isinstance(result, GIR)
        assert result.gir_code == gir_code
        assert result.title == title

    @given(valid_hass_categories, optional_title)
    @settings(max_examples=50)
    def test_hass_categories_parse_to_hass(self, hass_cat, title):
        """Property: HASS categories parse to HASS nodes."""
        req_dict = {"req": hass_cat}
        if title:
            req_dict["title"] = title
        result = parse(req_dict)
        assert isinstance(result, HASS)
        assert result.category == hass_cat
        assert result.title == title

    @given(valid_ci_types, optional_title)
    @settings(max_examples=50)
    def test_ci_types_parse_to_ci(self, ci_type, title):
        """Property: CI types parse to CI nodes."""
        req_dict = {"req": ci_type}
        if title:
            req_dict["title"] = title
        result = parse(req_dict)
        assert isinstance(result, CI)
        assert result.ci_type == ci_type
        assert result.title == title

    @given(plain_string_descriptions, optional_title)
    @settings(max_examples=50)
    def test_plain_strings_parse_to_plainstring(self, desc, title):
        """Property: Plain-string marked items parse to PlainString."""
        req_dict = {"req": desc, "plain-string": True}
        if title:
            req_dict["title"] = title
        result = parse(req_dict)
        assert isinstance(result, PlainString)
        assert result.description == desc
        assert result.title == title


class TestGroupParsing:
    """Test group node parsing properties."""

    @given(st.lists(leaf_req_dict(), min_size=1, max_size=5), optional_title)
    @settings(max_examples=100)
    def test_all_connection_creates_allgroup(self, children, title):
        """Property: connection-type='all' creates AllGroup (without threshold)."""
        req_dict: dict = {"reqs": children, "connection-type": "all"}
        if title:
            req_dict["title"] = title
        result = parse(req_dict)
        assert isinstance(result, AllGroup)
        assert len(result.children) == len(children)
        assert result.title == title

    @given(st.lists(leaf_req_dict(), min_size=1, max_size=5), optional_title)
    @settings(max_examples=100)
    def test_any_connection_creates_anygroup(self, children, title):
        """Property: connection-type='any' creates AnyGroup (without threshold)."""
        req_dict: dict = {"reqs": children, "connection-type": "any"}
        if title:
            req_dict["title"] = title
        result = parse(req_dict)
        assert isinstance(result, AnyGroup)
        assert len(result.children) == len(children)
        assert result.title == title

    @given(st.lists(leaf_req_dict(), min_size=1, max_size=5))
    @settings(max_examples=50)
    def test_no_connection_defaults_to_allgroup(self, children):
        """Property: Missing connection-type defaults to AllGroup."""
        req_dict = {"reqs": children}
        result = parse(req_dict)
        assert isinstance(result, AllGroup)

    @given(
        st.lists(leaf_req_dict(), min_size=1, max_size=5),
        st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_subject_threshold_creates_subject_threshold_group(self, children, cutoff):
        """Property: Subject thresholds create SubjectThresholdGroup."""
        # Ensure cutoff makes sense
        cutoff = min(cutoff, len(children))
        req_dict = {
            "reqs": children,
            "threshold": {"cutoff": cutoff, "criterion": "subjects", "type": "GTE"},
        }
        result = parse(req_dict)
        assert isinstance(result, SubjectThresholdGroup)
        assert result.cutoff == cutoff
        assert result.threshold_type == "GTE"

    @given(
        st.lists(leaf_req_dict(), min_size=1, max_size=5),
        st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_unit_threshold_creates_unit_threshold_group(self, children, cutoff):
        """Property: Unit thresholds create UnitThresholdGroup."""
        req_dict = {
            "reqs": children,
            "threshold": {"cutoff": cutoff, "criterion": "units", "type": "GTE"},
        }
        result = parse(req_dict)
        assert isinstance(result, UnitThresholdGroup)
        assert result.cutoff == cutoff
        assert result.threshold_type == "GTE"

    @given(
        st.lists(leaf_req_dict(), min_size=2, max_size=5),
        st.integers(min_value=1, max_value=5),
        st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50)
    def test_distinct_threshold_is_preserved(self, children, cutoff, distinct_cutoff):
        """Property: Distinct thresholds are correctly parsed."""
        cutoff = min(cutoff, len(children))
        distinct_cutoff = min(distinct_cutoff, len(children))
        req_dict = {
            "reqs": children,
            "threshold": {"cutoff": cutoff, "criterion": "subjects", "type": "GTE"},
            "distinct-threshold": {"cutoff": distinct_cutoff, "type": "GTE"},
        }
        result = parse(req_dict)
        assert isinstance(result, SubjectThresholdGroup)
        assert result.distinct_threshold is not None
        assert result.distinct_threshold.cutoff == distinct_cutoff


class TestIDGeneration:
    """Test ID generation properties."""

    @given(requirement_dict())
    @settings(max_examples=100)
    def test_all_req_ids_are_unique(self, req_dict):
        """Property: All req_ids in a tree should be unique."""
        result = parse(req_dict)
        all_nodes = collect_all_nodes(result)
        req_ids = [node.req_id for node in all_nodes]
        assert len(req_ids) == len(set(req_ids)), \
            f"Duplicate req_ids found: {[rid for rid in req_ids if req_ids.count(rid) > 1]}"

    @given(fireroad_response())
    @settings(max_examples=50)
    def test_fireroad_ids_use_title_as_prefix(self, response_dict):
        """Property: IDs should use the title as a hierarchical prefix."""
        result = parse_fireroad_response(response_dict)
        # Root should use a slug of the title as its req_id
        assert result.req_id is not None
        # All children should have IDs that start with root's ID
        for child in result.children:
            assert child.req_id is not None
            assert child.req_id.startswith(result.req_id + "/")


class TestErrorHandling:
    """Test error handling properties."""

    @given(st.dictionaries(st.text(min_size=1), st.text()))
    @settings(max_examples=50)
    def test_missing_req_or_reqs_raises_error(self, random_dict):
        """Property: Dicts without 'req' or 'reqs' should raise ParseError."""
        # Filter out dicts that happen to have 'req' or 'reqs'
        assume('req' not in random_dict and 'reqs' not in random_dict)

        with pytest.raises(ParseError):
            parse(random_dict)

    @given(st.text())
    @settings(max_examples=50)
    def test_non_list_reqs_raises_error(self, bad_reqs):
        """Property: 'reqs' must be a list."""
        # Skip actual lists
        assume(not isinstance(bad_reqs, list))

        req_dict = {"reqs": bad_reqs}
        with pytest.raises(ParseError):
            parse(req_dict)


class TestTreeStructure:
    """Test tree structure properties."""

    @given(requirement_dict(max_depth=4))
    @settings(max_examples=100)
    def test_tree_depth_preserved(self, req_dict):
        """Property: Parser preserves nesting structure."""
        result = parse(req_dict)

        # Count leaves in input and output should match
        def count_input_leaves(d):
            if 'req' in d and 'reqs' not in d:
                return 1
            if 'reqs' in d:
                return sum(count_input_leaves(child) for child in d['reqs'])
            return 0

        input_leaves = count_input_leaves(req_dict)
        output_leaves = count_leaves(result)
        assert input_leaves == output_leaves, \
            f"Leaf count mismatch: input={input_leaves}, output={output_leaves}"

    @given(fireroad_response(max_depth=3))
    @settings(max_examples=50)
    def test_requirement_list_children_count(self, response_dict):
        """Property: Top-level AllGroup has same number of children as input reqs."""
        result = parse_fireroad_response(response_dict)
        assert isinstance(result, AllGroup)
        assert len(result.children) == len(response_dict['reqs'])


class TestRoundTripProperties:
    """Test properties that verify parser behavior consistency."""

    @given(requirement_dict())
    @settings(max_examples=100)
    def test_parsing_is_deterministic(self, req_dict):
        """Property: Parsing the same input twice produces identical results."""
        result1 = parse(req_dict)
        result2 = parse(req_dict)
        assert result1 == result2

    @given(fireroad_response())
    @settings(max_examples=50)
    def test_fireroad_parsing_is_deterministic(self, response_dict):
        """Property: Parsing a Fireroad response twice produces identical results."""
        result1 = parse_fireroad_response(response_dict)
        result2 = parse_fireroad_response(response_dict)
        assert result1 == result2
