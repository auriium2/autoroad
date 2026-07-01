"""
Unit tests for objective utility functions.
"""

from shared.optimizer.objectives.utils import parse_time_to_minutes


def test_parse_time_to_minutes_am_pm():
    """Test that AM and PM times are correctly parsed and not treated as identical."""
    # "5.30 PM" should be 17 * 60 + 30 = 1050 minutes
    assert parse_time_to_minutes("5.30 PM", "0") == 1050

    # "5.30 AM" should be 5 * 60 + 30 = 330 minutes
    assert parse_time_to_minutes("5.30 AM", "0") == 330

    # "9" with is_evening="1" (PM) should be 9 + 12 = 21 * 60 = 1260 minutes
    assert parse_time_to_minutes("9", "1") == 1260

    # "9" with is_evening="0" (AM) should be 9 * 60 = 540 minutes
    assert parse_time_to_minutes("9", "0") == 540
