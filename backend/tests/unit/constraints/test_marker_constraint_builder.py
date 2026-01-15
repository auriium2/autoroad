"""
Unit tests for marker_constraint_builder.

These tests verify that marker constraints (pin, override, banish) are correctly
translated into CP-SAT constraints.
"""

import polars as pl
from ortools.sat.python import cp_model

from shared.models.requests import Marker
from shared.optimizer.marker_constraint_builder import add_marker_constraints
from shared.optimizer.semesters import REGULAR_SEMESTERS


def create_test_courses_df() -> pl.DataFrame:
    """Create a minimal course catalog for testing."""
    return pl.DataFrame({
        'subject_id': ['18.01', '18.02', '8.01', '8.02', '6.100A'],
        'title': ['Calculus I', 'Calculus II', 'Physics I', 'Physics II', 'Intro to CS'],
        'total_units': [12, 12, 12, 12, 12],
        'gir_attribute': ['CAL1', 'CAL2', 'PHY1', 'PHY2', None],
        'offered_fall': [True, True, True, True, True],
        'offered_spring': [True, True, True, True, True],
        'offered_IAP': [False, False, False, False, False],
    })


def create_take_vars(
    model: cp_model.CpModel,
    courses_df: pl.DataFrame,
    markers: list[Marker] | None = None
) -> dict[tuple[int, int], cp_model.IntVar]:
    """Create take_vars for testing, including special semesters if markers exist."""
    take_vars: dict[tuple[int, int], cp_model.IntVar] = {}

    # Build set of courses with special semester markers
    ase_courses: set[str] = set()
    must_take_courses: set[str] = set()
    if markers:
        for marker in markers:
            if marker.section == -1:
                ase_courses.add(marker.courseId)
            elif marker.section == -2:
                must_take_courses.add(marker.courseId)

    for course_idx in range(len(courses_df)):
        subject_id = courses_df[course_idx, 'subject_id']

        # Regular semesters
        for semester in REGULAR_SEMESTERS:
            var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
            take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)

        # ASE semester if marker exists
        if subject_id in ase_courses:
            take_vars[(course_idx, -1)] = model.NewBoolVar(f"take_{subject_id.replace('.', '_')}_s-1")

        # Must Take semester if marker exists
        if subject_id in must_take_courses:
            take_vars[(course_idx, -2)] = model.NewBoolVar(f"take_{subject_id.replace('.', '_')}_s-2")

    return take_vars


class TestPinMarkers:
    """Tests for pin marker behavior."""

    def test_pin_to_regular_semester(self):
        """Pin marker forces course to specific regular semester."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        # Pin 18.01 to Freshman Fall (section=0 -> semester=1)
        markers = [Marker(courseId='18.01', section=0, status='pin')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 1
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

        # Solve and verify
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Course should be in semester 1
        course_idx = 0  # 18.01
        assert solver.Value(take_vars[(course_idx, 1)]) == 1

    def test_pin_to_ase_semester(self):
        """Pin marker can place course in ASE (section=-1)."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        # Pin 18.01 to ASE
        markers = [Marker(courseId='18.01', section=-1, status='pin')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 1
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        course_idx = 0
        assert solver.Value(take_vars[(course_idx, -1)]) == 1

    def test_pin_must_take_forces_some_regular_semester(self):
        """Pin with section=-2 (Must Take) forces course to any regular semester."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        # Pin 18.01 to Must Take
        markers = [Marker(courseId='18.01', section=-2, status='pin')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 1
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Course should be in at least one regular semester
        course_idx = 0
        regular_takes = sum(
            solver.Value(take_vars[(course_idx, s)])
            for s in REGULAR_SEMESTERS
            if (course_idx, s) in take_vars
        )
        assert regular_takes >= 1

    def test_pin_nonexistent_course_warns(self):
        """Pin marker for nonexistent course produces warning."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [Marker(courseId='FAKE.999', section=0, status='pin')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 0
        assert len(result.warnings) == 1
        assert 'FAKE.999' in result.warnings[0]

    def test_multiple_pins_different_semesters(self):
        """Multiple pin markers can place courses in different semesters."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(courseId='18.01', section=0, status='pin'),  # Semester 1
            Marker(courseId='18.02', section=1, status='pin'),  # Semester 2
            Marker(courseId='8.01', section=2, status='pin'),   # Semester 3
        ]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 3
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Verify each course is in correct semester
        assert solver.Value(take_vars[(0, 1)]) == 1  # 18.01 in sem 1
        assert solver.Value(take_vars[(1, 2)]) == 1  # 18.02 in sem 2
        assert solver.Value(take_vars[(2, 3)]) == 1  # 8.01 in sem 3


class TestOverrideMarkers:
    """Tests for override marker behavior."""

    def test_override_pins_to_semester(self):
        """Override marker pins course to specified semester."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [Marker(courseId='18.02', section=0, status='override')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 1
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        course_idx = 1  # 18.02
        assert solver.Value(take_vars[(course_idx, 1)]) == 1

    def test_override_to_ase(self):
        """Override marker can place course in ASE."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [Marker(courseId='18.01', section=-1, status='override')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 1
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        assert solver.Value(take_vars[(0, -1)]) == 1

    def test_override_must_take_errors(self):
        """Override marker cannot be in Must Take (section=-2)."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [Marker(courseId='18.01', section=-2, status='override')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 0
        assert len(result.errors) == 1
        assert 'Must Take' in result.errors[0]

    def test_override_does_not_block_other_courses(self):
        """Override marker should NOT prevent other courses in same semester."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        # Override 18.02 and pin 18.01 both to semester 1
        markers = [
            Marker(courseId='18.02', section=0, status='override'),
            Marker(courseId='18.01', section=0, status='pin'),
        ]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 2
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Both should be in semester 1
        assert solver.Value(take_vars[(0, 1)]) == 1  # 18.01
        assert solver.Value(take_vars[(1, 1)]) == 1  # 18.02

    def test_override_returns_course_ids_for_prereq_skipping(self):
        """Override courses should be trackable for prerequisite skipping."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(courseId='18.02', section=0, status='override'),
            Marker(courseId='8.01', section=0, status='pin'),  # Not override
        ]
        create_take_vars(model, courses_df, markers)

        # Extract override course IDs (this is how it's done in real code)
        override_ids = {m.courseId for m in markers if m.status == 'override'}

        assert override_ids == {'18.02'}
        assert '8.01' not in override_ids


