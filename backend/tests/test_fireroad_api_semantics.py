"""
Empirical tests to understand Fireroad API semantics for thresholds and connection types.

We'll send various course combinations to the Fireroad API for real majors and observe
how threshold counting and connection types actually work.
"""

import json
from typing import Any

import requests


def query_fireroad_progress(major_key: str, courses: list[str]) -> dict[str, Any]:
    """
    Query Fireroad API for requirement progress.

    Args:
        major_key: The major/requirement key (e.g., 'major6-3new', 'major1', 'major7')
        courses: List of course IDs to check

    Returns:
        The API response as a dict
    """
    # Convert course IDs to the format Fireroad expects
    selected_subjects = []
    for i, course_id in enumerate(courses):
        selected_subjects.append({
            'subject_id': course_id,
            'title': course_id,
            'units': 12,
            'semester': i + 1
        })

    payload = {
        'coursesOfStudy': [major_key],
        'selectedSubjects': selected_subjects,
        'progressAssertions': {}
    }

    response = requests.post(
        f'https://fireroad.mit.edu/requirements/progress/{major_key}/',
        json=payload,
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        },
        timeout=30
    )

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API request failed: {response.status_code}\n{response.text}")


def find_requirement_by_title(node: Any, title: str) -> dict | None:
    """Recursively find a requirement by title in the response tree."""
    if isinstance(node, dict):
        if node.get('title') == title:
            return node
        if 'reqs' in node:
            for child in node['reqs']:
                found = find_requirement_by_title(child, title)
                if found:
                    return found
    return None


def find_requirement_by_path(node: Any, path_segments: list[str]) -> dict | None:
    """Find a requirement by following a path of titles."""
    current = node
    for segment in path_segments:
        current = find_requirement_by_title(current, segment)
        if current is None:
            return None
    return current


def print_requirement_status(req: dict, indent: int = 0) -> None:
    """Pretty print requirement status."""
    prefix = "  " * indent
    title = req.get('title', 'untitled')
    fulfilled = req.get('fulfilled', False)
    progress = req.get('progress', 0)
    min_val = req.get('min', 0)
    max_val = req.get('max', 0)
    threshold = req.get('threshold')
    conn_type = req.get('connection-type')

    status_icon = "✓" if fulfilled else "✗"

    print(f"{prefix}{status_icon} {title}")
    print(f"{prefix}   fulfilled={fulfilled}, progress={progress}/{min_val}-{max_val}")

    if threshold:
        print(f"{prefix}   threshold: {threshold}")
    if conn_type:
        print(f"{prefix}   connection-type: {conn_type}")

    # Print matched courses if any
    if 'reqs' in req:
        for child in req['reqs']:
            if isinstance(child, str):
                print(f"{prefix}   - {child}")
            elif isinstance(child, dict):
                if 'req' in child:
                    child_fulfilled = child.get('fulfilled', False)
                    child_icon = "✓" if child_fulfilled else "✗"
                    print(f"{prefix}   {child_icon} {child['req']}")


