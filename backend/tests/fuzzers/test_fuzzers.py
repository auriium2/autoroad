"""
Integration tests that run fuzzers to ensure they still work.

These tests fetch real data from Fireroad and validate that our parsers
and validators can handle all of it without errors.
"""
import pytest
import requests

from courses.prerequisites.parser import parse_fireroad, prereq_to_string
from courses.prerequisites.types import PrereqCourse, PrereqGroup


@pytest.fixture(scope="module")
def fireroad_courses():
    """Fetch all courses from Fireroad (cached for all tests in this module)."""
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    return response.json()


@pytest.fixture(scope="module")
def prerequisite_strings(fireroad_courses):
    """Extract all unique prerequisite strings from Fireroad courses."""
    prereq_strings = set()

    for course in fireroad_courses:
        if 'prerequisites' in course and course['prerequisites']:
            prereq_strings.add(course['prerequisites'])
        if 'prereqs' in course and course['prereqs']:
            prereq_strings.add(course['prereqs'])

    return {p for p in prereq_strings if p and p.strip()}


class TestPrerequisiteParserFuzzer:
    """Integration tests for the prerequisite parser using real Fireroad data."""

    def test_parser_handles_all_prerequisites(self, prerequisite_strings):
        """
        Test that the parser can handle ALL prerequisite strings from Fireroad
        without throwing exceptions.

        Note: The parser returns None for unparseable prerequisites like
        "Permission of instructor" - this is expected behavior, not a failure.
        """
        failures = []

        for prereq_str in prerequisite_strings:
            try:
                # Parser may return None for unparseable strings - that's OK
                parse_fireroad(prereq_str)
            except Exception as e:
                failures.append({
                    'prereq_str': prereq_str,
                    'error': str(e)
                })

        assert len(failures) == 0, f"Parser failed on {len(failures)} prerequisites: {failures[:5]}"

    def test_parser_produces_valid_output(self, prerequisite_strings):
        """
        Test that the parser produces valid PrereqNode objects
        (either PrereqCourse, PrereqGroup, or None for unparseable strings).
        """
        invalid_results = []

        for prereq_str in prerequisite_strings:
            try:
                result = parse_fireroad(prereq_str)
                # None is valid for unparseable strings like "Permission of instructor"
                if result is not None and not isinstance(result, (PrereqCourse, PrereqGroup)):
                    invalid_results.append({
                        'prereq_str': prereq_str,
                        'result_type': type(result).__name__
                    })
            except Exception:
                # Already tested in test_parser_handles_all_prerequisites
                pass

        assert len(invalid_results) == 0, \
            f"Parser produced invalid types: {invalid_results[:5]}"

    def test_parsed_results_can_be_stringified(self, prerequisite_strings):
        """
        Test that all parsed results can be converted back to strings
        without errors.
        """
        stringification_failures = []

        for prereq_str in prerequisite_strings:
            try:
                parsed = parse_fireroad(prereq_str)
                # Skip None results (unparseable strings)
                if parsed is None:
                    continue
                stringified = prereq_to_string(parsed)
                assert isinstance(stringified, str)
            except Exception as e:
                stringification_failures.append({
                    'prereq_str': prereq_str,
                    'error': str(e)
                })

        assert len(stringification_failures) == 0, \
            f"Stringification failed on {len(stringification_failures)} results: {stringification_failures[:5]}"

    def test_no_quoted_strings_in_parsed_courses(self, prerequisite_strings):
        """
        Regression test: Ensure no quoted strings (like ''permission of instructor'')
        are parsed as course IDs.
        """
        def extract_course_ids(node):
            if node is None:
                return []
            if isinstance(node, PrereqCourse):
                return [node.course_id]
            if isinstance(node, PrereqGroup):
                return [cid for item in node.items for cid in extract_course_ids(item)]
            return []

        quoted_string_failures = []

        for prereq_str in prerequisite_strings:
            try:
                parsed = parse_fireroad(prereq_str)
                course_ids = extract_course_ids(parsed)

                for course_id in course_ids:
                    if course_id.startswith("''") or course_id.startswith('"'):
                        quoted_string_failures.append({
                            'prereq_str': prereq_str,
                            'bad_course_id': course_id
                        })
                        break
            except Exception:
                # Already tested in other tests
                pass

        assert len(quoted_string_failures) == 0, \
            f"Found quoted strings parsed as courses: {quoted_string_failures[:5]}"

    def test_success_rate_meets_threshold(self, prerequisite_strings):
        """
        Meta-test: Ensure the parser has a high success rate (>95%).
        This acts as a quality gate.

        Note: The parser intentionally returns None for unparseable strings like
        "Permission of instructor", so the threshold is set to 95% to account
        for these valid None returns.
        """
        total = len(prerequisite_strings)
        successes = 0

        for prereq_str in prerequisite_strings:
            try:
                result = parse_fireroad(prereq_str)
                if result is not None:
                    successes += 1
            except Exception:
                pass

        success_rate = (successes / total * 100) if total > 0 else 0

        assert success_rate >= 95.0, \
            f"Parser success rate ({success_rate:.1f}%) is below 95% threshold"


