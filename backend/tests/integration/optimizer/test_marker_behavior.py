"""
Integration tests for marker behavior: pin, override, and banish.

These tests verify the specific behavior of each marker type:
- Pin: Forces a course to a specific semester
- Override: Forces a course to a specific semester AND skips prerequisites
- Banish: Prevents a course from being scheduled in a specific semester

Unlike test_marker_integration.py which tests scattered markers across schedules,
these tests focus on verifying the exact behavior of each marker type.
"""

import polars as pl
import pytest
from ortools.sat.python import cp_model

from api.models.requests import Marker
from api.services.cache import get_courses_data, get_parsed_prerequisites, get_requirements
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.constraints.basic import add_basic_constraints, create_take_vars
from optimizer.marker_constraint_builder import add_marker_constraints
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints
from tests.conftest import OptimizerTestConfig


def build_optimizer_with_markers(
    markers: list[Marker],
    requirement_keys: tuple[str, ...],
    start_year: int,
    max_semesters: int = 12,
) -> tuple[cp_model.CpModel, dict[tuple[int, int], cp_model.IntVar], pl.DataFrame, cp_model.CpSolver]:
    """
    Build optimizer with markers and return solved state.
    
    Returns model, take_vars, courses_df, and solver (after solving).
    """
    courses_data = get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    requirements_data = get_requirements(requirement_keys)
    prereq_trees = get_parsed_prerequisites(courses_df)

    model = cp_model.CpModel()
    take_vars = create_take_vars(
        model, courses_df, start_year,
        max_semesters=max_semesters, markers=markers
    )
    add_basic_constraints(model, take_vars, courses_df, max_semesters=max_semesters)

    for req_key in requirement_keys:
        if req_key in requirements_data:
            req_data = requirements_data[req_key]
            if isinstance(req_data, dict):
                req_tree = parse_requirement({
                    'reqs': req_data.get('reqs', []),
                    'title': req_key
                })
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                if validation.pruned_tree is not None:
                    add_requirement_constraints(
                        model, take_vars, validation.pruned_tree,
                        courses_df, start_year, enforce=True
                    )

    override_course_ids = {m.courseId for m in markers if m.status == 'override'}
    add_prerequisite_constraints(
        model, take_vars, courses_df, start_year,
        prereq_trees, override_course_ids
    )

    add_marker_constraints(model, take_vars, markers, courses_df, start_year)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.Solve(model)

    return model, take_vars, courses_df, solver


def get_course_idx(courses_df: pl.DataFrame, course_id: str) -> int:
    """Get course index from course ID."""
    subject_ids = courses_df['subject_id'].to_list()
    return subject_ids.index(course_id)


def section_to_semester(section: int) -> int:
    """
    Convert section to semester.
    
    section -1 = semester -1 (ASE)
    section 0 = semester 1 (Freshman Fall)
    section 1 = semester 2 (Freshman IAP)
    section 2 = semester 3 (Freshman Spring)
    etc.
    """
    if section == -1:
        return -1
    return section + 1


# =============================================================================
# PIN BEHAVIOR TESTS
# =============================================================================

