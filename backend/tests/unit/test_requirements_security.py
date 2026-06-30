"""
Unit tests for requirements loading security.
"""

from shared.services.cache import _load_local_requirement


def test_load_valid_local_requirement():
    """Verify that valid local requirements can be loaded correctly."""
    result = _load_local_requirement("minor6")
    assert result is not None
    assert isinstance(result, dict)


def test_load_local_requirement_path_traversal():
    """Verify that path traversal in local requirement keys is blocked."""
    # Attempting to traverse out of the REQUIREMENTS_DIR
    result_outside = _load_local_requirement("../pyproject")
    assert result_outside is None

    result_passwd = _load_local_requirement("../../../../etc/passwd")
    assert result_passwd is None

    result_absolute = _load_local_requirement("/etc/passwd")
    assert result_absolute is None
