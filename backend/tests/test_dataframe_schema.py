"""
Regression tests for DataFrame schema inference.

This ensures that when creating DataFrames from API data (list of dicts),
all columns are properly detected even if they're sparse.
"""
import polars as pl


def test_sparse_columns_are_detected():
    """
    Regression test: Sparse columns should be detected when creating DataFrame.
    
    When creating a DataFrame from a list of dicts where some keys are missing
    from most dictionaries AND appear after the default inference window,
    polars needs infer_schema_length=None to detect all columns.
    This was the root cause of the communication_requirement bug.
    """
    # Simulate Fireroad API data where communication_requirement appears late
    # Polars default infer_schema_length is 100, so put the sparse column after that
    courses_data = [
        {'subject_id': f'COURSE.{i}', 'gir_attribute': None}
        for i in range(150)
    ]
    # Add communication_requirement only after row 100
    courses_data[120]['communication_requirement'] = 'CI-H'
    courses_data[140]['communication_requirement'] = 'CI-HW'

    # Without infer_schema_length=None, sparse columns appearing after row 100 are missed
    df_broken = pl.DataFrame(courses_data)

    # With infer_schema_length=None, all columns are detected
    df_fixed = pl.DataFrame(courses_data, infer_schema_length=None)

    # The fixed version should have the communication_requirement column
    assert 'communication_requirement' in df_fixed.columns, \
        "Sparse column 'communication_requirement' should be detected with infer_schema_length=None"
    assert 'communication_requirement' not in df_broken.columns, \
        "Without infer_schema_length=None, sparse columns appearing after row 100 are missed"


def test_filtering_sparse_columns():
    """
    Test that filtering works correctly on sparse columns.
    """
    courses_data = [
        {'subject_id': '6.100A'},
        {'subject_id': '21W.022', 'communication_requirement': 'CI-H'},
        {'subject_id': '21W.035', 'communication_requirement': 'CI-HW'},
        {'subject_id': '18.01'},
    ]

    df = pl.DataFrame(courses_data, infer_schema_length=None)

    # Filter for CI-H courses
    comm_reqs = df['communication_requirement'].to_list()
    ci_h_indices = [i for i, v in enumerate(comm_reqs) if v == 'CI-H']

    assert ci_h_indices == [1], "Should find CI-H at index 1"
    assert df[1, 'subject_id'] == '21W.022', "Should be the correct course"


def test_all_columns_present_in_api_style_data():
    """
    Test that creating a DataFrame the way the API does preserves all columns.
    """
    # Simulate real API data structure
    courses_data = [
        {
            'subject_id': '6.100A',
            'gir_attribute': None,
            'hass_attribute': None,
            'total_units': 12,
        },
        {
            'subject_id': '21W.022',
            'gir_attribute': None,
            'hass_attribute': 'HASS-H',
            'total_units': 12,
            'communication_requirement': 'CI-H',  # Only some courses have this
        },
        {
            'subject_id': '18.01',
            'gir_attribute': 'CAL1',
            'hass_attribute': None,
            'total_units': 12,
        },
    ]

    df = pl.DataFrame(courses_data, infer_schema_length=None)

    # All expected columns should be present
    expected_columns = {'subject_id', 'gir_attribute', 'hass_attribute',
                       'total_units', 'communication_requirement'}
    assert expected_columns.issubset(set(df.columns)), \
        f"Missing columns: {expected_columns - set(df.columns)}"