def save_full_response(major_key: str, courses: list[str], filename: str) -> None:
    """Save full API response to a file for inspection."""
    result = query_fireroad_progress(major_key, courses)
    with open(filename, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Full response saved to {filename}")


def test_major6_3new_aus_bug():
    """
    Test the actual AUS bug scenario from major6-3new.

    Question: Does taking 6.C01 + 18.404 (without 6.C011) satisfy AUS?
    - AUS has threshold: 2 subjects, connection: any
    - Contains a nested group with connection: all containing 6.C01 and 6.C011
    """
    print("\n" + "="*80)
    print("TEST 1: Major 6-3 (new) - AUS Bug Scenario")
    print("="*80)

    # Scenario 1: Only 6.C01 + 18.404 (group not satisfied)
    print("\n--- Scenario 1a: 6.C01 + 18.404 (missing 6.C011) ---")
    result = query_fireroad_progress('major6-3new', ['6.C01', '18.404'])
    aus = find_requirement_by_title(result, 'AUS')
    if aus:
        print_requirement_status(aus)

        # Find the 6.C01/6.C011 group
        if 'reqs' in aus:
            for idx, child in enumerate(aus['reqs']):
                if isinstance(child, dict) and 'reqs' in child:
                    child_courses = []
                    for grandchild in child.get('reqs', []):
                        if isinstance(grandchild, str):
                            child_courses.append(grandchild)
                        elif isinstance(grandchild, dict) and 'req' in grandchild:
                            child_courses.append(grandchild['req'])

                    if '6.C01' in child_courses and '6.C011' in child_courses:
                        print(f"\n  Found nested group at index {idx}:")
                        print_requirement_status(child, indent=1)

    # Scenario 1b: Both 6.C01 + 6.C011 + 18.404 (group satisfied)
    print("\n--- Scenario 1b: 6.C01 + 6.C011 + 18.404 (group satisfied) ---")
    result = query_fireroad_progress('major6-3new', ['6.C01', '6.C011', '18.404'])
    aus = find_requirement_by_title(result, 'AUS')
    if aus:
        print_requirement_status(aus)

        # Find the group again
        if 'reqs' in aus:
            for idx, child in enumerate(aus['reqs']):
                if isinstance(child, dict) and 'reqs' in child:
                    child_courses = []
                    for grandchild in child.get('reqs', []):
                        if isinstance(grandchild, str):
                            child_courses.append(grandchild)
                        elif isinstance(grandchild, dict) and 'req' in grandchild:
                            child_courses.append(grandchild['req'])

                    if '6.C01' in child_courses and '6.C011' in child_courses:
                        print(f"\n  Found nested group at index {idx}:")
                        print_requirement_status(child, indent=1)

    # Scenario 1c: Only 18.404 and one other AUS course (no group courses)
    print("\n--- Scenario 1c: 18.404 + 6.3100 (no group courses at all) ---")
    result = query_fireroad_progress('major6-3new', ['18.404', '6.3100'])
    aus = find_requirement_by_title(result, 'AUS')
    if aus:
        print_requirement_status(aus)

    # Save full response for detailed inspection
    save_full_response('major6-3new', ['6.C01', '18.404'],
                      'fireroad_response_major6-3new_aus_bug.json')


def test_major1_girs():
    """
    Test Course 1 (Civil Engineering) requirements.

    Look for examples of threshold + connection-type combinations.
    """
    print("\n" + "="*80)
    print("TEST 2: Major 1 (Civil Engineering)")
    print("="*80)

    # Get some basic Course 1 classes
    courses = ['1.00', '1.010', '1.020', '1.041', '18.03']

    print(f"\n--- Testing with courses: {courses} ---")
    result = query_fireroad_progress('major1', courses)

    # Print top-level requirements
    if 'reqs' in result:
        for req in result['reqs']:
            if isinstance(req, dict) and 'title' in req:
                print(f"\n{req['title']}:")
                print_requirement_status(req, indent=1)

    save_full_response('major1', courses, 'fireroad_response_major1.json')


def test_major7_bio():
    """
    Test Course 7 (Biology) requirements.

    Biology has complex nested requirements with various thresholds.
    """
    print("\n" + "="*80)
    print("TEST 3: Major 7 (Biology)")
    print("="*80)

    # Get some basic Course 7 classes
    courses = ['7.002', '7.003', '7.004', '7.005', '7.06', '5.12']

    print(f"\n--- Testing with courses: {courses} ---")
    result = query_fireroad_progress('major7', courses)

    # Print top-level requirements
    if 'reqs' in result:
        for req in result['reqs']:
            if isinstance(req, dict) and 'title' in req:
                print(f"\n{req['title']}:")
                print_requirement_status(req, indent=1)

    save_full_response('major7', courses, 'fireroad_response_major7.json')


def test_major2_meche():
    """
    Test Course 2 (Mechanical Engineering) requirements.

    Look for threshold examples with units criterion.
    """
    print("\n" + "="*80)
    print("TEST 4: Major 2 (Mechanical Engineering)")
    print("="*80)

    # Get some basic Course 2 classes
    courses = ['2.001', '2.002', '2.003', '2.004', '2.005', '2.006']

    print(f"\n--- Testing with courses: {courses} ---")
    result = query_fireroad_progress('major2', courses)

    # Print top-level requirements
    if 'reqs' in result:
        for req in result['reqs']:
            if isinstance(req, dict) and 'title' in req:
                print(f"\n{req['title']}:")
                print_requirement_status(req, indent=1)

    save_full_response('major2', courses, 'fireroad_response_major2.json')


def test_comprehensive_aus_variations():
    """
    Test many variations of the AUS scenario to understand threshold semantics.
    """
    print("\n" + "="*80)
    print("TEST 5: Comprehensive AUS Variations")
    print("="*80)

    test_cases = [
        ("6.C01 only", ['6.C01']),
        ("6.C011 only", ['6.C011']),
        ("6.C01 + 6.C011 (group complete)", ['6.C01', '6.C011']),
        ("6.C01 + one other AUS", ['6.C01', '6.3900']),
        ("6.C011 + one other AUS", ['6.C011', '6.3900']),
        ("Two non-group AUS", ['6.3900', '18.404']),
        ("Three non-group AUS", ['6.3900', '18.404', '6.3100']),
        ("Group + one non-group", ['6.C01', '6.C011', '18.404']),
        ("Group + two non-group", ['6.C01', '6.C011', '18.404', '6.3900']),
    ]

    for name, courses in test_cases:
        print(f"\n--- {name}: {courses} ---")
        result = query_fireroad_progress('major6-3new', courses)
        aus = find_requirement_by_title(result, 'AUS')
        if aus:
            fulfilled = aus.get('fulfilled', False)
            progress = aus.get('progress', 0)
            min_val = aus.get('min', 0)
            status = "✓ SATISFIED" if fulfilled else "✗ NOT SATISFIED"
            print(f"  AUS: {status} (progress={progress}/{min_val})")

            # Check the nested group
            if 'reqs' in aus:
                for child in aus['reqs']:
                    if isinstance(child, dict) and 'reqs' in child:
                        child_courses = []
                        for grandchild in child.get('reqs', []):
                            if isinstance(grandchild, str):
                                child_courses.append(grandchild)
                            elif isinstance(grandchild, dict) and 'req' in grandchild:
                                child_courses.append(grandchild['req'])

                        if '6.C01' in child_courses and '6.C011' in child_courses:
                            group_fulfilled = child.get('fulfilled', False)
                            group_progress = child.get('progress', 0)
                            group_min = child.get('min', 0)
                            group_status = "✓ SATISFIED" if group_fulfilled else "✗ NOT SATISFIED"
                            print(f"  Nested group (6.C01/6.C011): {group_status} (progress={group_progress}/{group_min})")
                            break


def test_units_criterion_semantics():
    """
    Test threshold with criterion='units' to understand counting semantics.

    Major 1 has "Elective Subjects with Engineering Content" with:
    - threshold: 48 units, criterion='units'

    We'll test various combinations to see if it counts:
    A) Units from all leaf courses
    B) Units from satisfied direct children only
    """
    print("\n" + "="*80)
    print("TEST 6: Units Criterion Semantics (Major 1)")
    print("="*80)

    # Test with courses that have different unit values
    test_cases = [
        ("One 12-unit course", ["1.00"], 12),
        ("Two 12-unit courses", ["1.00", "1.020"], 24),
        ("Three 12-unit courses", ["1.00", "1.020", "1.041"], 36),
        ("Four 12-unit courses", ["1.00", "1.020", "1.041", "1.050"], 48),
    ]

    for name, courses, expected_units in test_cases:
        print(f"\n--- {name}: {courses} (expected: {expected_units} units) ---")

        # Need to set actual unit values for these courses
        selected_subjects = []
        for i, course_id in enumerate(courses):
            selected_subjects.append({
                'subject_id': course_id,
                'title': course_id,
                'units': 12,  # All Course 1 classes are typically 12 units
                'semester': i + 1
            })

        payload = {
            'coursesOfStudy': ['major1'],
            'selectedSubjects': selected_subjects,
            'progressAssertions': {}
        }

        response = requests.post(
            'https://fireroad.mit.edu/requirements/progress/major1/',
            json=payload,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            elective = find_requirement_by_title(result, 'Elective Subjects with Engineering Content')
            if elective:
                fulfilled = elective.get('fulfilled', False)
                progress = elective.get('progress', 0)
                min_val = elective.get('min', 0)
                max_val = elective.get('max', 0)
                threshold = elective.get('threshold')

                status = "✓ SATISFIED" if fulfilled else "✗ NOT SATISFIED"
                print(f"  Electives: {status}")
                print(f"  Progress: {progress}/{max_val} units")
                print(f"  Threshold: {threshold}")


def test_major2_units_with_groups():
    """
    Test if nested groups affect unit counting.

    Look for Major 2 requirements that might have nested groups with units criterion.
    """
    print("\n" + "="*80)
    print("TEST 7: Units with Nested Groups (if any exist)")
    print("="*80)

    # First, let's see what the structure looks like
    courses = ["2.001", "2.002", "2.003", "2.004"]
    result = query_fireroad_progress('major2', courses)

    # Look for any requirement with units threshold
    def find_units_thresholds(node, path=""):
        results = []
        if isinstance(node, dict):
            threshold = node.get('threshold')
            if threshold and threshold.get('criterion') == 'units':
                results.append({
                    'path': path,
                    'title': node.get('title', 'untitled'),
                    'threshold': threshold,
                    'has_nested_groups': any(
                        isinstance(child, dict) and 'reqs' in child
                        for child in node.get('reqs', [])
                    )
                })

            if 'reqs' in node:
                for i, child in enumerate(node['reqs']):
                    child_path = f"{path}/{node.get('title', f'child{i}')}" if path else node.get('title', 'root')
                    results.extend(find_units_thresholds(child, child_path))

        return results

    units_reqs = find_units_thresholds(result)

    if units_reqs:
        print(f"\nFound {len(units_reqs)} requirements with units threshold:")
        for req in units_reqs:
            print(f"  - {req['path']}: {req['threshold']}")
            print(f"    Has nested groups: {req['has_nested_groups']}")
    else:
        print("  No requirements with units threshold found in this test")


def main():
    """Run all tests."""
    print("\nFireroad API Semantics Investigation")
    print("=" * 80)
    print("Goal: Understand how threshold and connection-type interact")
    print("=" * 80)

    try:
        # Run all tests
        test_major6_3new_aus_bug()
        test_comprehensive_aus_variations()
        test_units_criterion_semantics()
        test_major2_units_with_groups()
        test_major1_girs()
        test_major7_bio()
        test_major2_meche()

        print("\n" + "="*80)
        print("All tests completed!")
        print("Check the generated JSON files for full response details.")
        print("="*80)

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
