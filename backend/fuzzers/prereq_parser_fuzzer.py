"""
Fuzz test prerequisite parser using real Fireroad data

This script:
1. Fetches all course data from Fireroad
2. Extracts unique prerequisite strings
3. Tests our parser against all of them
4. Reports which ones fail to parse
5. Analyzes patterns in failures to improve the parser
"""

import json
import re
from collections import Counter, defaultdict

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Please run 'uv pip install -e .' in the backend directory to install dependencies.")
    exit(1)

from courses import (
    PrereqCourse,
    PrereqGroup,
    PrereqNode,
    is_valid_course_id,
    parse_fireroad,
    prereq_to_string,
)


def fetch_fireroad_courses():
    """Fetch all course data from Fireroad"""
    print("Fetching course data from Fireroad...")
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    return response.json()


def extract_prerequisite_strings(courses):
    """Extract all unique prerequisite strings from course data"""
    prereq_strings = set()

    for course in courses:
        if 'prerequisites' in course and course['prerequisites']:
            prereq_strings.add(course['prerequisites'])
        if 'prereqs' in course and course['prereqs']:
            prereq_strings.add(course['prereqs'])

    prereq_strings = {p for p in prereq_strings if p and p.strip()}

    return sorted(prereq_strings)


def clean_prerequisite_string(prereq_str):
    """Clean prerequisite strings"""
    if not prereq_str:
        return ""
    return prereq_str.strip()


def categorize_prerequisite(prereq_str):
    """Categorize a prerequisite string by its structure"""
    categories = []
    if '/' in prereq_str or ' or ' in prereq_str.lower():
        categories.append('OR')
    if ',' in prereq_str or ' and ' in prereq_str.lower():
        categories.append('AND')
    if '(' in prereq_str:
        categories.append('NESTED')
    if re.search(r'\d+\s+of', prereq_str, re.IGNORECASE):
        categories.append('THRESHOLD')
    if 'coreq' in prereq_str.lower():
        categories.append('COREQUISITE')
    if not categories:
        categories.append('SIMPLE')
    return ','.join(categories)


def validate_parsed_result(parsed: PrereqNode):
    """
    Validates the parsed PrereqNode to ensure it's logical and contains valid courses.
    Returns a tuple of (is_valid: bool, issues: list[str]).
    """
    issues = []

    def get_all_courses(node: PrereqNode) -> list[str]:
        if isinstance(node, PrereqCourse):
            return [node.course_id]
        if isinstance(node, PrereqGroup):
            return [course for item in node.items for course in get_all_courses(item)]
        return []

    all_courses = get_all_courses(parsed)

    # Case 1: No courses found in a non-empty structure
    if not all_courses and (isinstance(parsed, PrereqCourse) or (isinstance(parsed, PrereqGroup) and parsed.items)):
        issues.append("Parse result is a non-empty structure but contains no course IDs.")

    # Case 2: Check for invalid course IDs
    invalid_courses = [course for course in all_courses if not is_valid_course_id(course)]
    if invalid_courses:
        issues.append(f"Result contains invalid course IDs: {', '.join(invalid_courses)}")

    # Case 3: Check for a high ratio of invalid to valid courses
    if all_courses:
        valid_courses = [c for c in all_courses if c not in invalid_courses]
        if not valid_courses:
            issues.append("No valid course IDs found in the parse result.")
        elif len(invalid_courses) > len(valid_courses):
            issues.append("More invalid than valid course IDs found.")

    return not issues, issues


def test_parser(prereq_strings):
    """
    Tests the prerequisite parser against a list of strings and returns structured results.
    """
    results = defaultdict(list)
    category_stats = defaultdict(lambda: Counter())
    failure_patterns = Counter()

    for prereq_str in prereq_strings:
        cleaned = clean_prerequisite_string(prereq_str)
        if not cleaned:
            results["empty_after_clean"].append(prereq_str)
            continue

        category = categorize_prerequisite(cleaned)
        category_stats[category]["total"] += 1

        try:
            parsed = parse_fireroad(cleaned)
            is_valid, issues = validate_parsed_result(parsed)

            if not is_valid:
                results["junk_parse"].append({
                    "original": prereq_str,
                    "cleaned": cleaned,
                    "parsed": str(parsed),
                    "issues": issues,
                    "category": category,
                })
                category_stats[category]["junk"] += 1
                failure_patterns["junk_parse"] += 1
                # Don't double-count in failures - junk is tracked separately
            else:
                results["success"].append({
                    "original": prereq_str,
                    "cleaned": cleaned,
                    "readable": prereq_to_string(parsed),
                    "category": category,
                })
                category_stats[category]["success"] += 1

        except Exception as e:
            results["failure"].append({
                "original": prereq_str,
                "cleaned": cleaned,
                "error": str(e),
                "category": category,
            })
            category_stats[category]["failure"] += 1
            # Basic failure pattern analysis
            if "permission" in cleaned.lower():
                failure_patterns["contains_permission"] += 1
            elif "coreq" in cleaned.lower():
                failure_patterns["contains_coreq"] += 1
            else:
                failure_patterns["other_error"] += 1

    return results, category_stats, failure_patterns


