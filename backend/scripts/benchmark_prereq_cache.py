import time
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import polars as pl
from api.services.cache import get_courses_data
from courses.prerequisites.parser import parse_fireroad


def benchmark_with_cache():
    """Measure performance using the cached function"""
    from api.services.cache import get_parsed_prerequisites
    
    # Get courses data
    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    
    print(f"Loaded {len(courses_df)} courses")
    print("\n" + "="*60)
    print("TEST 1: Cache MISS (first call)")
    print("="*60)
    
    # First call - cache miss
    start = time.perf_counter()
    prereq_trees = get_parsed_prerequisites(courses_df)
    elapsed_miss = time.perf_counter() - start
    
    print(f"Time: {elapsed_miss*1000:.2f}ms")
    print(f"Prerequisites parsed: {len(prereq_trees)}")
    
    print("\n" + "="*60)
    print("TEST 2: Cache HIT (second call)")
    print("="*60)
    
    # Second call - cache hit
    start = time.perf_counter()
    prereq_trees = get_parsed_prerequisites(courses_df)
    elapsed_hit = time.perf_counter() - start
    
    print(f"Time: {elapsed_hit*1000:.2f}ms")
    print(f"Prerequisites parsed: {len(prereq_trees)}")
    
    return elapsed_miss, elapsed_hit


def benchmark_without_cache():
    """Measure raw parsing performance without cache"""
    # Get courses data
    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    
    print("\n" + "="*60)
    print("TEST 3: No cache (raw parsing)")
    print("="*60)
    
    # Parse directly without cache
    start = time.perf_counter()
    prereq_trees = {}
    for course_idx in range(len(courses_df)):
        prereq_str = courses_df[course_idx, 'prerequisites']
        if prereq_str is not None and prereq_str:
            try:
                prereq_tree = parse_fireroad(prereq_str)
                prereq_trees[course_idx] = prereq_tree
            except Exception:
                pass
    elapsed = time.perf_counter() - start
    
    print(f"Time: {elapsed*1000:.2f}ms")
    print(f"Prerequisites parsed: {len(prereq_trees)}")
    
    return elapsed


if __name__ == '__main__':
    print("Benchmarking prerequisite parsing performance...")
    print("This will measure the actual impact of the cache.\n")
    
    # Test with cache
    elapsed_miss, elapsed_hit = benchmark_with_cache()
    
    # Test without cache (raw parsing)
    elapsed_no_cache = benchmark_without_cache()
    
    # Analysis
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Cache miss (first parse): {elapsed_miss*1000:>8.2f}ms")
    print(f"Cache hit (cached):       {elapsed_hit*1000:>8.2f}ms")
    print(f"No cache (raw parse):     {elapsed_no_cache*1000:>8.2f}ms")
    
    if elapsed_hit > 0:
        speedup = elapsed_miss / elapsed_hit
        print(f"\nCache speedup:            {speedup:>8.1f}x faster")
    
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)
    
    # Check if parsing is fast enough that cache doesn't matter
    if elapsed_miss < 0.010:  # Less than 10ms
        print("⚠️  Parsing is VERY FAST (<10ms)")
        print("    Cache may not be necessary - overhead is minimal")
    elif elapsed_miss < 0.050:  # Less than 50ms
        print("⚠️  Parsing is FAST (<50ms)")
        print("    Cache provides minor benefit but may not be critical")
    elif elapsed_miss < 0.100:  # Less than 100ms
        print("✓  Parsing is MODERATE (50-100ms)")
        print("   Cache provides noticeable speedup")
    else:  # Over 100ms
        print("✓  Parsing is SLOW (>100ms)")
        print("   Cache is definitely beneficial")
    
    # Check speedup ratio
    if elapsed_hit > 0:
        if speedup < 2:
            print(f"\n⚠️  Cache speedup is LOW ({speedup:.1f}x)")
            print("    May not justify the complexity")
        elif speedup < 10:
            print(f"\n✓  Cache speedup is MODERATE ({speedup:.1f}x)")
            print("   Worthwhile improvement")
        else:
            print(f"\n✓  Cache speedup is HIGH ({speedup:.1f}x)")
            print("   Excellent performance gain")
    
    # Final recommendation
    print("\n" + "="*60)
    print("RECOMMENDATION")
    print("="*60)
    
    if elapsed_miss < 0.010:
        print("🔴 REMOVE CACHE")
        print("   Parsing is so fast that cache overhead may not be worth it")
    elif elapsed_miss < 0.050 and (elapsed_hit <= 0 or elapsed_miss / elapsed_hit < 3):
        print("🟡 CONSIDER REMOVING CACHE")
        print("   Parsing is fast and cache provides minimal benefit")
    else:
        print("🟢 KEEP CACHE")
        print("   Cache provides meaningful performance improvement")
