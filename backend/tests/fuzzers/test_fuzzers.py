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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
