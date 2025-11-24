"""
Empirical tests to discover Fireroad's actual threshold and connection-type semantics.

We use the real major6-3new requirement structure and test edge cases to understand:
1. Does threshold with criterion='subjects' count leaf courses or respect group boundaries?
2. What does connection-type='any' + threshold mean?
3. Are constraints bidirectional?
"""

import requests


def query_fireroad(courses: list[str]) -> dict:
    """Query Fireroad API for major6-3new with given courses."""
    # Convert course IDs to the format Fireroad expects
    selected_subjects = []
    for i, course_id in enumerate(courses):
        selected_subjects.append({
            'subject_id': course_id,
            'title': course_id,  # We don't care about the title for testing
            'units': 12,  # Default units
            'semester': i + 1  # Just put them in consecutive semesters
        })

    payload = {
        'coursesOfStudy': ['major6-3new'],
        'selectedSubjects': selected_subjects,
        'progressAssertions': {}
    }

    response = requests.post(
        'https://fireroad.mit.edu/requirements/progress/major6-3new/',
        json=payload,
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        },
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code}\n{response.text}")

    return response.json()


def find_requirement(node, title):
    """Recursively find a requirement by title."""
    if isinstance(node, dict):
        if node.get('title') == title:
            return node
        if 'reqs' in node:
            for child in node['reqs']:
                found = find_requirement(child, title)
                if found:
                    return found
    return None


def print_requirement_status(req: dict, indent: int = 0):
    """Print requirement status in a readable format."""
    prefix = "  " * indent
    title = req.get('title', req.get('req', 'unnamed'))
    fulfilled = req.get('fulfilled', False)
    progress = req.get('progress', '?')
    min_val = req.get('min')
    max_val = req.get('max')

    status = "✓" if fulfilled else "✗"

    if min_val is not None or max_val is not None:
        print(f"{prefix}{status} {title}: {progress}/{max_val or '?'}")
    else:
        print(f"{prefix}{status} {title}: {progress}")


def test_aus_with_partial_group():
    """
    Test: AUS with only 6.C01 (not 6.C011) + 18.404

    AUS structure:
    - threshold: 2 subjects, criterion='subjects', connection='any'
    - 52 individual courses (including 18.404)
    - 1 group at index 48: connection='all' with [6.C01, 6.C011]

    Question: If we take 6.C01 + 18.404, does AUS count:
      A) 2 leaf courses (6.C01 + 18.404) → fulfilled
      B) 1 child + partial group → not fulfilled
    """
    print("\n" + "="*80)
    print("TEST 1: AUS with partial group (6.C01 + 18.404, missing 6.C011)")
    print("="*80)

    courses = ["6.C01", "18.404"]
    result = query_fireroad(courses)
    aus = find_requirement(result, 'AUS')

    if aus:
        print("\nAUS Result:")
        print(f"  fulfilled: {aus.get('fulfilled')}")
        print(f"  progress: {aus.get('progress')}")
        print(f"  max: {aus.get('max')}")

        # Find the 6.C01/6.C011 group
        if 'reqs' in aus:
            for child in aus['reqs']:
                if isinstance(child, dict) and 'reqs' in child:
                    child_courses = []
                    for gc in child.get('reqs', []):
                        course_id = gc if isinstance(gc, str) else gc.get('req')
                        if course_id:
                            child_courses.append(course_id)

                    if '6.C01' in child_courses and '6.C011' in child_courses:
                        print("\n  6.C01/6.C011 group:")
                        print(f"    fulfilled: {child.get('fulfilled')}")
                        print(f"    progress: {child.get('progress')}")

                        # Check individual courses in group
                        print("    courses taken:")
                        for gc in child.get('reqs', []):
                            course_id = gc if isinstance(gc, str) else gc.get('req')
                            taken = "✓" if course_id in courses else "✗"
                            print(f"      {taken} {course_id}")

        print("\n  INTERPRETATION:")
        if aus.get('fulfilled'):
            print("    Fireroad counts leaf courses INDIVIDUALLY (ignores group boundary)")
        else:
            progress = aus.get('progress', 0)
            if progress == 1:
                print("    Fireroad counts satisfied CHILDREN (group not satisfied → doesn't count)")
            else:
                print("    Fireroad counts satisfied leaf courses from satisfied groups only")


def test_aus_with_full_group():
    """
    Test: AUS with both 6.C01 AND 6.C011 (no other courses)

    Question: Does the group count as:
      A) 2 subjects toward threshold
      B) 1 satisfied child
    """
    print("\n" + "="*80)
    print("TEST 2: AUS with complete group (6.C01 + 6.C011 only)")
    print("="*80)

    courses = ["6.C01", "6.C011"]
    result = query_fireroad(courses)
    aus = find_requirement(result, 'AUS')

    if aus:
        print("\nAUS Result:")
        print(f"  fulfilled: {aus.get('fulfilled')}")
        print(f"  progress: {aus.get('progress')}")
        print(f"  max: {aus.get('max')}")

        print("\n  INTERPRETATION:")
        if aus.get('fulfilled'):
            print("    The group counts as 2 subjects (both courses count)")
        else:
            print(f"    Progress = {aus.get('progress')}")
            if aus.get('progress') == 1:
                print("    The group counts as 1 child unit")
            elif aus.get('progress') == 2:
                print("    Both courses in the group count individually")