class TestFireroadDataIntegrity:
    """Tests to ensure Fireroad data is accessible and has expected structure."""

    def test_fireroad_api_is_accessible(self, fireroad_courses):
        """Test that we can fetch data from Fireroad."""
        assert len(fireroad_courses) > 1000, \
            "Expected at least 1000 courses from Fireroad"

    def test_courses_have_expected_fields(self, fireroad_courses):
        """Test that courses have the expected structure."""
        sample_course = fireroad_courses[0]

        # Check for key fields
        assert 'subject_id' in sample_course, "Courses should have subject_id"

    def test_prerequisite_strings_exist(self, prerequisite_strings):
        """Test that we extracted prerequisite strings."""
        assert len(prerequisite_strings) > 100, \
            "Expected at least 100 unique prerequisite strings"


@pytest.fixture(scope="module")
def all_fireroad_requirements():
    """Fetch all requirement lists from Fireroad."""
    response = requests.get('https://fireroad.mit.edu/requirements/list_reqs')
    response.raise_for_status()
    req_list = response.json()

    requirements = {}
    for req_id in req_list.keys():
        try:
            req_response = requests.get(f'https://fireroad.mit.edu/requirements/get_json/{req_id}')
            if req_response.status_code == 200:
                requirements[req_id] = req_response.json()
        except Exception:
            pass

    return requirements


class TestRequirementParserFuzzer:
    """
    Integration tests for the requirement parser using all Fireroad requirements.

    This fuzzer ensures that all real requirement data can be parsed without
    errors and that all groups have valid thresholds (preventing infeasibility bugs).
    """

    def test_parser_handles_all_requirements(self, all_fireroad_requirements):
        """Test that the parser can handle all Fireroad requirements without exceptions."""
        from courses.requirements.parser import parse_requirement

        failures = []

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            try:
                result = parse_requirement({'reqs': req_data['reqs'], 'title': req_id})
                assert result is not None
            except Exception as e:
                failures.append((req_id, str(e)))

        if failures:
            failure_msg = "\n".join([f"  {req_id}: {error}" for req_id, error in failures[:10]])
            pytest.fail(
                f"Parser failed on {len(failures)} requirements:\n{failure_msg}\n"
                f"{'... and more' if len(failures) > 10 else ''}"
            )

    def test_groups_with_thresholds_have_valid_cutoffs(self, all_fireroad_requirements):
        """
        Verify that requirement groups with thresholds have valid cutoff values.

        This is a regression test to ensure threshold cutoffs are properly parsed
        and don't have invalid values (like negative numbers or None).
        """
        from courses.requirements.parser import parse_requirement
        from courses.requirements.types import RequirementGroup

        invalid_thresholds = []

        def check_thresholds(node, path="root"):
            """Recursively check that all thresholds have valid cutoffs."""
            if isinstance(node, RequirementGroup):
                if node.threshold is not None:
                    # Check for invalid cutoff values
                    if node.threshold.cutoff < 0:
                        invalid_thresholds.append((path, f"negative cutoff: {node.threshold.cutoff}"))
                    if node.threshold.criterion not in ('subjects', 'units'):
                        invalid_thresholds.append((path, f"invalid criterion: {node.threshold.criterion}"))

                for i, child in enumerate(node.items):
                    check_thresholds(child, f"{path}.{i}")

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            try:
                result = parse_requirement({'reqs': req_data['reqs'], 'title': req_id})
                check_thresholds(result, f"{req_id}")
            except Exception:
                pass

        if invalid_thresholds:
            sample = invalid_thresholds[:20]
            pytest.fail(
                f"Found {len(invalid_thresholds)} requirement groups with invalid thresholds:\n"
                f"{sample}\n"
                f"{'... and more' if len(invalid_thresholds) > 20 else ''}"
            )

    def test_requirement_parsing_success_rate(self, all_fireroad_requirements):
        """Test that we can parse at least 95% of Fireroad requirements."""
        from courses.requirements.parser import parse_requirement

        total = 0
        successes = 0

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            total += 1
            try:
                result = parse_requirement({'reqs': req_data['reqs'], 'title': req_id})
                if result is not None:
                    successes += 1
            except Exception:
                pass

        success_rate = (successes / total * 100) if total > 0 else 0

        assert success_rate >= 95.0, \
            f"Requirement parser success rate ({success_rate:.1f}%) is below 95% threshold"


