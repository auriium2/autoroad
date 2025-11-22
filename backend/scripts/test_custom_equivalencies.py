"""
Test script to verify custom equivalencies flow end-to-end
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl

from optimizer.objectives.equivalents import DiscourageEquivalentCourses


def test_custom_equivalencies():
    """Test that custom equivalencies are properly merged and applied"""

    # Create a minimal courses dataframe with 6.100A and 6.100L
    courses_df = pl.DataFrame({
        "subject_id": ["6.100A", "6.100L", "18.01"],
        "equivalent_subjects": [None, None, None],  # Fireroad has no equivalencies
        "offered_fall": [True, True, True],
        "offered_spring": [True, True, True],
        "offered_IAP": [False, False, False],
        "offered_summer": [False, False, False],
        "total_units": [12, 12, 12],
        "not_offered_year": [None, None, None],
    })

    # Create custom equivalencies
    custom_equivalencies = {
        "6.100A": ["6.100L"],
        "6.100L": ["6.100A"]
    }

    # Test DiscourageEquivalentCourses with custom equivalencies
    objective = DiscourageEquivalentCourses()
    preprocessed = objective.preprocess(courses_df, custom_equivalencies=custom_equivalencies)

    # Create index mapping
    course_id_to_idx = {courses_df[i, 'subject_id']: i for i in range(len(courses_df))}
    idx_6_100a = course_id_to_idx.get("6.100A")
    idx_6_100l = course_id_to_idx.get("6.100L")

    print("✓ Preprocessed equivalency groups:")
    for group_idx, group in enumerate(preprocessed["equiv_groups"]):
        course_names = [courses_df[idx, 'subject_id'] for idx in group]
        print(f"  Group {group_idx}: {course_names}")

    # Verify that 6.100A and 6.100L are in the same group
    found_custom_group = False
    for group in preprocessed["equiv_groups"]:
        if idx_6_100a in group and idx_6_100l in group:
            found_custom_group = True
            print("\n✓ Custom equivalency detected: 6.100A ≡ 6.100L")
            break

    if not found_custom_group:
        print("\n✗ FAILED: Custom equivalency not detected!")
        return False

    # Test default overrides from JSON
    preprocessed_with_defaults = objective.preprocess(courses_df, custom_equivalencies=None)

    found_default_group = False
    for group in preprocessed_with_defaults["equiv_groups"]:
        if idx_6_100a in group and idx_6_100l in group:
            found_default_group = True
            print("✓ Default JSON override detected: 6.100A ≡ 6.100L")
            break

    if not found_default_group:
        print("✗ FAILED: Default JSON override not loaded!")
        return False

    print("\n✓ All tests passed!")
    return True

if __name__ == "__main__":
    success = test_custom_equivalencies()
    sys.exit(0 if success else 1)