def print_report(results, category_stats, failure_patterns, prereq_strings):
    """Prints a comprehensive and readable report of the fuzz test results."""
    total = len(prereq_strings)
    success_count = len(results["success"])
    failure_count = len(results["failure"])
    junk_count = len(results["junk_parse"])

    # --- HEADER ---
    print("\n" + "=" * 80)
    print("PREREQUISITE PARSER FUZZ TEST REPORT")
    print("=" * 80)

    # --- SUMMARY ---
    print(f"\nTotal unique prerequisite strings: {total}")
    print(f"  - ✅ Successfully parsed: {success_count} ({success_count/total*100:.1f}%)")
    print(f"  - ⚠️ Parsed with junk: {junk_count} ({junk_count/total*100:.1f}%)")
    print(f"  - ❌ Failed to parse: {failure_count} ({failure_count/total*100:.1f}%)")

    # --- CATEGORY BREAKDOWN ---
    print("\n" + "-" * 80)
    print("PERFORMANCE BY CATEGORY")
    print("-" * 80)
    # Sort categories by total count, descending
    sorted_categories = sorted(category_stats.items(), key=lambda item: item[1]['total'], reverse=True)
    for category, stats in sorted_categories:
        cat_total = stats['total']
        cat_success = stats['success']
        success_rate = cat_success / cat_total * 100 if cat_total > 0 else 0
        print(f"\nCategory: {category} (Total: {cat_total})")
        print(f"  - Success: {cat_success} ({success_rate:.1f}%)")
        print(f"  - Junk: {stats['junk']}")
        print(f"  - Failure: {stats['failure']}")

    # --- FAILURE ANALYSIS ---
    if failure_patterns:
        print("\n" + "-" * 80)
        print("COMMON FAILURE PATTERNS")
        print("-" * 80)
        for pattern, count in failure_patterns.most_common():
            print(f"  - {pattern}: {count} occurrences")

    # --- SAMPLE JUNK ---
    if results["junk_parse"]:
        print("\n" + "-" * 80)
        print("SAMPLES OF JUNK PARSES (up to 10)")
        print("-" * 80)
        for i, junk in enumerate(results["junk_parse"][:10], 1):
            print(f"\n{i}. Original: '{junk['original']}'")
            print(f"   - Category: {junk['category']}")
            print(f"   - Issues: {', '.join(junk['issues'])}")

    # --- SAMPLE FAILURES ---
    if results["failure"]:
        print("\n" + "-" * 80)
        print("SAMPLES OF PARSE FAILURES (up to 10)")
        print("-" * 80)
        for i, failure in enumerate(results["failure"][:10], 1):
            print(f"\n{i}. Original: '{failure['original']}'")
            print(f"   - Category: {failure['category']}")
            print(f"   - Error: {failure['error']}")


def save_results(results, filename="prereq_test_results.json"):
    """Saves the detailed test results to a JSON file."""
    # Convert sets to lists for JSON serialization
    for key in results:
        if isinstance(results[key], list):
            for item in results[key]:
                if isinstance(item, dict):
                    for sub_key, sub_value in item.items():
                        if isinstance(sub_value, set):
                            item[sub_key] = list(sub_value)

    with open(filename, "w") as f:
        json.dump(
            {
                "success_count": len(results["success"]),
                "failure_count": len(results["failure"]),
                "junk_count": len(results["junk_parse"]),
                "failures": results["failure"],
                "junk_parses": results["junk_parse"],
            },
            f,
            indent=2,
        )
    print(f"\nDetailed results saved to {filename}")


def main():
    """Main function to run the fuzz test."""
    print("Starting Fireroad Prerequisite Parser Fuzz Test\n")

    try:
        courses = fetch_fireroad_courses()
        print(f"Fetched {len(courses)} courses from Fireroad.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching course data: {e}")
        return

    prereq_strings = extract_prerequisite_strings(courses)
    print(f"Found {len(prereq_strings)} unique prerequisite strings to test.\n")

    print("Running parser against all strings...")
    results, category_stats, failure_patterns = test_parser(prereq_strings)

    print_report(results, category_stats, failure_patterns, prereq_strings)
    save_results(results)

    print("\n" + "="*80)
    print("Fuzz test complete!")
    print("="*80)


if __name__ == '__main__':
    main()
