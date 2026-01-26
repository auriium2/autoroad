"""
Tests for Hydrant semester resolution logic.

Uses property-based testing with Hypothesis to verify invariants hold
across all possible month/year combinations.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from shared.services.hydrant import resolve_semester

# ============ Property-Based Tests ============

@given(
    current_year=st.integers(min_value=2020, max_value=2040),
    current_month=st.integers(min_value=1, max_value=12),
    target_year=st.integers(min_value=2020, max_value=2040),
    target_term=st.sampled_from(["f", "s", "i"]),
)
@settings(max_examples=500)
def test_data_semester_always_same_term_type(
    current_year: int, current_month: int, target_year: int, target_term: str
):
    """The returned data_semester should always be the same term type as requested."""
    target_semester = f"{target_term}{target_year % 100}"
    fetch, data = resolve_semester(target_semester, current_year, current_month)

    assert data[0] == target_term, (
        f"Requested {target_term} but got {data[0]}. "
        f"target={target_semester}, year={current_year}, month={current_month}"
    )


@given(
    current_year=st.integers(min_value=2020, max_value=2040),
    current_month=st.integers(min_value=1, max_value=12),
    target_year=st.integers(min_value=2020, max_value=2040),
    target_term=st.sampled_from(["f", "s", "i"]),
)
@settings(max_examples=500)
def test_data_semester_never_in_future(
    current_year: int, current_month: int, target_year: int, target_term: str
):
    """The returned data_semester should never be from the future."""
    target_semester = f"{target_term}{target_year % 100}"
    fetch, data = resolve_semester(target_semester, current_year, current_month)

    if fetch == "latest":
        # Latest is always current semester, which is not future
        return

    data_year = int(data[1:]) + 2000
    data_term = data[0]

    # Determine if data semester is in the future
    if data_term == "f":
        # Fall X is in the future if we're before June of year X
        is_future = data_year > current_year or (data_year == current_year and current_month < 6)
    elif data_term == "s":
        # Spring X is in the future if we're before Jan of year X
        is_future = data_year > current_year
    else:  # IAP
        # IAP X is in the future if we're before Jan of year X
        is_future = data_year > current_year

    assert not is_future, (
        f"Data semester {data} is in the future relative to {current_month}/{current_year}. "
        f"target={target_semester}"
    )


@given(
    current_year=st.integers(min_value=2020, max_value=2040),
    current_month=st.integers(min_value=1, max_value=12),
    target_year=st.integers(min_value=2020, max_value=2040),
    target_term=st.sampled_from(["f", "s", "i"]),
)
@settings(max_examples=500)
def test_fetch_semester_is_valid(
    current_year: int, current_month: int, target_year: int, target_term: str
):
    """fetch_semester should be 'latest' or a valid semester code."""
    target_semester = f"{target_term}{target_year % 100}"
    fetch, data = resolve_semester(target_semester, current_year, current_month)

    if fetch == "latest":
        return

    assert len(fetch) == 3, f"Invalid fetch semester: {fetch}"
    assert fetch[0] in ("f", "s", "i"), f"Invalid term in fetch: {fetch}"
    assert fetch[1:].isdigit(), f"Invalid year in fetch: {fetch}"


@given(
    current_year=st.integers(min_value=2020, max_value=2040),
    current_month=st.integers(min_value=1, max_value=12),
)
@settings(max_examples=200)
def test_current_semester_uses_latest(current_year: int, current_month: int):
    """Requesting the current semester should always use 'latest'."""
    if current_month <= 5:
        current_sem = f"s{current_year % 100}"
    else:
        current_sem = f"f{current_year % 100}"

    fetch, data = resolve_semester(current_sem, current_year, current_month)

    assert fetch == "latest", f"Current semester {current_sem} should use 'latest', got {fetch}"
    assert data == current_sem, f"Data should be {current_sem}, got {data}"


# ============ Specific Scenario Tests ============

class TestSpringMonths:
    """Tests when current month is January-May (latest = spring)."""

    @pytest.mark.parametrize("month", [1, 2, 3, 4, 5])
    def test_request_current_spring(self, month: int):
        """Requesting current spring uses latest."""
        fetch, data = resolve_semester("s26", 2026, month)
        assert fetch == "latest"
        assert data == "s26"

    @pytest.mark.parametrize("month", [1, 2, 3, 4, 5])
    def test_request_future_spring(self, month: int):
        """Requesting future spring uses latest (best available)."""
        fetch, data = resolve_semester("s27", 2026, month)
        assert fetch == "latest"
        assert data == "s26"

    @pytest.mark.parametrize("month", [1, 2, 3, 4, 5])
    def test_request_past_spring(self, month: int):
        """Requesting past spring fetches it directly."""
        fetch, data = resolve_semester("s25", 2026, month)
        assert fetch == "s25"
        assert data == "s25"

    @pytest.mark.parametrize("month", [1, 2, 3, 4, 5])
    def test_request_current_fall(self, month: int):
        """Requesting fall when in spring falls back to previous fall."""
        # In spring 2026, requesting f26 (not yet happened) -> f25
        fetch, data = resolve_semester("f26", 2026, month)
        assert fetch == "f25"
        assert data == "f25"

    @pytest.mark.parametrize("month", [1, 2, 3, 4, 5])
    def test_request_future_fall(self, month: int):
        """Requesting future fall falls back to previous fall."""
        fetch, data = resolve_semester("f27", 2026, month)
        assert fetch == "f25"
        assert data == "f25"

    @pytest.mark.parametrize("month", [1, 2, 3, 4, 5])
    def test_request_past_fall(self, month: int):
        """Requesting past fall fetches it directly."""
        fetch, data = resolve_semester("f24", 2026, month)
        assert fetch == "f24"
        assert data == "f24"


class TestFallMonths:
    """Tests when current month is June-December (latest = fall)."""

    @pytest.mark.parametrize("month", [6, 7, 8, 9, 10, 11, 12])
    def test_request_current_fall(self, month: int):
        """Requesting current fall uses latest."""
        fetch, data = resolve_semester("f26", 2026, month)
        assert fetch == "latest"
        assert data == "f26"

    @pytest.mark.parametrize("month", [6, 7, 8, 9, 10, 11, 12])
    def test_request_future_fall(self, month: int):
        """Requesting future fall uses latest (best available)."""
        fetch, data = resolve_semester("f27", 2026, month)
        assert fetch == "latest"
        assert data == "f26"

    @pytest.mark.parametrize("month", [6, 7, 8, 9, 10, 11, 12])
    def test_request_past_fall(self, month: int):
        """Requesting past fall fetches it directly."""
        fetch, data = resolve_semester("f25", 2026, month)
        assert fetch == "f25"
        assert data == "f25"

    @pytest.mark.parametrize("month", [6, 7, 8, 9, 10, 11, 12])
    def test_request_future_spring(self, month: int):
        """Requesting future spring when in fall falls back to most recent spring."""
        # In fall 2026, requesting s27 (not yet happened) -> s26 (most recent spring)
        fetch, data = resolve_semester("s27", 2026, month)
        assert fetch == "s26"
        assert data == "s26"

    @pytest.mark.parametrize("month", [6, 7, 8, 9, 10, 11, 12])
    def test_request_past_spring(self, month: int):
        """Requesting past spring fetches it directly."""
        fetch, data = resolve_semester("s26", 2026, month)
        assert fetch == "s26"
        assert data == "s26"


class TestIAPHandling:
    """Tests for IAP semester handling."""

    def test_iap_in_january(self):
        """In January, IAP of current year should use archived."""
        # January 2026: latest=s26, requesting i26
        fetch, data = resolve_semester("i26", 2026, 1)
        assert data[0] == "i"  # Must be IAP

    def test_iap_in_february(self):
        """In February+, IAP of current year should use archived."""
        fetch, data = resolve_semester("i26", 2026, 2)
        assert data[0] == "i"

    def test_future_iap_in_fall(self):
        """Requesting future IAP when in fall."""
        # October 2026: latest=f26, requesting i27
        fetch, data = resolve_semester("i27", 2026, 10)
        assert data[0] == "i"


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_year_2000_encoding(self):
        """Year encoding works correctly."""
        fetch, data = resolve_semester("s25", 2026, 3)
        assert data == "s25"

    def test_year_boundary_december(self):
        """December of year X, latest is fall X."""
        fetch, data = resolve_semester("f26", 2026, 12)
        assert fetch == "latest"
        assert data == "f26"

    def test_year_boundary_january(self):
        """January of year X, latest is spring X."""
        fetch, data = resolve_semester("s26", 2026, 1)
        assert fetch == "latest"
        assert data == "s26"

    def test_very_old_semester(self):
        """Requesting a semester from years ago."""
        fetch, data = resolve_semester("f20", 2026, 6)
        assert fetch == "f20"
        assert data == "f20"

    def test_very_future_semester(self):
        """Requesting a semester far in the future."""
        fetch, data = resolve_semester("s35", 2026, 3)
        # Should fall back to current spring
        assert fetch == "latest"
        assert data == "s26"


class TestRealWorldScenarios:
    """Tests based on real usage patterns."""

    def test_class_of_2029_freshman_spring_in_january_2026(self):
        """
        Class of 2029, Freshman Spring = s26
        In January 2026, latest = s26
        Should use latest.
        """
        fetch, data = resolve_semester("s26", 2026, 1)
        assert fetch == "latest"
        assert data == "s26"

    def test_class_of_2029_sophomore_fall_in_january_2026(self):
        """
        Class of 2029, Sophomore Fall = f26
        In January 2026, latest = s26
        f26 hasn't happened yet, should fall back to f25.
        """
        fetch, data = resolve_semester("f26", 2026, 1)
        assert fetch == "f25"
        assert data == "f25"

    def test_class_of_2029_sophomore_spring_in_january_2026(self):
        """
        Class of 2029, Sophomore Spring = s27
        In January 2026, latest = s26
        s27 hasn't happened yet, should use latest (s26).
        """
        fetch, data = resolve_semester("s27", 2026, 1)
        assert fetch == "latest"
        assert data == "s26"

    def test_class_of_2028_senior_fall_in_october_2027(self):
        """
        Class of 2028, Senior Fall = f27
        In October 2027, latest = f27
        Should use latest.
        """
        fetch, data = resolve_semester("f27", 2027, 10)
        assert fetch == "latest"
        assert data == "f27"

    def test_viewing_past_schedule_in_fall(self):
        """
        Looking at a schedule from last spring while in fall.
        """
        # October 2026: latest = f26, looking at s26
        fetch, data = resolve_semester("s26", 2026, 10)
        assert fetch == "s26"
        assert data == "s26"