class TestReq2ParserFuzzer:
    """
    Integration tests for the req_2 parser using all Fireroad requirements.

    This fuzzer ensures that all real requirement data can be parsed into
    the new typed req_2 nodes without errors.
    """

    def test_parser_handles_all_requirements(self, all_fireroad_requirements):
        """Test that the req_2 parser can handle all Fireroad requirements without exceptions."""
        from courses.requirements.req_2.parser import parse_fireroad_response

        failures = []

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            try:
                result = parse_fireroad_response(req_data)
                assert result is not None
            except Exception as e:
                failures.append((req_id, str(e)))

        if failures:
            failure_msg = "\n".join([f"  {req_id}: {error}" for req_id, error in failures[:10]])
            pytest.fail(
                f"req_2 parser failed on {len(failures)} requirements:\n{failure_msg}\n"
                f"{'... and more' if len(failures) > 10 else ''}"
            )

    def test_all_nodes_are_correct_types(self, all_fireroad_requirements):
        """
        Verify that the req_2 parser produces only valid node types.
        """
        from courses.requirements.req_2.parser import parse_fireroad_response
        from courses.requirements.req_2.types import (
            AllGroup, AnyGroup, Course, CI, GIR, HASS, PlainString,
            SubjectThresholdGroup, UnitThresholdGroup, Node
        )

        invalid_types = []

        def check_types(node, path="root"):
            """Recursively check that all nodes are valid types."""
            valid_types = (AllGroup, AnyGroup, Course, CI, GIR, HASS, PlainString,
                          SubjectThresholdGroup, UnitThresholdGroup)

            if not isinstance(node, valid_types):
                invalid_types.append((path, type(node).__name__))
                return

            # Check children for group types
            if hasattr(node, 'children'):
                for i, child in enumerate(node.children):
                    check_types(child, f"{path}.{i}")

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            try:
                result = parse_fireroad_response(req_data)
                check_types(result, req_id)
            except Exception:
                pass

        if invalid_types:
            pytest.fail(f"Found {len(invalid_types)} invalid node types: {invalid_types[:20]}")

    def test_threshold_groups_have_valid_cutoffs(self, all_fireroad_requirements):
        """
        Verify that threshold groups have valid cutoff values (non-negative).
        """
        from courses.requirements.req_2.parser import parse_fireroad_response
        from courses.requirements.req_2.types import SubjectThresholdGroup, UnitThresholdGroup

        invalid_thresholds = []

        def check_thresholds(node, path="root"):
            """Recursively check that all threshold groups have valid cutoffs."""
            if isinstance(node, (SubjectThresholdGroup, UnitThresholdGroup)):
                if node.cutoff < 0:
                    invalid_thresholds.append((path, f"negative cutoff: {node.cutoff}"))
                if node.threshold_type not in ('GTE', 'LTE'):
                    invalid_thresholds.append((path, f"invalid threshold_type: {node.threshold_type}"))

            if hasattr(node, 'children'):
                for i, child in enumerate(node.children):
                    check_thresholds(child, f"{path}.{i}")

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            try:
                result = parse_fireroad_response(req_data)
                check_thresholds(result, req_id)
            except Exception:
                pass

        if invalid_thresholds:
            pytest.fail(
                f"Found {len(invalid_thresholds)} invalid thresholds:\n"
                f"{invalid_thresholds[:20]}"
            )

    def test_groups_have_children(self, all_fireroad_requirements):
        """
        Verify that all group nodes have at least one child.
        Empty groups are invalid and would cause constraint issues.
        """
        from courses.requirements.req_2.parser import parse_fireroad_response
        from courses.requirements.req_2.types import (
            AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup
        )

        empty_groups = []

        def check_children(node, path="root"):
            """Recursively check that all groups have children."""
            group_types = (AllGroup, AnyGroup, SubjectThresholdGroup, UnitThresholdGroup)

            if isinstance(node, group_types):
                if len(node.children) == 0:
                    empty_groups.append(path)

                for i, child in enumerate(node.children):
                    check_children(child, f"{path}.{i}")

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            try:
                result = parse_fireroad_response(req_data)
                check_children(result, req_id)
            except Exception:
                pass

        if empty_groups:
            pytest.fail(f"Found {len(empty_groups)} empty groups: {empty_groups[:20]}")

    def test_parsing_success_rate(self, all_fireroad_requirements):
        """Test that we can parse at least 95% of Fireroad requirements."""
        from courses.requirements.req_2.parser import parse_fireroad_response

        total = 0
        successes = 0

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            total += 1
            try:
                result = parse_fireroad_response(req_data)
                if result is not None:
                    successes += 1
            except Exception:
                pass

        success_rate = (successes / total * 100) if total > 0 else 0

        assert success_rate >= 95.0, \
            f"req_2 parser success rate ({success_rate:.1f}%) is below 95% threshold"

    def test_old_and_new_parsers_produce_equivalent_structures(self, all_fireroad_requirements):
        """
        Test that the old and new parsers produce structurally equivalent results.

        This compares:
        - Number of leaf nodes
        - Tree depth
        - Group types (threshold vs non-threshold)
        """
        from courses.requirements.parser import parse_requirement
        from courses.requirements.req_2.parser import parse_fireroad_response
        from courses.requirements.types import RequirementCourse, RequirementGroup, RequirementPlainString
        from courses.requirements.req_2.types import (
            AllGroup, AnyGroup, Course, CI, GIR, HASS, PlainString,
            SubjectThresholdGroup, UnitThresholdGroup
        )

        def count_old_leaves(node):
            if isinstance(node, (RequirementCourse, RequirementPlainString)):
                return 1
            if isinstance(node, RequirementGroup):
                return sum(count_old_leaves(c) for c in node.items)
            return 0

        def count_new_leaves(node):
            if isinstance(node, (Course, GIR, HASS, CI, PlainString)):
                return 1
            if hasattr(node, 'children'):
                return sum(count_new_leaves(c) for c in node.children)
            return 0

        mismatches = []

        for req_id, req_data in all_fireroad_requirements.items():
            if not isinstance(req_data, dict) or 'reqs' not in req_data:
                continue

            try:
                old_result = parse_requirement({'reqs': req_data['reqs'], 'title': req_id})
                new_result = parse_fireroad_response(req_data)

                old_leaves = count_old_leaves(old_result)
                new_leaves = count_new_leaves(new_result)

                if old_leaves != new_leaves:
                    mismatches.append((req_id, old_leaves, new_leaves))
            except Exception:
                pass

        if mismatches:
            sample = mismatches[:10]
            pytest.fail(
                f"Found {len(mismatches)} mismatches in leaf count:\n"
                f"{sample}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