@pytest.mark.slow
class TestPinBehavior:
    """Tests that verify pin marker behavior."""

    def test_pin_forces_course_to_exact_semester(self, optimizer_config: OptimizerTestConfig):
        """Pin should force the course to the exact specified semester."""
        target_section = 3  # Sophomore Fall (semester 4)
        target_semester = section_to_semester(target_section)

        markers = [
            Marker(courseId='6.100A', section=target_section, status='pin'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Pin should produce feasible solution"

        course_idx = get_course_idx(courses_df, '6.100A')
        assert solver.Value(take_vars[(course_idx, target_semester)]) == 1, \
            f"6.100A should be in semester {target_semester}"

        # Verify it's not in any other semester
        for sem in range(1, 13):
            if sem != target_semester:
                if (course_idx, sem) in take_vars:
                    assert solver.Value(take_vars[(course_idx, sem)]) == 0, \
                        f"6.100A should NOT be in semester {sem}"

    def test_pin_to_ase_semester(self, optimizer_config: OptimizerTestConfig):
        """Pin to ASE (section -1) should place course in semester -1."""
        markers = [
            Marker(courseId='18.01', section=-1, status='pin'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Pin to ASE should produce feasible solution"

        course_idx = get_course_idx(courses_df, '18.01')
        assert solver.Value(take_vars[(course_idx, -1)]) == 1, \
            "18.01 should be in ASE (semester -1)"

    def test_multiple_pins_same_semester(self, optimizer_config: OptimizerTestConfig):
        """Multiple courses can be pinned to the same semester."""
        target_section = 0  # Freshman Fall (semester 1)
        target_semester = section_to_semester(target_section)

        markers = [
            Marker(courseId='18.01', section=target_section, status='pin'),
            Marker(courseId='8.01', section=target_section, status='pin'),
            Marker(courseId='6.100A', section=target_section, status='pin'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Multiple pins to same semester should be feasible"

        for course_id in ['18.01', '8.01', '6.100A']:
            course_idx = get_course_idx(courses_df, course_id)
            assert solver.Value(take_vars[(course_idx, target_semester)]) == 1, \
                f"{course_id} should be in semester {target_semester}"

    def test_pin_respects_prerequisites(self, optimizer_config: OptimizerTestConfig):
        """
        Pin should still enforce prerequisites.
        
        6.100B requires 6.100A, so pinning 6.100B to semester 1 should fail
        if 6.100A isn't taken before.
        """
        # Pin 6.100B to Freshman Fall, but no 6.100A pinned before
        markers = [
            Marker(courseId='6.100B', section=0, status='pin'),  # Freshman Fall
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        # This should be infeasible because 6.100B needs 6.100A first
        # and you can't take 6.100A before semester 1
        assert solver.StatusName() == 'INFEASIBLE', \
            "Pin should enforce prerequisites (6.100B needs 6.100A first)"

    def test_pin_with_prerequisite_satisfied(self, optimizer_config: OptimizerTestConfig):
        """Pin should work when prerequisites are satisfied."""
        markers = [
            Marker(courseId='6.100A', section=0, status='pin'),  # Freshman Fall
            Marker(courseId='6.100B', section=2, status='pin'),  # Freshman Spring
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Pin with satisfied prereqs should be feasible"

        a_idx = get_course_idx(courses_df, '6.100A')
        b_idx = get_course_idx(courses_df, '6.100B')
        assert solver.Value(take_vars[(a_idx, 1)]) == 1, "6.100A in semester 1"
        assert solver.Value(take_vars[(b_idx, 3)]) == 1, "6.100B in semester 3"


# =============================================================================
# OVERRIDE BEHAVIOR TESTS
# =============================================================================

@pytest.mark.slow
class TestOverrideBehavior:
    """Tests that verify override marker behavior."""

    def test_override_forces_course_to_semester(self, optimizer_config: OptimizerTestConfig):
        """Override should force the course to the specified semester."""
        target_section = 3  # Sophomore Fall (semester 4)
        target_semester = section_to_semester(target_section)

        markers = [
            Marker(courseId='6.100A', section=target_section, status='override'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Override should produce feasible solution"

        course_idx = get_course_idx(courses_df, '6.100A')
        assert solver.Value(take_vars[(course_idx, target_semester)]) == 1, \
            f"6.100A should be in semester {target_semester}"

    def test_override_skips_prerequisites(self, optimizer_config: OptimizerTestConfig):
        """
        Override should allow taking a course without its prerequisites.
        
        6.100B normally requires 6.100A first.
        Override should allow 6.100B in semester 1 without 6.100A.
        """
        markers = [
            Marker(courseId='6.100B', section=0, status='override'),  # Freshman Fall
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Override should skip prereqs and be feasible"

        course_idx = get_course_idx(courses_df, '6.100B')
        assert solver.Value(take_vars[(course_idx, 1)]) == 1, \
            "6.100B should be in semester 1 (override skips prereqs)"

    def test_override_allows_prereq_after_course(self, optimizer_config: OptimizerTestConfig):
        """
        Override allows taking the prerequisite AFTER the course.
        
        18.06 requires 18.02 (CAL2).
        With override, we can take 18.06 first and 18.02 later.
        """
        markers = [
            Marker(courseId='18.06', section=0, status='override'),  # Freshman Fall
            Marker(courseId='18.02', section=2, status='pin'),        # Freshman Spring (after!)
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Override should allow prereq after course"

        idx_1806 = get_course_idx(courses_df, '18.06')
        idx_1802 = get_course_idx(courses_df, '18.02')

        assert solver.Value(take_vars[(idx_1806, 1)]) == 1, "18.06 in semester 1"
        assert solver.Value(take_vars[(idx_1802, 3)]) == 1, "18.02 in semester 3"

    def test_override_multiple_courses(self, optimizer_config: OptimizerTestConfig):
        """Multiple courses can have override status."""
        markers = [
            Marker(courseId='6.100B', section=0, status='override'),  # No 6.100A needed
            Marker(courseId='18.06', section=0, status='override'),   # No 18.02 needed
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Multiple overrides should be feasible"

    def test_override_does_not_affect_other_courses_prereqs(self, optimizer_config: OptimizerTestConfig):
        """
        Override only skips prereqs for the overridden course.
        Other courses still need their prerequisites.
        """
        markers = [
            Marker(courseId='6.100A', section=0, status='override'),
            # 6.100B is NOT overridden, should still need 6.100A first
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('major6-3new', 'girs'),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE']

        a_idx = get_course_idx(courses_df, '6.100A')
        b_idx = get_course_idx(courses_df, '6.100B')

        a_sem = None
        b_sem = None
        for sem in range(-1, 13):
            if (a_idx, sem) in take_vars and solver.Value(take_vars[(a_idx, sem)]) == 1:
                a_sem = sem
            if (b_idx, sem) in take_vars and solver.Value(take_vars[(b_idx, sem)]) == 1:
                b_sem = sem

        if b_sem is not None and a_sem is not None:
            assert a_sem < b_sem, \
                f"6.100B (sem {b_sem}) should be after 6.100A (sem {a_sem})"


# =============================================================================
# BANISH BEHAVIOR TESTS
# =============================================================================

@pytest.mark.slow
class TestBanishBehavior:
    """Tests that verify banish marker behavior."""

    def test_banish_prevents_course_in_semester(self, optimizer_config: OptimizerTestConfig):
        """Banish should prevent a course from being in the specified semester."""
        banished_section = 0  # Freshman Fall (semester 1)
        banished_semester = section_to_semester(banished_section)

        markers = [
            Marker(courseId='18.01', section=banished_section, status='banish'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Banish should produce feasible solution"

        course_idx = get_course_idx(courses_df, '18.01')
        assert solver.Value(take_vars[(course_idx, banished_semester)]) == 0, \
            f"18.01 should NOT be in semester {banished_semester} (banished)"

    def test_banish_allows_course_in_other_semesters(self, optimizer_config: OptimizerTestConfig):
        """Banish only affects the specific semester, course can be elsewhere."""
        banished_section = 0  # Freshman Fall (semester 1)
        banished_semester = section_to_semester(banished_section)

        markers = [
            Marker(courseId='18.01', section=banished_section, status='banish'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE']

        course_idx = get_course_idx(courses_df, '18.01')

        # Find where 18.01 was placed
        placed_semester = None
        for sem in range(-1, 13):
            if (course_idx, sem) in take_vars and solver.Value(take_vars[(course_idx, sem)]) == 1:
                placed_semester = sem
                break

        assert placed_semester is not None, "18.01 should be placed somewhere"
        assert placed_semester != banished_semester, \
            f"18.01 should not be in banished semester {banished_semester}"

    def test_banish_multiple_semesters(self, optimizer_config: OptimizerTestConfig):
        """A course can be banished from multiple semesters."""
        markers = [
            Marker(courseId='18.01', section=0, status='banish'),  # Not in Freshman Fall
            Marker(courseId='18.01', section=2, status='banish'),  # Not in Freshman Spring
            Marker(courseId='18.01', section=3, status='banish'),  # Not in Sophomore Fall
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Multiple banishes should be feasible"

        course_idx = get_course_idx(courses_df, '18.01')

        # Verify not in any banished semester
        assert solver.Value(take_vars[(course_idx, 1)]) == 0, "Not in semester 1"
        assert solver.Value(take_vars[(course_idx, 3)]) == 0, "Not in semester 3"
        assert solver.Value(take_vars[(course_idx, 4)]) == 0, "Not in semester 4"

    def test_banish_multiple_courses_same_semester(self, optimizer_config: OptimizerTestConfig):
        """Multiple courses can be banished from the same semester."""
        markers = [
            Marker(courseId='18.01', section=0, status='banish'),
            Marker(courseId='8.01', section=0, status='banish'),
            Marker(courseId='6.100A', section=0, status='banish'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Multiple courses banished from same semester should be feasible"

        for course_id in ['18.01', '8.01', '6.100A']:
            course_idx = get_course_idx(courses_df, course_id)
            assert solver.Value(take_vars[(course_idx, 1)]) == 0, \
                f"{course_id} should NOT be in semester 1"

    def test_banish_respects_other_constraints(self, optimizer_config: OptimizerTestConfig):
        """Banish works alongside other constraints like prerequisites."""
        markers = [
            Marker(courseId='6.100A', section=0, status='pin'),    # Pin to Fall
            Marker(courseId='6.100B', section=2, status='banish'),  # Can't be in Spring
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('major6-3new', 'girs'),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE']

        b_idx = get_course_idx(courses_df, '6.100B')

        # 6.100B can't be in semester 3 (banished from Freshman Spring)
        assert solver.Value(take_vars[(b_idx, 3)]) == 0, \
            "6.100B should NOT be in semester 3 (banished)"


# =============================================================================
# COMBINED MARKER BEHAVIOR TESTS
# =============================================================================

@pytest.mark.slow
class TestCombinedMarkerBehavior:
    """Tests that verify interactions between different marker types."""

    def test_pin_and_banish_different_courses(self, optimizer_config: OptimizerTestConfig):
        """Pin and banish can be used together on different courses."""
        markers = [
            Marker(courseId='18.01', section=0, status='pin'),     # Pin to Fall
            Marker(courseId='8.01', section=0, status='banish'),   # Can't be in Fall
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE']

        idx_1801 = get_course_idx(courses_df, '18.01')
        idx_801 = get_course_idx(courses_df, '8.01')

        assert solver.Value(take_vars[(idx_1801, 1)]) == 1, "18.01 pinned to semester 1"
        assert solver.Value(take_vars[(idx_801, 1)]) == 0, "8.01 banished from semester 1"

    def test_override_and_banish_same_course(self, optimizer_config: OptimizerTestConfig):
        """
        Override and banish can both affect the same course.
        Override pins to one semester, banish prevents another.
        """
        markers = [
            Marker(courseId='6.100B', section=0, status='override'),  # Override to Fall
            Marker(courseId='6.100B', section=2, status='banish'),    # Banish from Spring (redundant but valid)
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE']

        course_idx = get_course_idx(courses_df, '6.100B')
        assert solver.Value(take_vars[(course_idx, 1)]) == 1, "6.100B in semester 1 (override)"
        assert solver.Value(take_vars[(course_idx, 3)]) == 0, "6.100B not in semester 3 (banish)"

    def test_all_marker_types_together(self, optimizer_config: OptimizerTestConfig):
        """All three marker types working together."""
        markers = [
            # ASE credit
            Marker(courseId='18.01', section=-1, status='pin'),
            # Regular pins
            Marker(courseId='8.01', section=0, status='pin'),         # Freshman Fall
            Marker(courseId='18.02', section=2, status='pin'),        # Freshman Spring
            # Override - skip prereqs
            Marker(courseId='6.100B', section=0, status='override'),  # No 6.100A needed
            # Banish
            Marker(courseId='6.100A', section=0, status='banish'),    # Can't be in Fall
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "All marker types together should be feasible"

        # Verify each marker's effect
        idx_1801 = get_course_idx(courses_df, '18.01')
        idx_801 = get_course_idx(courses_df, '8.01')
        idx_1802 = get_course_idx(courses_df, '18.02')
        idx_100b = get_course_idx(courses_df, '6.100B')
        idx_100a = get_course_idx(courses_df, '6.100A')

        assert solver.Value(take_vars[(idx_1801, -1)]) == 1, "18.01 in ASE"
        assert solver.Value(take_vars[(idx_801, 1)]) == 1, "8.01 in semester 1 (pin)"
        assert solver.Value(take_vars[(idx_1802, 3)]) == 1, "18.02 in semester 3 (pin)"
        assert solver.Value(take_vars[(idx_100b, 1)]) == 1, "6.100B in semester 1 (override)"
        assert solver.Value(take_vars[(idx_100a, 1)]) == 0, "6.100A not in semester 1 (banish)"

    def test_complex_realistic_scenario(self, optimizer_config: OptimizerTestConfig):
        """
        Realistic scenario with ASE credits, pins, overrides, and banishes
        for a CS major.
        """
        markers = [
            # ASE - came in with calculus credit
            Marker(courseId='18.01', section=-1, status='pin'),
            Marker(courseId='18.02', section=-1, status='pin'),
            # Freshman Fall - light load due to adjustment
            Marker(courseId='8.01', section=0, status='pin'),
            Marker(courseId='6.100A', section=0, status='pin'),
            # Want to delay physics II
            Marker(courseId='8.02', section=0, status='banish'),
            Marker(courseId='8.02', section=2, status='banish'),
            # Override to take 6.1010 early (normally needs 6.100B)
            Marker(courseId='6.1010', section=2, status='override'),
            # Regular pin for 6.100B
            Marker(courseId='6.100B', section=3, status='pin'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('major6-3new', 'girs'),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Complex realistic scenario should be feasible"

        # Verify key constraints
        idx_802 = get_course_idx(courses_df, '8.02')
        assert solver.Value(take_vars[(idx_802, 1)]) == 0, "8.02 banished from semester 1"
        assert solver.Value(take_vars[(idx_802, 3)]) == 0, "8.02 banished from semester 3"

        idx_6_1010 = get_course_idx(courses_df, '6.1010')
        assert solver.Value(take_vars[(idx_6_1010, 3)]) == 1, "6.1010 in semester 3 (override)"


# =============================================================================
# EDGE CASES AND ERROR CONDITIONS
# =============================================================================

@pytest.mark.slow
class TestMarkerEdgeCases:
    """Edge cases and boundary conditions for markers."""

    def test_pin_and_banish_same_course_same_semester_is_infeasible(self, optimizer_config: OptimizerTestConfig):
        """
        Pinning and banishing a course to the same semester is contradictory.
        """
        markers = [
            Marker(courseId='18.01', section=0, status='pin'),
            Marker(courseId='18.01', section=0, status='banish'),
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() == 'INFEASIBLE', \
            "Pin + banish same semester should be infeasible"

    def test_banish_course_with_equivalents_still_feasible(self, optimizer_config: OptimizerTestConfig):
        """
        Banishing a course from all regular semesters is still feasible if equivalents exist.
        
        18.01 has equivalents (like 18.01A) that can satisfy CAL1, so banishing
        18.01 from all regular semesters should NOT make the problem infeasible.
        """
        # Banish 18.01 from all regular semesters (sections 0-11 = semesters 1-12)
        markers = [
            Marker(courseId='18.01', section=s, status='banish')
            for s in range(0, 12)  # sections 0-11 = semesters 1-12
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        # Should still be feasible - equivalents like 18.01A can satisfy CAL1
        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Banishing course with equivalents should still be feasible"

        # Verify 18.01 is not taken in any regular semester (1-12)
        course_idx = get_course_idx(courses_df, '18.01')
        for sem in range(1, 13):
            if (course_idx, sem) in take_vars:
                assert solver.Value(take_vars[(course_idx, sem)]) == 0, \
                    f"18.01 should not be in semester {sem} (banished)"

    def test_empty_markers_still_works(self, optimizer_config: OptimizerTestConfig):
        """No markers at all should still produce valid solution."""
        markers: list[Marker] = []

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "No markers should be feasible"

    def test_duplicate_pin_markers_same_semester(self, optimizer_config: OptimizerTestConfig):
        """Duplicate pin markers for same course/semester should work."""
        markers = [
            Marker(courseId='18.01', section=0, status='pin'),
            Marker(courseId='18.01', section=0, status='pin'),  # Duplicate
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() in ['OPTIMAL', 'FEASIBLE'], \
            "Duplicate pins should be handled gracefully"

    def test_pin_to_conflicting_semesters_infeasible(self, optimizer_config: OptimizerTestConfig):
        """Pinning same course to different semesters is impossible."""
        markers = [
            Marker(courseId='18.01', section=0, status='pin'),  # Semester 1
            Marker(courseId='18.01', section=2, status='pin'),  # Semester 3
        ]

        model, take_vars, courses_df, solver = build_optimizer_with_markers(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
        )

        assert solver.StatusName() == 'INFEASIBLE', \
            "Pinning to two different semesters should be infeasible"
