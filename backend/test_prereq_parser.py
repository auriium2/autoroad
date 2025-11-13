"""
Fuzz test prerequisite parser using real Fireroad data

This script:
1. Fetches all course data from Fireroad
2. Extracts unique prerequisite strings
3. Tests our parser against all of them
4. Reports which ones fail to parse
5. Analyzes patterns in failures to improve the parser
"""

import requests
import json
from collections import Counter, defaultdict
import re
from prerequisites_fireroad import (
    fireroad_to_courseroad,
    prereq_to_string,
    is_valid_course_id,
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
        # Fireroad stores prerequisites in different fields
        if 'prerequisites' in course and course['prerequisites']:
            prereq_strings.add(course['prerequisites'])
        if 'prereqs' in course and course['prereqs']:
            prereq_strings.add(course['prereqs'])
    
    # Remove empty/null values
    prereq_strings = {p for p in prereq_strings if p and p.strip()}
    
    return sorted(prereq_strings)


def clean_prerequisite_string(prereq_str):
    """
    Clean prerequisite strings - but the Fireroad parser handles most of this internally
    """
    if not prereq_str:
        return ""
    
    # Just basic cleanup - the parser will filter out junk
    prereq_str = prereq_str.strip()
    
    return prereq_str


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


def is_valid_course_id(s):
    """Check if a string looks like a valid MIT course ID"""
    # MIT courses are like: 6.100A, 18.03, 14.01, etc.
    # Pattern: department number, dot, course number, optional letter
    return bool(re.match(r'^\d+\.\d+[A-Z]?$', s.strip()))


def validate_parsed_result(parsed, original):
    """
    Validate that the parsed result contains actual course IDs, not junk.
    Returns (is_valid, issues)
    """
    issues = []
    
    def extract_course_ids(arr):
        """Recursively extract all course IDs from a prerequisite array"""
        courses = []
        if not isinstance(arr, list) or len(arr) == 0:
            return courses
        
        for item in arr[1:]:  # Skip the count
            if isinstance(item, str):
                courses.append(item)
            elif isinstance(item, list):
                courses.extend(extract_course_ids(item))
            elif isinstance(item, dict) and 'id' in item:
                courses.append(item['id'])
        return courses
    
    course_ids = extract_course_ids(parsed)
    
    if not course_ids:
        issues.append("No course IDs found in parse result")
        return False, issues
    
    # Check if any course IDs are actually valid
    valid_count = sum(1 for cid in course_ids if is_valid_course_id(cid))
    invalid_courses = [cid for cid in course_ids if not is_valid_course_id(cid)]
    
    if valid_count == 0:
        issues.append(f"No valid course IDs found. Got: {course_ids}")
        return False, issues
    
    # If more than 50% are junk, consider it a bad parse
    if invalid_courses and len(invalid_courses) > len(course_ids) * 0.5:
        issues.append(f"Too many invalid course IDs: {invalid_courses}")
        return False, issues
    
    return True, []


def test_parser(prereq_strings):
    """Test the parser against all prerequisite strings"""
    results = {
        'success': [],
        'failure': [],
        'empty_after_clean': [],
        'junk_parse': [],  # Parsed but contains junk
    }
    
    failure_patterns = Counter()
    category_stats = defaultdict(lambda: {'total': 0, 'success': 0, 'failure': 0, 'junk': 0})
    
    for prereq_str in prereq_strings:
        cleaned = clean_prerequisite_string(prereq_str)
        
        if not cleaned:
            results['empty_after_clean'].append(prereq_str)
            continue
        
        category = categorize_prerequisite(cleaned)
        category_stats[category]['total'] += 1
        
        try:
            # Try to parse with Fireroad parser
            parsed = fireroad_to_courseroad(cleaned)
            
            # Validate the parse result
            is_valid, issues = validate_parsed_result(parsed, prereq_str)
            
            if not is_valid:
                # Parsed successfully but result is junk
                results['junk_parse'].append({
                    'original': prereq_str,
                    'cleaned': cleaned,
                    'parsed': parsed,
                    'issues': issues,
                    'category': category,
                })
                category_stats[category]['junk'] += 1
                failure_patterns['junk_parse'] += 1
                continue
            
            # Try to convert back to string (validates structure)
            readable = prereq_to_string(parsed)
            
            results['success'].append({
                'original': prereq_str,
                'cleaned': cleaned,
                'parsed': parsed,
                'readable': readable,
                'category': category,
            })
            category_stats[category]['success'] += 1
            
        except Exception as e:
            results['failure'].append({
                'original': prereq_str,
                'cleaned': cleaned,
                'error': str(e),
                'category': category,
            })
            category_stats[category]['failure'] += 1
            
            # Track failure patterns
            if 'permission' in cleaned.lower():
                failure_patterns['contains_permission'] += 1
            elif 'coreq' in cleaned.lower():
                failure_patterns['contains_coreq'] += 1
            elif re.search(r'\d+\.\d+[A-Z]', cleaned):
                failure_patterns['complex_course_id'] += 1
            elif '/' in cleaned:
                failure_patterns['slash_delimiter'] += 1
            else:
                failure_patterns['other'] += 1
    
    return results, category_stats, failure_patterns


def print_report(results, category_stats, failure_patterns, prereq_strings):
    """Print a comprehensive test report"""
    total = len(prereq_strings)
    success_count = len(results['success'])
    failure_count = len(results['failure'])
    empty_count = len(results['empty_after_clean'])
    junk_count = len(results['junk_parse'])
    
    print("\n" + "="*80)
    print("PREREQUISITE PARSER FUZZ TEST REPORT")
    print("="*80)
    
    print(f"\nTotal prerequisite strings: {total}")
    print(f"  ✓ Successfully parsed: {success_count} ({success_count/total*100:.1f}%)")
    print(f"  ⚠ Parsed but junk result: {junk_count} ({junk_count/total*100:.1f}%)")
    print(f"  ✗ Failed to parse: {failure_count} ({failure_count/total*100:.1f}%)")
    print(f"  ∅ Empty after cleaning: {empty_count} ({empty_count/total*100:.1f}%)")
    
    print("\n" + "-"*80)
    print("PERFORMANCE BY CATEGORY")
    print("-"*80)
    
    for category, stats in sorted(category_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        total_cat = stats['total']
        success_cat = stats['success']
        failure_cat = stats['failure']
        junk_cat = stats['junk']
        success_rate = (success_cat / total_cat * 100) if total_cat > 0 else 0
        
        print(f"\n{category}:")
        print(f"  Total: {total_cat}")
        print(f"  Success: {success_cat} ({success_rate:.1f}%)")
        print(f"  Junk: {junk_cat}")
        print(f"  Failure: {failure_cat}")
    
    if failure_patterns:
        print("\n" + "-"*80)
        print("FAILURE PATTERNS")
        print("-"*80)
        for pattern, count in failure_patterns.most_common(10):
            print(f"  {pattern}: {count}")
    
    if results['junk_parse']:
        print("\n" + "-"*80)
        print("SAMPLE JUNK PARSES (first 20)")
        print("-"*80)
        for i, junk in enumerate(results['junk_parse'][:20], 1):
            print(f"\n{i}. Original: {junk['original']}")
            print(f"   Cleaned:  {junk['cleaned']}")
            print(f"   Category: {junk['category']}")
            print(f"   Issues:   {'; '.join(junk['issues'])}")
    
    if results['failure']:
        print("\n" + "-"*80)
        print("SAMPLE FAILURES (first 20)")
        print("-"*80)
        for i, failure in enumerate(results['failure'][:20], 1):
            print(f"\n{i}. Original: {failure['original']}")
            print(f"   Cleaned:  {failure['cleaned']}")
            print(f"   Category: {failure['category']}")
            print(f"   Error:    {failure['error']}")
    
    if results['success']:
        print("\n" + "-"*80)
        print("SAMPLE SUCCESSES (first 10)")
        print("-"*80)
        for i, success in enumerate(results['success'][:10], 1):
            print(f"\n{i}. Original: {success['original']}")
            print(f"   Parsed:   {success['readable']}")


def save_results(results, filename='prereq_test_results.json'):
    """Save detailed results to a JSON file"""
    # Convert to serializable format
    output = {
        'success_count': len(results['success']),
        'failure_count': len(results['failure']),
        'empty_count': len(results['empty_after_clean']),
        'junk_count': len(results['junk_parse']),
        'failures': results['failure'],
        'junk_parses': results['junk_parse'],
        'successes': [
            {
                'original': s['original'],
                'cleaned': s['cleaned'],
                'readable': s['readable'],
                'category': s['category'],
            }
            for s in results['success']
        ],
    }
    
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nDetailed results saved to {filename}")


def main():
    print("Starting Fireroad Prerequisite Parser Fuzz Test\n")
    
    # Fetch data
    courses = fetch_fireroad_courses()
    print(f"Fetched {len(courses)} courses")
    
    # Extract prerequisites
    prereq_strings = extract_prerequisite_strings(courses)
    print(f"Found {len(prereq_strings)} unique prerequisite strings\n")
    
    # Test parser
    print("Testing parser...")
    results, category_stats, failure_patterns = test_parser(prereq_strings)
    
    # Print report
    print_report(results, category_stats, failure_patterns, prereq_strings)
    
    # Save results
    save_results(results)
    
    print("\n" + "="*80)
    print("Test complete!")
    print("="*80)


if __name__ == '__main__':
    main()
