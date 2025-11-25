"""
Integration tests for marker behavior with real course data and requirements.

These tests verify that markers (pin, override, banish) work correctly when
combined with real GIRs, majors, prerequisites, and the full optimizer setup.

Key scenarios tested:
- Scattered markers across different semesters
- Mix of pin/override/banish in realistic configurations
- Multiple majors with arbitrary marker placements
- Edge cases like heavy course loads in specific semesters
"""

import polars as pl
import pytest
from ortools.sat.python import cp_model

from api.models.requests import Marker
from tests.conftest import OptimizerTestConfig
from tests.test_helpers import build_optimizer_model


def build_full_optimizer(
    markers: list[Marker],
    requirement_keys: tuple[str, ...],
    start_year: int,
    max_semesters: int = 12,
) -> tuple[cp_model.CpModel, dict[tuple[int, int], cp_model.IntVar], pl.DataFrame]:
    """
    Build a complete optimizer with real data, requirements, and markers.
    
    Returns the model, take_vars, and courses_df for verification.
    """
    result = build_optimizer_model(
        requirement_keys=requirement_keys,
        markers=markers,
        start_year=start_year,
        max_semesters=max_semesters,
        with_objectives=False,
    )
    return result.model, result.take_vars, result.courses_df


def get_course_idx(courses_df: pl.DataFrame, course_id: str) -> int:
    """Get course index from course ID."""
    subject_ids = courses_df['subject_id'].to_list()
    return subject_ids.index(course_id)


