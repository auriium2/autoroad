"""
Fuzz test requirements parser using real Fireroad data

This script:
1. Fetches all requirement data from Fireroad
2. Tests our parser against all of them
3. Reports which ones fail to parse
4. Analyzes requirement structures and patterns
"""

import json
from collections import Counter, defaultdict
from typing import Any
import requests

from courses import (
    RequirementParseError,
    parse_requirement,
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementPlainString,
)


def fetch_fireroad_requirements() -> dict[str, Any]:
    """Fetch all requirements from Fireroad"""
    print("Fetching requirements list from Fireroad...")
    response = requests.get('https://fireroad.mit.edu/requirements/list_reqs')
    response.raise_for_status()
    req_list = response.json()

    print(f"Found {len(req_list)} requirement keys. Fetching details...")

    requirements = {}
    for key in req_list.keys():
        try:
            resp = requests.get(f'https://fireroad.mit.edu/requirements/get_json/{key}')
            resp.raise_for_status()
            requirements[key] = resp.json()
        except Exception as e:
            print(f"Warning: Failed to fetch requirement '{key}': {e}")

    return requirements


def extract_all_requirement_items(requirements: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """
    Extract all individual requirement items from the requirements data.

    Returns a list of (path, requirement_item) tuples where path identifies the requirement.
    """
    items: list[tuple[str, dict[str, Any]]] = []

    def extract_from_item(item: Any, path: str) -> None:
        """Recursively extract requirement items"""
        if not isinstance(item, dict):
            return

        items.append((path, item))

        # If this has sub-requirements, recurse
        if 'reqs' in item and isinstance(item['reqs'], list):
            for i, sub_req in enumerate(item['reqs']):
                sub_path = f"{path}[{i}]"
                extract_from_item(sub_req, sub_path)

    # Process each requirement
    for key, req_data in requirements.items():
        if 'reqs' in req_data and isinstance(req_data['reqs'], list):
            for i, req_item in enumerate(req_data['reqs']):
                path = f"{key}.reqs[{i}]"
                extract_from_item(req_item, path)

    return items


def categorize_requirement(req_item: dict[str, Any]) -> str:
    """Categorize a requirement by its structure"""
    categories = []

    if 'req' in req_item and 'reqs' not in req_item:
        # Check if it's a plain-string (boolean flag)
        if req_item.get('plain-string', False):
            categories.append('PLAIN_STRING')
        else:
            categories.append('LEAF')
            course_id = req_item['req']
            if course_id.startswith('GIR:'):
                categories.append('GIR')
            elif course_id.startswith('HASS'):
                categories.append('HASS')
            elif course_id.startswith('CI-'):
                categories.append('CI')
    elif 'reqs' in req_item:
        categories.append('GROUP')
        if 'connection-type' in req_item:
            categories.append(f"CONN_{req_item['connection-type'].upper()}")
        if 'threshold' in req_item:
            categories.append('THRESHOLD')
        if 'distinct-threshold' in req_item:
            categories.append('DISTINCT_THRESHOLD')

    return ','.join(categories) if categories else 'UNKNOWN'


def analyze_requirement_structure(req: RequirementNode) -> dict[str, int]:
    """Analyze the structure of a parsed requirement tree"""
    stats = {
        'total_nodes': 0,
        'course_nodes': 0,
        'plain_string_nodes': 0,
        'group_nodes': 0,
        'max_depth': 0,
    }

    def traverse(node: RequirementNode, depth: int = 0) -> None:
        stats['total_nodes'] += 1
        stats['max_depth'] = max(stats['max_depth'], depth)

        if isinstance(node, RequirementCourse):
            stats['course_nodes'] += 1
        elif isinstance(node, RequirementPlainString):
            stats['plain_string_nodes'] += 1
        elif isinstance(node, RequirementGroup):
            stats['group_nodes'] += 1
            for item in node.items:
                traverse(item, depth + 1)

    traverse(req)
    return stats


def test_parser(requirement_items: list[tuple[str, dict[str, Any]]]) -> tuple[dict[str, list[Any]], dict[str, Counter[str]], Counter[str]]:
    """
    Tests the requirements parser against all requirement items.

    Returns:
        - results: Dict of success/failure lists
        - category_stats: Stats by category
        - structure_stats: Statistics about parsed structures
    """
    results: dict[str, list[Any]] = defaultdict(list)
    category_stats: dict[str, Counter[str]] = defaultdict(Counter)
    structure_stats: Counter[str] = Counter()

    for path, req_item in requirement_items:
        category = categorize_requirement(req_item)
        category_stats[category]["total"] += 1

        try:
            parsed = parse_requirement(req_item)

            # Analyze structure
            stats = analyze_requirement_structure(parsed)
            structure_stats[f"depth_{stats['max_depth']}"] += 1

            results["success"].append({
                "path": path,
                "category": category,
                "original": req_item,
                "structure_stats": stats,
            })
            category_stats[category]["success"] += 1

        except RequirementParseError as e:
            results["failure"].append({
                "path": path,
                "category": category,
                "error": str(e),
                "original": req_item,
            })
            category_stats[category]["failure"] += 1
        except Exception as e:
            results["failure"].append({
                "path": path,
                "category": category,
                "error": f"Unexpected error: {type(e).__name__}: {e}",
                "original": req_item,
            })
            category_stats[category]["failure"] += 1

    return dict(results), dict(category_stats), structure_stats


def print_report(results: dict[str, list[Any]], category_stats: dict[str, Counter[str]], structure_stats: Counter[str], total_items: int) -> None:
    """Prints a comprehensive report of the fuzz test results."""
    success_count = len(results.get("success", []))
    failure_count = len(results.get("failure", []))

    # --- HEADER ---
    print("\n" + "=" * 80)
    print("REQUIREMENTS PARSER FUZZ TEST REPORT")
    print("=" * 80)

    # --- SUMMARY ---
    print(f"\nTotal requirement items tested: {total_items}")
    print(f"  - ✅ Successfully parsed: {success_count} ({success_count/total_items*100:.1f}%)")
    print(f"  - ❌ Failed to parse: {failure_count} ({failure_count/total_items*100:.1f}%)")

    # --- STRUCTURE STATS ---
    if structure_stats:
        print("\n" + "-" * 80)
        print("TREE DEPTH DISTRIBUTION")
        print("-" * 80)
        for depth_key in sorted(structure_stats.keys()):
            count = structure_stats[depth_key]
            print(f"  {depth_key}: {count} requirements")

    # --- CATEGORY BREAKDOWN ---
    print("\n" + "-" * 80)
    print("PERFORMANCE BY CATEGORY")
    print("-" * 80)
    sorted_categories = sorted(category_stats.items(), key=lambda item: item[1]['total'], reverse=True)
    for category, stats in sorted_categories:
        cat_total = stats['total']
        cat_success = stats['success']
        cat_failure = stats['failure']
        success_rate = cat_success / cat_total * 100 if cat_total > 0 else 0
        print(f"\nCategory: {category} (Total: {cat_total})")
        print(f"  - Success: {cat_success} ({success_rate:.1f}%)")
        print(f"  - Failure: {cat_failure}")

    # --- SAMPLE FAILURES ---
    failures = results.get("failure", [])
    if failures:
        print("\n" + "-" * 80)
        print("SAMPLE PARSE FAILURES (up to 10)")
        print("-" * 80)
        for i, failure in enumerate(failures[:10], 1):
            print(f"\n{i}. Path: {failure['path']}")
            print(f"   Category: {failure['category']}")
            print(f"   Error: {failure['error']}")
            print(f"   Original: {json.dumps(failure['original'], indent=2)[:200]}...")


def save_results(results: dict[str, list[Any]], filename: str = "requirements_test_results.json") -> None:
    """Saves the detailed test results to a JSON file."""
    # Remove 'original' from results to reduce file size
    clean_results = {
        "success_count": len(results.get("success", [])),
        "failure_count": len(results.get("failure", [])),
        "failures": [
            {k: v for k, v in f.items() if k != 'original'}
            for f in results.get("failure", [])
        ],
    }

    with open(filename, "w") as f:
        json.dump(clean_results, f, indent=2)
    print(f"\nDetailed results saved to {filename}")


def main() -> None:
    """Main function to run the fuzz test."""
    print("Starting Fireroad Requirements Parser Fuzz Test\n")

    try:
        requirements = fetch_fireroad_requirements()
        print(f"Successfully fetched {len(requirements)} requirements from Fireroad.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching requirements data: {e}")
        return

    requirement_items = extract_all_requirement_items(requirements)
    print(f"Extracted {len(requirement_items)} individual requirement items to test.\n")

    print("Running parser against all items...")
    results, category_stats, structure_stats = test_parser(requirement_items)

    print_report(results, category_stats, structure_stats, len(requirement_items))
    save_results(results)

    print("\n" + "=" * 80)
    print("Fuzz test complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