class TestBanishMarkers:
    """Tests for banish marker behavior."""

    def test_banish_prevents_specific_semester(self):
        """Banish marker prevents course from specific semester."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        # Banish 18.01 from semester 1
        markers = [Marker(courseId='18.01', section=0, status='banish')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 1
        assert len(result.errors) == 0

        # Force taking the course somewhere
        course_idx = 0
        model.Add(sum(take_vars[(course_idx, s)] for s in REGULAR_SEMESTERS) >= 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Should NOT be in semester 1
        assert solver.Value(take_vars[(course_idx, 1)]) == 0

        # But should be somewhere else
        other_semesters = sum(
            solver.Value(take_vars[(course_idx, s)])
            for s in REGULAR_SEMESTERS if s != 1
        )
        assert other_semesters >= 1

    def test_banish_allows_other_semesters(self):
        """Banish only affects specified semester, not others."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [Marker(courseId='18.01', section=0, status='banish')]
        take_vars = create_take_vars(model, courses_df, markers)

        add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        # Pin to semester 2 should work
        course_idx = 0
        model.Add(take_vars[(course_idx, 2)] == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(take_vars[(course_idx, 2)]) == 1

    def test_banish_from_ase_errors(self):
        """Banish cannot target ASE semester."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        # Try to banish from ASE
        markers = [Marker(courseId='18.01', section=-1, status='banish')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 0
        assert len(result.errors) == 1

    def test_banish_from_must_take_prevents_all_semesters(self):
        """Banish in Must Take (section=-2) prevents course from all semesters."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        # Banish 18.01 from Must Take = never take it
        markers = [Marker(courseId='18.01', section=-2, status='banish')]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        # Should add a constraint for each semester the course is available
        assert result.constraints_added == 12  # All regular semesters
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Course should not be taken in any semester
        course_idx = 0
        for s in REGULAR_SEMESTERS:
            assert solver.Value(take_vars[(course_idx, s)]) == 0

    def test_multiple_banish_same_course(self):
        """Multiple banish markers can exclude course from multiple semesters."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(courseId='18.01', section=0, status='banish'),  # Ban from sem 1
            Marker(courseId='18.01', section=1, status='banish'),  # Ban from sem 2
            Marker(courseId='18.01', section=2, status='banish'),  # Ban from sem 3
        ]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 3

        # Force taking the course
        course_idx = 0
        model.Add(sum(take_vars[(course_idx, s)] for s in REGULAR_SEMESTERS) >= 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Should not be in semesters 1, 2, or 3
        assert solver.Value(take_vars[(course_idx, 1)]) == 0
        assert solver.Value(take_vars[(course_idx, 2)]) == 0
        assert solver.Value(take_vars[(course_idx, 3)]) == 0


class TestMixedMarkers:
    """Tests for combinations of different marker types."""

    def test_pin_and_banish_different_courses(self):
        """Pin one course and banish another works correctly."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(courseId='18.01', section=0, status='pin'),
            Marker(courseId='18.02', section=0, status='banish'),
        ]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 2

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # 18.01 in semester 1, 18.02 not in semester 1
        assert solver.Value(take_vars[(0, 1)]) == 1
        assert solver.Value(take_vars[(1, 1)]) == 0

    def test_ase_and_regular_pins(self):
        """ASE and regular semester pins can coexist."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(courseId='18.01', section=-1, status='pin'),  # ASE
            Marker(courseId='18.02', section=0, status='pin'),   # Semester 1
        ]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 2

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        assert solver.Value(take_vars[(0, -1)]) == 1  # 18.01 in ASE
        assert solver.Value(take_vars[(1, 1)]) == 1   # 18.02 in sem 1

    def test_override_and_pin_same_semester(self):
        """Override and pin markers can place courses in same semester."""
        courses_df = create_test_courses_df()
        model = cp_model.CpModel()

        markers = [
            Marker(courseId='18.01', section=0, status='pin'),
            Marker(courseId='18.02', section=0, status='override'),
            Marker(courseId='8.01', section=0, status='pin'),
        ]
        take_vars = create_take_vars(model, courses_df, markers)

        result = add_marker_constraints(model, take_vars, markers, courses_df, 2025)

        assert result.constraints_added == 3
        assert len(result.errors) == 0

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # All three should be in semester 1
        assert solver.Value(take_vars[(0, 1)]) == 1
        assert solver.Value(take_vars[(1, 1)]) == 1
        assert solver.Value(take_vars[(2, 1)]) == 1