def test_aus_with_group_plus_one():
    """
    Test: AUS with 6.C01 + 6.C011 + 18.404

    Question: How many subjects does this count as?
      A) 3 (all leaf courses)
      B) 2 (group + one course)
    """
    print("\n" + "="*80)
    print("TEST 3: AUS with complete group + one more (6.C01 + 6.C011 + 18.404)")
    print("="*80)

    courses = ["6.C01", "6.C011", "18.404"]
    result = query_fireroad(courses)
    aus = find_requirement(result, 'AUS')

    if aus:
        print("\nAUS Result:")
        print(f"  fulfilled: {aus.get('fulfilled')}")
        print(f"  progress: {aus.get('progress')}")
        print(f"  max: {aus.get('max')}")

        print("\n  INTERPRETATION:")
        progress = aus.get('progress', 0)
        if progress == 3:
            print("    All 3 leaf courses count individually")
        elif progress == 2:
            print("    Group counts as single unit (or only satisfied children count)")


def test_aus_with_only_outside_course():
    """
    Test: AUS with only 18.404 (no group courses)

    Question: Is progress = 1?
    """
    print("\n" + "="*80)
    print("TEST 4: AUS with only one course outside group (18.404)")
    print("="*80)

    courses = ["18.404"]
    result = query_fireroad(courses)
    aus = find_requirement(result, 'AUS')

    if aus:
        print("\nAUS Result:")
        print(f"  fulfilled: {aus.get('fulfilled')}")
        print(f"  progress: {aus.get('progress')}")
        print(f"  max: {aus.get('max')}")


def test_aus_with_two_outside_courses():
    """
    Test: AUS with 18.404 + 6.1040 (two courses, not from the group)

    This should definitely be fulfilled since we have 2 subjects.
    """
    print("\n" + "="*80)
    print("TEST 5: AUS with two courses outside group (18.404 + 6.1040)")
    print("="*80)

    courses = ["18.404", "6.1040"]
    result = query_fireroad(courses)
    aus = find_requirement(result, 'AUS')

    if aus:
        print("\nAUS Result:")
        print(f"  fulfilled: {aus.get('fulfilled')}")
        print(f"  progress: {aus.get('progress')}")
        print(f"  max: {aus.get('max')}")

        if not aus.get('fulfilled'):
            print("\n  ⚠️  UNEXPECTED: Should be fulfilled with 2 independent courses!")


def test_connection_type_any_semantics():
    """
    Test what connection-type='any' means when combined with threshold.

    We'll test with just 6.C01 (only from the group, no other courses).

    If connection='any' means "at least one child must be satisfied":
      - The group is not satisfied (needs both 6.C01 and 6.C011)
      - No direct children are satisfied
      - Should NOT be fulfilled

    If connection='any' means something else:
      - We'll learn what!
    """
    print("\n" + "="*80)
    print("TEST 6: AUS with only 6.C01 (to test connection-type='any')")
    print("="*80)

    courses = ["6.C01"]
    result = query_fireroad(courses)
    aus = find_requirement(result, 'AUS')

    if aus:
        print("\nAUS Result:")
        print(f"  fulfilled: {aus.get('fulfilled')}")
        print(f"  progress: {aus.get('progress')}")
        print(f"  max: {aus.get('max')}")

        print("\n  INTERPRETATION:")
        if aus.get('fulfilled'):
            print("    connection='any' might not be enforced, or threshold overrides it")
        else:
            if aus.get('progress') == 0:
                print("    Partial group courses don't count at all")
            elif aus.get('progress') == 1:
                print("    Partial group course counts as 1, but not enough for threshold")


def run_all_tests():
    """Run all empirical tests."""
    print("\n" + "="*80)
    print("FIREROAD API SEMANTICS EMPIRICAL TESTING")
    print("="*80)

    try:
        test_aus_with_partial_group()
        test_aus_with_full_group()
        test_aus_with_group_plus_one()
        test_aus_with_only_outside_course()
        test_aus_with_two_outside_courses()
        test_connection_type_any_semantics()

        print("\n" + "="*80)
        print("SUMMARY OF FINDINGS")
        print("="*80)
        print("\nBased on the tests above, we can determine:")
        print("1. How threshold with criterion='subjects' counts courses")
        print("2. Whether group boundaries are respected")
        print("3. What connection-type='any' means with threshold")
        print("4. Whether constraints are bidirectional")

    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    run_all_tests()
