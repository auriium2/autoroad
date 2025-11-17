"""
Integration tests for optimizer feasibility with real Fireroad data.

These tests ensure that common scheduling scenarios produce feasible solutions.
They use real course data from Fireroad and test various marker combinations.
"""
import pytest
import requests
import polars as pl
from ortools.sat.python import cp_model

from api.routes.optimize import (
    create_take_vars,
    add_basic_constraints,
    parse_prerequisites_for_all_courses,
)
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.marker_constraint_builder import add_marker_constraints
from optimizer.objectives.builder import ObjectiveBuilder
from optimizer.objectives.units import MinimizeUnits
from optimizer.objectives.ratings import MaximizeRating
from api.models.requests import Marker


@pytest.fixture(scope="module")
def fireroad_courses_df():
    """Fetch all courses from Fireroad and return as polars DataFrame."""
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    courses_data = response.json()
    courses_data = [c for c in courses_data if not c.get('is_historical')]
    # CRITICAL: Use infer_schema_length=None to detect all columns
    return pl.DataFrame(courses_data, infer_schema_length=None)


class TestOptimizerFeasibility:
    """Test that the optimizer produces feasible solutions for common scenarios."""
    
    def test_girs_only_is_feasible(self, fireroad_courses_df):
        """
        Test that scheduling just GIRs is feasible.
        
        This is the most basic scenario - student needs to complete:
        - 2 Physics (PHY1, PHY2)
        - 2 Calculus (CAL1, CAL2)  
        - 1 Chemistry (CHEM)
        - 1 Biology (BIOL)
        """
        model = cp_model.CpModel()
        planning_year_start = 2024
        max_semesters = 8
        
        # Create take variables
        take_vars = create_take_vars(
            model, 
            fireroad_courses_df, 
            planning_year_start, 
            max_semesters,
            markers=None
        )
        
        # Add basic constraints
        add_basic_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            max_units_per_semester=60,
            max_units_iap=12,
            max_semesters=max_semesters
        )
        
        # Add prerequisites
        prereq_trees = parse_prerequisites_for_all_courses(fireroad_courses_df)
        add_prerequisite_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            planning_year_start,
            prereq_trees,
            override_course_ids=set()
        )
        
        # Add minimal objective (minimize total courses)
        objective_builder = ObjectiveBuilder()
        objective_builder.add(MinimizeUnits(), weight=1.0)
        objective = objective_builder.build(model, take_vars, fireroad_courses_df, planning_year_start)
        model.Minimize(objective)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.Solve(model)
        
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "GIRs-only scenario should be feasible"
    
    def test_pinned_courses_is_feasible(self, fireroad_courses_df):
        """
        Test that pinning common freshman courses is feasible.
        
        Pins:
        - 18.01 (Calculus 1) - Semester 1
        - 8.01 (Physics 1) - Semester 1  
        - 6.100A (Intro CS) - Semester 1
        - 5.111 (Chemistry) - Semester 1
        """
        model = cp_model.CpModel()
        planning_year_start = 2024
        max_semesters = 8
        
        markers = [
            Marker(courseId='18.01', status='pin', section=0),  # Semester 0 = Freshman Fall
            Marker(courseId='8.01', status='pin', section=0),
            Marker(courseId='6.100A', status='pin', section=0),
            Marker(courseId='5.111', status='pin', section=0),
        ]
        
        take_vars = create_take_vars(
            model,
            fireroad_courses_df,
            planning_year_start,
            max_semesters,
            markers=markers
        )
        
        # Add marker constraints
        marker_result = add_marker_constraints(
            model,
            take_vars,
            markers,
            fireroad_courses_df,
            planning_year_start
        )
        
        assert marker_result.constraints_added == 4, "Should add 4 pin constraints"
        assert len(marker_result.errors) == 0, "Should have no errors"
        
        add_basic_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            max_units_per_semester=60,
            max_units_iap=12,
            max_semesters=max_semesters
        )
        
        prereq_trees = parse_prerequisites_for_all_courses(fireroad_courses_df)
        add_prerequisite_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            planning_year_start,
            prereq_trees,
            override_course_ids=set()
        )
        
        objective_builder = ObjectiveBuilder()
        objective_builder.add(MinimizeUnits(), weight=1.0)
        objective = objective_builder.build(model, take_vars, fireroad_courses_df, planning_year_start)
        model.Minimize(objective)
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.Solve(model)
        
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Pinned courses scenario should be feasible"
    
    def test_ase_with_markers_is_feasible(self, fireroad_courses_df):
        """
        Test that ASE (Advanced Standing Exam) with markers is feasible.
        
        ASE:
        - 18.01 (got credit, semester -1)
        
        Pins:
        - 18.02 (Calculus 2) - Semester 1
        - 8.01 (Physics 1) - Semester 1
        - 6.100A (Intro CS) - Semester 1  
        - 5.111 (Chemistry) - Semester 1
        """
        model = cp_model.CpModel()
        planning_year_start = 2024
        max_semesters = 8
        
        markers = [
            Marker(courseId='18.01', status='pin', section=-1),  # ASE credit (use pin with section=-1)
            Marker(courseId='18.02', status='pin', section=0),  # Freshman Fall
            Marker(courseId='8.01', status='pin', section=0),  # Freshman Fall
            Marker(courseId='6.100A', status='pin', section=0),  # Freshman Fall
            Marker(courseId='5.111', status='pin', section=0),  # Freshman Fall
        ]
        
        take_vars = create_take_vars(
            model,
            fireroad_courses_df,
            planning_year_start,
            max_semesters,
            markers=markers
        )
        
        marker_result = add_marker_constraints(
            model,
            take_vars,
            markers,
            fireroad_courses_df,
            planning_year_start
        )
        
        assert marker_result.constraints_added == 5
        assert len(marker_result.errors) == 0
        
        add_basic_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            max_units_per_semester=60,
            max_units_iap=12,
            max_semesters=max_semesters
        )
        
        prereq_trees = parse_prerequisites_for_all_courses(fireroad_courses_df)
        # ASE courses can satisfy prerequisites
        add_prerequisite_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            planning_year_start,
            prereq_trees,
            override_course_ids=set()
        )
        
        objective_builder = ObjectiveBuilder()
        objective_builder.add(MinimizeUnits(), weight=1.0)
        objective = objective_builder.build(model, take_vars, fireroad_courses_df, planning_year_start)
        model.Minimize(objective)
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.Solve(model)
        
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "ASE with markers scenario should be feasible"
    
    def test_override_marker_is_feasible(self, fireroad_courses_df):
        """
        Test that override markers (ignoring prerequisites) work.
        
        Override:
        - 18.02 (normally requires 18.01, but we override) - Semester 1
        
        Pins:
        - 8.01 (Physics 1) - Semester 1
        - 6.100A (Intro CS) - Semester 1
        - 5.111 (Chemistry) - Semester 1
        """
        model = cp_model.CpModel()
        planning_year_start = 2024
        max_semesters = 8
        
        markers = [
            Marker(courseId='18.02', status='override', section=0),  # Override prereqs
            Marker(courseId='8.01', status='pin', section=0),
            Marker(courseId='6.100A', status='pin', section=0),
            Marker(courseId='5.111', status='pin', section=0),
        ]
        
        take_vars = create_take_vars(
            model,
            fireroad_courses_df,
            planning_year_start,
            max_semesters,
            markers=markers
        )
        
        marker_result = add_marker_constraints(
            model,
            take_vars,
            markers,
            fireroad_courses_df,
            planning_year_start
        )
        
        assert marker_result.constraints_added == 4
        assert len(marker_result.errors) == 0
        
        add_basic_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            max_units_per_semester=60,
            max_units_iap=12,
            max_semesters=max_semesters
        )
        
        prereq_trees = parse_prerequisites_for_all_courses(fireroad_courses_df)
        # Override courses skip prerequisite checks
        add_prerequisite_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            planning_year_start,
            prereq_trees,
            override_course_ids={'18.02'}
        )
        
        objective_builder = ObjectiveBuilder()
        objective_builder.add(MinimizeUnits(), weight=1.0)
        objective = objective_builder.build(model, take_vars, fireroad_courses_df, planning_year_start)
        model.Minimize(objective)
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.Solve(model)
        
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Override marker scenario should be feasible"
    
    def test_realistic_course_load_is_feasible(self, fireroad_courses_df):
        """
        Test a realistic full 4-year schedule with various course types.
        
        This tests a more complex scenario with:
        - Multiple semesters of courses
        - Prerequisites that need to be satisfied
        - Mix of GIRs and major courses
        """
        model = cp_model.CpModel()
        planning_year_start = 2024
        max_semesters = 8
        
        # Typical EECS freshman/sophomore courses (only Fall offerings to keep it simple)
        markers = [
            # Freshman Fall (Section 0)
            Marker(courseId='18.01', status='pin', section=0),
            Marker(courseId='8.01', status='pin', section=0),
            Marker(courseId='6.100A', status='pin', section=0),
            
            # Sophomore Fall (Section 3)
            Marker(courseId='6.1200', status='pin', section=3),  # Math for CS
            Marker(courseId='18.03', status='pin', section=3),  # Diff Eq
        ]
        
        take_vars = create_take_vars(
            model,
            fireroad_courses_df,
            planning_year_start,
            max_semesters,
            markers=markers
        )
        
        marker_result = add_marker_constraints(
            model,
            take_vars,
            markers,
            fireroad_courses_df,
            planning_year_start
        )
        
        assert marker_result.constraints_added == 5
        assert len(marker_result.errors) == 0
        
        add_basic_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            max_units_per_semester=60,
            max_units_iap=12,
            max_semesters=max_semesters
        )
        
        prereq_trees = parse_prerequisites_for_all_courses(fireroad_courses_df)
        add_prerequisite_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            planning_year_start,
            prereq_trees,
            override_course_ids=set()
        )
        
        # Use default objectives
        objective_builder = ObjectiveBuilder()
        objective_builder.add(MinimizeUnits(), weight=1.0)
        objective_builder.add(MaximizeRating(), weight=0.5)
        objective = objective_builder.build(model, take_vars, fireroad_courses_df, planning_year_start)
        model.Minimize(objective)
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)
        
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Realistic course load scenario should be feasible"
    
    def test_banish_marker_is_feasible(self, fireroad_courses_df):
        """
        Test that banish markers (preventing courses in specific semesters) work.
        
        Banish:
        - 18.01 from Semester 1 (will be placed elsewhere)
        
        Pin:
        - 8.01 in Semester 1
        """
        model = cp_model.CpModel()
        planning_year_start = 2024
        max_semesters = 8
        
        markers = [
            Marker(courseId='18.01', status='banish', section=0),  # Freshman Fall,  # Can't take in Sem 1
            Marker(courseId='8.01', status='pin', section=0),  # Freshman Fall
        ]
        
        take_vars = create_take_vars(
            model,
            fireroad_courses_df,
            planning_year_start,
            max_semesters,
            markers=markers
        )
        
        marker_result = add_marker_constraints(
            model,
            take_vars,
            markers,
            fireroad_courses_df,
            planning_year_start
        )
        
        # Banish adds a constraint, pin adds a constraint
        assert marker_result.constraints_added >= 2
        assert len(marker_result.errors) == 0
        
        add_basic_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            max_units_per_semester=60,
            max_units_iap=12,
            max_semesters=max_semesters
        )
        
        prereq_trees = parse_prerequisites_for_all_courses(fireroad_courses_df)
        add_prerequisite_constraints(
            model,
            take_vars,
            fireroad_courses_df,
            planning_year_start,
            prereq_trees,
            override_course_ids=set()
        )
        
        objective_builder = ObjectiveBuilder()
        objective_builder.add(MinimizeUnits(), weight=1.0)
        objective = objective_builder.build(model, take_vars, fireroad_courses_df, planning_year_start)
        model.Minimize(objective)
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.Solve(model)
        
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE], \
            "Banish marker scenario should be feasible"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