@pytest.mark.slow
class TestScatteredMarkersCS:
    """Tests for Course 6-3 (CS) with markers scattered across semesters."""

    def test_cs_scattered_pins_across_four_years(self, optimizer_config: OptimizerTestConfig):
        """
        Pin courses scattered across all four years - should remain feasible.
        
        Section to semester mapping:
        - section 0 = semester 1 (Freshman Fall)
        - section 2 = semester 3 (Freshman Spring)
        - section 3 = semester 4 (Sophomore Fall)
        - section 5 = semester 6 (Sophomore Spring)
        - section 6 = semester 7 (Junior Fall)
        - section 8 = semester 9 (Junior Spring)
        - section 9 = semester 10 (Senior Fall)
        - section 11 = semester 12 (Senior Spring)
        Note: sections 1, 4, 7, 10 are IAP semesters
        """
        markers = [
            # Freshman Fall (section 0)
            Marker(courseId='6.100A', section=0, status='pin'),
            Marker(courseId='18.01', section=0, status='pin'),
            Marker(courseId='8.01', section=0, status='pin'),
            # Freshman Spring (section 2)
            Marker(courseId='6.100B', section=2, status='pin'),
            Marker(courseId='18.02', section=2, status='pin'),
            # Sophomore Fall (section 3)
            Marker(courseId='6.1010', section=3, status='pin'),
            # Junior Fall (section 6)
            Marker(courseId='6.1800', section=6, status='pin'),
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major6-3new', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "6-3 with scattered pins should be feasible"

    def test_cs_mixed_pin_override_banish(self, optimizer_config: OptimizerTestConfig):
        """
        Mix of all marker types scattered across semesters.
        """
        markers = [
            # ASE credits
            Marker(courseId='18.01', section=-1, status='pin'),
            Marker(courseId='8.01', section=-1, status='pin'),
            # Freshman Fall - pin and override
            Marker(courseId='6.100A', section=0, status='pin'),
            Marker(courseId='18.02', section=0, status='override'),  # Skip prereq
            # Banish from Freshman Spring (section 2 = semester 3)
            Marker(courseId='6.1010', section=2, status='banish'),   # Can't take in spring
            # Sophomore Fall - more pins
            Marker(courseId='6.1200', section=3, status='pin'),      # Math for CS
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major6-3new', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "6-3 with mixed markers should be feasible"

        # Verify banish is respected (section 2 = semester 3)
        course_idx = get_course_idx(courses_df, '6.1010')
        assert solver.Value(take_vars[(course_idx, 3)]) == 0, \
            "6.1010 should not be in semester 3 (banished)"

    def test_cs_override_multiple_advanced_courses(self, optimizer_config: OptimizerTestConfig):
        """
        Override multiple advanced courses to take them early.
        """
        markers = [
            # Override advanced courses into sophomore year
            Marker(courseId='6.1010', section=3, status='override'),   # Fundamentals
            Marker(courseId='6.1800', section=3, status='override'),   # Systems
            Marker(courseId='6.1200', section=3, status='override'),   # Math for CS
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major6-3new', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "6-3 with multiple overrides should be feasible"


@pytest.mark.slow
class TestScatteredMarkersMechE:
    """Tests for Course 2 (MechE) with scattered markers."""

    def test_meche_realistic_schedule(self, optimizer_config: OptimizerTestConfig):
        """
        Realistic MechE schedule with courses pinned to typical semesters.
        """
        markers = [
            # Freshman Fall (section 0)
            Marker(courseId='18.01', section=0, status='pin'),
            Marker(courseId='8.01', section=0, status='pin'),
            # Freshman Spring (section 2)
            Marker(courseId='18.02', section=2, status='pin'),
            Marker(courseId='8.02', section=2, status='pin'),
            # Sophomore Fall (section 3) - core MechE
            Marker(courseId='2.001', section=3, status='pin'),    # Mechanics
            # Sophomore Spring (section 5)
            Marker(courseId='2.003', section=5, status='pin'),    # Dynamics
            # Junior Fall (section 6)
            Marker(courseId='2.004', section=6, status='pin'),    # Dynamics & Control II
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major2', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "MechE with realistic schedule should be feasible"

    def test_meche_with_ase_and_overrides(self, optimizer_config: OptimizerTestConfig):
        """
        MechE with ASE credits and some overrides.
        """
        markers = [
            # ASE - came in with AP credits
            Marker(courseId='18.01', section=-1, status='pin'),
            Marker(courseId='18.02', section=-1, status='pin'),
            Marker(courseId='8.01', section=-1, status='pin'),
            # Override to take 2.001 early (freshman spring = section 2)
            Marker(courseId='2.001', section=2, status='override'),
            # Pin later courses (sophomore fall = section 3)
            Marker(courseId='2.003', section=3, status='pin'),
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major2', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "MechE with ASE and overrides should be feasible"


@pytest.mark.slow
class TestScatteredMarkersMath:
    """Tests for Course 18 (Math) with scattered markers."""

    def test_math_heavy_first_year(self, optimizer_config: OptimizerTestConfig):
        """
        Math major with heavy course load pinned to freshman year.
        
        Note: 18.02 requires 18.01 as prereq, so we put 18.01 in ASE.
        18.06 requires CAL2 (18.02), so we put 18.02 in fall and 18.06 in spring.
        """
        markers = [
            # ASE - 18.01 as prior credit so 18.02 can be in fall
            Marker(courseId='18.01', section=-1, status='pin'),
            # Heavy freshman fall (section 0)
            Marker(courseId='18.02', section=0, status='pin'),     # CAL2 - needed for 18.06
            Marker(courseId='8.01', section=0, status='pin'),
            # Freshman spring (section 2) - courses that need fall prereqs
            Marker(courseId='18.06', section=2, status='pin'),     # Linear Algebra (needs CAL2)
            Marker(courseId='18.03', section=2, status='pin'),     # Diff Eq
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major18pm', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Math with heavy first year should be feasible"

    def test_math_override_to_skip_prereqs(self, optimizer_config: OptimizerTestConfig):
        """
        Override allows taking 18.06 without CAL2 prerequisite.
        
        Without override, 18.06 requires 18.02 (CAL2) first.
        With override, we can take 18.06 in Freshman Fall.
        """
        markers = [
            # Override 18.06 to take without prereqs
            Marker(courseId='18.06', section=0, status='override'),  # Freshman Fall - no prereq needed
            Marker(courseId='18.01', section=0, status='pin'),
            Marker(courseId='8.01', section=0, status='pin'),
            # Take 18.02 later (normally this would need to be before 18.06)
            Marker(courseId='18.02', section=2, status='pin'),        # Freshman Spring
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major18pm', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Math with override on 18.06 should be feasible"

        # Verify 18.06 is in Freshman Fall (semester 1)
        course_idx = get_course_idx(courses_df, '18.06')
        assert solver.Value(take_vars[(course_idx, 1)]) == 1, \
            "18.06 should be in semester 1 (override)"

    def test_math_with_scattered_banishes(self, optimizer_config: OptimizerTestConfig):
        """
        Math major with courses banished from certain semesters.
        """
        markers = [
            # Pin basics
            Marker(courseId='18.01', section=0, status='pin'),       # Freshman Fall
            Marker(courseId='18.02', section=2, status='pin'),       # Freshman Spring
            # Banish 18.06 from fall semesters (only want in spring)
            Marker(courseId='18.06', section=0, status='banish'),    # Ban from Freshman Fall
            Marker(courseId='18.06', section=3, status='banish'),    # Ban from Sophomore Fall
            Marker(courseId='18.06', section=6, status='banish'),    # Ban from Junior Fall
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major18pm', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Math with scattered banishes should be feasible"


@pytest.mark.slow
class TestScatteredMarkersDoubleMajor:
    """Tests for double majors with scattered markers."""

    def test_cs_math_double_major_scattered(self, optimizer_config: OptimizerTestConfig):
        """
        Double major 6-3 + 18C with markers scattered across schedule.
        """
        markers = [
            # ASE
            Marker(courseId='18.01', section=-1, status='pin'),
            Marker(courseId='18.02', section=-1, status='pin'),
            # Freshman Fall (section 0)
            Marker(courseId='6.100A', section=0, status='pin'),
            Marker(courseId='8.01', section=0, status='pin'),
            # Freshman Spring (section 2)
            Marker(courseId='6.100B', section=2, status='pin'),
            Marker(courseId='18.06', section=2, status='pin'),
            # Sophomore Fall (section 3)
            Marker(courseId='6.1010', section=3, status='pin'),
            # Sophomore Spring (section 5)
            Marker(courseId='18.03', section=5, status='pin'),
            # Junior Fall (section 6) - override to pack in more
            Marker(courseId='6.1800', section=6, status='override'),
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major6-3new', 'major18c', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Double major 6-3 + 18C with scattered markers should be feasible"

    def test_cs_econ_double_major(self, optimizer_config: OptimizerTestConfig):
        """
        Double major 6-3 + 14 (Economics) with scattered markers.
        """
        markers = [
            # ASE
            Marker(courseId='18.01', section=-1, status='pin'),
            # Freshman Fall (section 0)
            Marker(courseId='6.100A', section=0, status='pin'),
            Marker(courseId='14.01', section=0, status='pin'),     # Micro
            # Freshman Spring (section 2)
            Marker(courseId='18.02', section=2, status='pin'),
            Marker(courseId='14.02', section=2, status='pin'),     # Macro
            # Sophomore Fall (section 3)
            Marker(courseId='6.1010', section=3, status='pin'),
            # Sophomore Spring (section 5)
            Marker(courseId='14.30', section=5, status='pin'),     # Stats
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major6-3new', 'major14-1', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Double major 6-3 + 14 with scattered markers should be feasible"


@pytest.mark.slow
class TestEdgeCaseMarkers:
    """Edge cases and stress tests for markers."""

    def test_all_girs_in_ase(self, optimizer_config: OptimizerTestConfig):
        """
        Student with all GIR science courses in ASE.
        """
        markers = [
            Marker(courseId='18.01', section=-1, status='pin'),
            Marker(courseId='18.02', section=-1, status='pin'),
            Marker(courseId='8.01', section=-1, status='pin'),
            Marker(courseId='8.02', section=-1, status='pin'),
            Marker(courseId='5.111', section=-1, status='pin'),   # Chemistry
            Marker(courseId='7.012', section=-1, status='pin'),   # Biology
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "All GIR science in ASE should be feasible"

    def test_heavy_single_semester_load(self, optimizer_config: OptimizerTestConfig):
        """
        Many courses pinned to a single semester.
        """
        markers = [
            # All in Freshman Fall (section 0)
            Marker(courseId='18.01', section=0, status='pin'),
            Marker(courseId='8.01', section=0, status='pin'),
            Marker(courseId='6.100A', section=0, status='pin'),
            Marker(courseId='7.012', section=0, status='pin'),
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('girs',),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Heavy single semester load should be feasible"

    def test_markers_every_year(self, optimizer_config: OptimizerTestConfig):
        """
        Markers scattered across all four years (avoiding IAP semesters).
        """
        markers = [
            Marker(courseId='18.01', section=-1, status='pin'),    # ASE
            Marker(courseId='8.01', section=0, status='pin'),      # Freshman Fall
            Marker(courseId='18.02', section=2, status='pin'),     # Freshman Spring
            Marker(courseId='8.02', section=3, status='pin'),      # Sophomore Fall
            Marker(courseId='6.100A', section=5, status='pin'),    # Sophomore Spring
            Marker(courseId='6.100B', section=6, status='pin'),    # Junior Fall
            Marker(courseId='6.1010', section=8, status='pin'),    # Junior Spring
            Marker(courseId='6.1200', section=9, status='pin'),    # Senior Fall
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major6-3new', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Markers scattered across all years should be feasible"

    def test_multiple_banishes_same_semester(self, optimizer_config: OptimizerTestConfig):
        """
        Multiple courses banished from the same semester.
        """
        markers = [
            # Banish multiple courses from Freshman Fall
            Marker(courseId='6.100A', section=0, status='banish'),
            Marker(courseId='18.01', section=0, status='banish'),
            Marker(courseId='8.01', section=0, status='banish'),
        ]

        model, take_vars, courses_df = build_full_optimizer(
            markers=markers,
            requirement_keys=('major6-3new', 'girs'),
            start_year=optimizer_config.start_year,
            max_semesters=optimizer_config.max_semesters,
        )

        solver = cp_model.CpSolver()
        optimizer_config.configure_solver(solver)
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Multiple banishes from same semester should be feasible"

        # Verify none of the banished courses are in semester 1
        for course_id in ['6.100A', '18.01', '8.01']:
            course_idx = get_course_idx(courses_df, course_id)
            assert solver.Value(take_vars[(course_idx, 1)]) == 0, \
                f"{course_id} should not be in semester 1"
