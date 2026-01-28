"""Tests for requirement progress calculation."""


from shared.courses.requirements.progress import compute_progress
from shared.courses.requirements.types import (
    CI,
    GIR,
    HASS,
    AllGroup,
    AnyGroup,
    CIThreshold,
    Course,
    GIRThreshold,
    HASSThreshold,
    SubjectThresholdGroup,
    UnitThresholdGroup,
)


def make_course_data(
    subject_id: str,
    gir_attribute: str | None = None,
    hass_attribute: str | None = None,
    communication_requirement: str | None = None,
    total_units: int = 12,
) -> dict:
    return {
        "subject_id": subject_id,
        "gir_attribute": gir_attribute,
        "hass_attribute": hass_attribute,
        "communication_requirement": communication_requirement,
        "total_units": total_units,
    }


class TestHASSThresholdProgress:
    """Tests for HASSThreshold progress calculation."""

    def test_hass_threshold_empty(self):
        node = HASSThreshold(cutoff=3, category=None)
        result = compute_progress(node, set(), {})
        assert result.fulfilled is False
        assert result.progress == 0
        assert result.max == 3

    def test_hass_threshold_partial(self):
        node = HASSThreshold(cutoff=3, category=None)
        id2course = {
            "21L.001": make_course_data("21L.001", hass_attribute="HASS-H"),
            "21M.011": make_course_data("21M.011", hass_attribute="HASS-A"),
        }
        result = compute_progress(node, {"21L.001", "21M.011"}, id2course)
        assert result.fulfilled is False
        assert result.progress == 2
        assert result.max == 3
        assert set(result.sat_courses) == {"21L.001", "21M.011"}

    def test_hass_threshold_fulfilled(self):
        node = HASSThreshold(cutoff=2, category=None)
        id2course = {
            "21L.001": make_course_data("21L.001", hass_attribute="HASS-H"),
            "21M.011": make_course_data("21M.011", hass_attribute="HASS-A"),
            "21A.100": make_course_data("21A.100", hass_attribute="HASS-S"),
        }
        result = compute_progress(node, {"21L.001", "21M.011", "21A.100"}, id2course)
        assert result.fulfilled is True
        assert result.progress == 2
        assert result.max == 2

    def test_hass_threshold_specific_category(self):
        node = HASSThreshold(cutoff=2, category="HASS-A")
        id2course = {
            "21L.001": make_course_data("21L.001", hass_attribute="HASS-H"),
            "21M.011": make_course_data("21M.011", hass_attribute="HASS-A"),
            "21M.030": make_course_data("21M.030", hass_attribute="HASS-A"),
        }
        result = compute_progress(node, {"21L.001", "21M.011", "21M.030"}, id2course)
        assert result.fulfilled is True
        assert result.progress == 2
        # Only HASS-A courses count
        assert set(result.sat_courses) == {"21M.011", "21M.030"}


class TestCIThresholdProgress:
    """Tests for CIThreshold progress calculation."""

    def test_ci_threshold_empty(self):
        node = CIThreshold(cutoff=2, ci_type="CI-H")
        result = compute_progress(node, set(), {})
        assert result.fulfilled is False
        assert result.progress == 0
        assert result.max == 2

    def test_ci_threshold_partial(self):
        node = CIThreshold(cutoff=2, ci_type="CI-H")
        id2course = {
            "6.100A": make_course_data("6.100A", communication_requirement="CI-H"),
        }
        result = compute_progress(node, {"6.100A"}, id2course)
        assert result.fulfilled is False
        assert result.progress == 1
        assert result.max == 2

    def test_ci_threshold_fulfilled(self):
        node = CIThreshold(cutoff=2, ci_type="CI-H")
        id2course = {
            "6.100A": make_course_data("6.100A", communication_requirement="CI-H"),
            "6.101": make_course_data("6.101", communication_requirement="CI-H"),
            "6.102": make_course_data("6.102", communication_requirement="CI-HW"),
        }
        result = compute_progress(node, {"6.100A", "6.101", "6.102"}, id2course)
        assert result.fulfilled is True
        assert result.progress == 2
        # Only CI-H courses count
        assert set(result.sat_courses) == {"6.100A", "6.101"}

    def test_ci_threshold_cihw(self):
        node = CIThreshold(cutoff=1, ci_type="CI-HW")
        id2course = {
            "6.100A": make_course_data("6.100A", communication_requirement="CI-H"),
            "6.102": make_course_data("6.102", communication_requirement="CI-HW"),
        }
        result = compute_progress(node, {"6.100A", "6.102"}, id2course)
        assert result.fulfilled is True
        assert result.progress == 1
        assert result.sat_courses == ["6.102"]


