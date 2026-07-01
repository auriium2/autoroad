"""
Unit tests for schedule conflict constraints and Hydrant data processing.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from shared.optimizer.constraints.conflicts import fetch_hydrant_schedule_data


def test_fetch_hydrant_schedule_data_unpacking():
    """Test that fetch_hydrant_schedule_data correctly calls and unpacks get_hydrant_semester_data."""
    mock_data = {
        "classes": {
            "6.100A": {
                "lectureSections": [
                    [[[0, 2]], "room1"]
                ]
            }
        }
    }

    # Patch get_hydrant_semester_data on the module where it's defined and cached
    with patch("shared.services.cache.get_hydrant_semester_data", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_data

        required_result, options_result = asyncio.run(
            fetch_hydrant_schedule_data(["6.100A"], "f25")
        )

        # Verify that get_hydrant_semester_data was called once
        mock_get.assert_called_once_with("f25")

        # Verify we got non-empty results (meaning no ValueError unpacking exception occurred)
        assert "6.100A" in required_result
        assert "6.100A" in options_result
        assert len(required_result["6.100A"]) == 1