class TestGIRThresholdProgress:
    """Tests for GIRThreshold progress calculation."""

    def test_gir_threshold_empty(self):
        node = GIRThreshold(cutoff=2, gir_code="REST")
        result = compute_progress(node, set(), {})
        assert result.fulfilled is False
        assert result.progress == 0
        assert result.max == 2

    def test_gir_threshold_partial(self):
        node = GIRThreshold(cutoff=2, gir_code="REST")
        id2course = {
            "8.01": make_course_data("8.01", gir_attribute="REST"),
        }
        result = compute_progress(node, {"8.01"}, id2course)
        assert result.fulfilled is False
        assert result.progress == 1
        assert result.max == 2

    def test_gir_threshold_fulfilled(self):
        node = GIRThreshold(cutoff=2, gir_code="REST")
        id2course = {
            "8.01": make_course_data("8.01", gir_attribute="REST"),
            "8.02": make_course_data("8.02", gir_attribute="REST"),
            "18.01": make_course_data("18.01", gir_attribute="CAL1"),
        }
        result = compute_progress(node, {"8.01", "8.02", "18.01"}, id2course)
        assert result.fulfilled is True
        assert result.progress == 2
        # Only REST courses count
        assert set(result.sat_courses) == {"8.01", "8.02"}


class TestThresholdNodesInGroups:
    """Tests that threshold nodes work correctly when nested in groups."""

    def test_hass_threshold_in_allgroup(self):
        """HASSThreshold should work when nested in an AllGroup."""
        hass_node = HASSThreshold(cutoff=2, category=None)
        root = AllGroup(children=(hass_node,))

        id2course = {
            "21L.001": make_course_data("21L.001", hass_attribute="HASS-H"),
            "21M.011": make_course_data("21M.011", hass_attribute="HASS-A"),
        }
        result = compute_progress(root, {"21L.001", "21M.011"}, id2course)
        assert result.fulfilled is True
        assert len(result.children) == 1
        assert result.children[0].progress == 2

    def test_ci_threshold_in_anygroup(self):
        """CIThreshold should work when nested in an AnyGroup."""
        ci_node = CIThreshold(cutoff=1, ci_type="CI-H")
        other_course = Course(subject_id="6.100A")
        root = AnyGroup(children=(ci_node, other_course))

        id2course = {
            "6.101": make_course_data("6.101", communication_requirement="CI-H"),
        }
        result = compute_progress(root, {"6.101"}, id2course)
        assert result.fulfilled is True

    def test_gir_threshold_in_subject_threshold_group(self):
        """GIRThreshold should work when nested in SubjectThresholdGroup."""
        gir_node = GIRThreshold(cutoff=1, gir_code="REST")
        root = SubjectThresholdGroup(children=(gir_node,), cutoff=1)

        id2course = {
            "8.01": make_course_data("8.01", gir_attribute="REST"),
        }
        result = compute_progress(root, {"8.01"}, id2course)
        assert result.fulfilled is True

    def test_hass_threshold_in_unit_threshold_group(self):
        """HASSThreshold should work when nested in UnitThresholdGroup."""
        hass_node = HASSThreshold(cutoff=1, category=None)
        root = UnitThresholdGroup(children=(hass_node,), cutoff=12)

        id2course = {
            "21L.001": make_course_data("21L.001", hass_attribute="HASS-H", total_units=12),
        }
        result = compute_progress(root, {"21L.001"}, id2course)
        assert result.fulfilled is True


class TestAllNodeTypesHandled:
    """Regression tests to ensure all node types are handled by compute_progress."""

    def test_course_node(self):
        node = Course(subject_id="6.100A")
        result = compute_progress(node, {"6.100A"}, {"6.100A": make_course_data("6.100A")})
        assert result is not None

    def test_gir_node(self):
        node = GIR(gir_code="CAL1")
        result = compute_progress(node, {"18.01"}, {"18.01": make_course_data("18.01", gir_attribute="CAL1")})
        assert result is not None

    def test_gir_threshold_node(self):
        node = GIRThreshold(cutoff=1, gir_code="CAL1")
        result = compute_progress(node, set(), {})
        assert result is not None

    def test_hass_node(self):
        node = HASS(category="HASS-A")
        result = compute_progress(node, set(), {})
        assert result is not None

    def test_hass_threshold_node(self):
        node = HASSThreshold(cutoff=1, category=None)
        result = compute_progress(node, set(), {})
        assert result is not None

    def test_ci_node(self):
        node = CI(ci_type="CI-H")
        result = compute_progress(node, set(), {})
        assert result is not None

    def test_ci_threshold_node(self):
        node = CIThreshold(cutoff=1, ci_type="CI-H")
        result = compute_progress(node, set(), {})
        assert result is not None

    def test_allgroup_node(self):
        node = AllGroup(children=())
        result = compute_progress(node, set(), {})
        assert result is not None

    def test_anygroup_node(self):
        node = AnyGroup(children=())
        result = compute_progress(node, set(), {})
        assert result is not None

    def test_subject_threshold_group_node(self):
        node = SubjectThresholdGroup(children=(), cutoff=1)
        result = compute_progress(node, set(), {})
        assert result is not None

    def test_unit_threshold_group_node(self):
        node = UnitThresholdGroup(children=(), cutoff=12)
        result = compute_progress(node, set(), {})
        assert result is not None
