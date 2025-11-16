"""
Optimizer worker: runs CP-SAT optimization jobs in background.

This worker handles:
- Requirement constraints (GIRs, major requirements)
- Prerequisite constraints
- User markers (pin, banish, solo)
- Objective functions (minimize units, maximize ratings, etc.)
- Real-time progress streaming via Redis
"""

import asyncio
import json
from typing import Any, Dict, List

import pandas as pd
import redis.asyncio as redis
from ortools.sat.python import cp_model

from courses.prerequisites.parser import parse_fireroad
from courses.requirements.parser import parse_requirement
from courses.requirements.validator import validate_and_prune
from optimizer.marker_constraint_builder import add_marker_constraints, parse_markers_from_dict
from optimizer.objectives import (
    FrontloadCourses,
    MaximizeRating,
    MinimizeTotalHours,
    MinimizeUnits,
    ObjectiveBuilder,
)
from optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from optimizer.requirement_constraint_builder import add_requirement_constraints
from utils.utils import find_current_school_year, is_valid_class_semester

# Type aliases for clarity
CourseData = List[Dict[str, Any]]
RequirementsData = Dict[str, Any]
TakeVars = Dict[tuple[int, int], cp_model.IntVar]


class RedisStreamCallback(cp_model.CpSolverSolutionCallback):
    """
    CP-SAT callback that publishes solutions to Redis Stream for SSE.
    
    Runs in synchronous context (CP-SAT constraint) but queues messages
    for async publishing to avoid blocking the solver.
    """

    def __init__(
        self,
        take_vars: TakeVars,
        courses_df: pd.DataFrame,
        job_id: str,
        redis_client: redis.Redis
    ):
        super().__init__()
        self.take_vars = take_vars
        self.courses_df = courses_df
        self.job_id = job_id
        self.redis_client = redis_client
        self.solution_count = 0
        self._pending_messages: List[Dict[str, Any]] = []

    def on_solution_callback(self) -> None:
        self.solution_count += 1

        # Check for cancellation request (checked on each solution)
        # Allows responsive cancellation without busy-waiting
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            cancel_flag = loop.run_until_complete(
                self.redis_client.get(f"cancel:{self.job_id}")
            )
            if cancel_flag:
                print(f"Job {self.job_id} cancelled by user")
                self.StopSearch()
                return
        except:
            pass  # Don't fail solve if cancellation check fails

        nodes = []
        semester_units = [0] * 12

        for (course_idx, semester), var in self.take_vars.items():
            if self.Value(var) != 0:
                course_id = self.courses_df.at[course_idx, 'subject_id']
                title = self.courses_df.at[course_idx, 'title'] if 'title' in self.courses_df.columns else None
                units = self.courses_df.at[course_idx, 'total_units'] if 'total_units' in self.courses_df.columns else 12

                nodes.append({
                    "courseId": course_id,
                    "section": semester - 1,  # Convert to 0-based for frontend
                    "title": title
                })

                if pd.notna(units):
                    semester_units[semester - 1] += int(units)

        message = {
            "type": "solution",
            "step": self.solution_count,
            "nodes": nodes,
            "semesterUnits": semester_units,
            "objectiveValue": self.ObjectiveValue()
        }

        # Queue message for async publishing
        self._pending_messages.append(message)

    async def publish_pending_messages(self) -> None:
        """Publish all pending messages to Redis Stream"""
        for message in self._pending_messages:
            await self.redis_client.xadd(
                f"optimization:{self.job_id}",
                {"data": json.dumps(message)}
            )
        self._pending_messages.clear()


def create_take_vars(model: cp_model.CpModel, courses_df: pd.DataFrame, planning_year_start: int, max_semesters: int) -> TakeVars:
    """Create decision variables for taking courses."""
    take_vars = {}

    for course_idx in courses_df.index:
        subject_id = courses_df.at[course_idx, 'subject_id']

        for semester in range(1, max_semesters + 1):
            if is_valid_class_semester(course_idx, semester, courses_df, planning_year_start):
                var_name = f"take_{subject_id.replace('.', '_')}_s{semester}"
                take_vars[(course_idx, semester)] = model.NewBoolVar(var_name)

    return take_vars


def add_basic_constraints(
    model: cp_model.CpModel,
    take_vars: TakeVars,
    courses_df: pd.DataFrame,
    max_units_per_semester: int,
    max_units_iap: int,
    max_semesters: int
):
    """Add basic constraints like max units per semester, taking course once, etc."""

    # Constraint: Take each course at most once
    for course_idx in courses_df.index:
        course_takes = [
            take_vars[(course_idx, s)]
            for s in range(1, max_semesters + 1)
            if (course_idx, s) in take_vars
        ]
        if course_takes:
            model.Add(sum(course_takes) <= 1)

    # Constraint: Max units per semester
    for semester in range(1, max_semesters + 1):
        # Determine max units for this semester
        # Semester 1 is always fall (48 units)
        # IAP semesters: 2, 5, 8, 11 (every 3rd semester starting from 2)
        is_iap = (semester - 2) % 3 == 0 and semester >= 2 and semester <= 11
        max_units = max_units_iap if is_iap else max_units_per_semester

        semester_takes = [
            take_vars[(c, semester)] * courses_df.at[c, 'total_units']
            for c in courses_df.index
            if (c, semester) in take_vars and 'total_units' in courses_df.columns and pd.notna(courses_df.at[c, 'total_units'])
        ]
        if semester_takes:
            model.Add(sum(semester_takes) <= max_units)


def parse_prerequisites_for_all_courses(courses_df: pd.DataFrame) -> dict:
    """Parse prerequisites for all courses."""
    prereq_trees = {}

    for course_idx in courses_df.index:
        prereq_str = courses_df.at[course_idx, 'prerequisites']

        if pd.notna(prereq_str) and prereq_str:
            try:
                prereq_tree = parse_fireroad(prereq_str)
                if prereq_tree is not None:
                    prereq_trees[course_idx] = prereq_tree
            except Exception:
                # Silently skip courses with unparseable prerequisites
                pass

    return prereq_trees


async def run_optimization_job(
    ctx: Dict[str, Any],
    job_id: str,
    request_data: Dict[str, Any],
    courses_data: CourseData,
    requirements_data: RequirementsData
) -> None:
    """
    arq worker function to run CP-SAT optimization.
    
    This is the main entry point for background optimization jobs.
    Publishes real-time progress to Redis Stream for SSE consumption.
    
    Args:
        ctx: arq context (contains redis pool)
        job_id: Unique job identifier (UUID)
        request_data: Optimization request with markers, requirements, constraints
        courses_data: List of course dictionaries from Fireroad API
        requirements_data: Requirements trees keyed by requirement name
        
    Raises:
        Exception: Any error during optimization (logged and published to stream)
    """

    redis_client = ctx['redis']

    try:
        # Publish progress: initialization
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Initializing optimization...",
                "step": 1,
                "totalSteps": 10
            })}
        )

        # Convert to DataFrame
        courses_df = pd.DataFrame(courses_data)

        # Get planning year
        planning_year = request_data.get('planningYear')
        if not planning_year:
            _, planning_year = find_current_school_year()

        planning_year_start = int(planning_year.split('-')[0])

        # Extract constraints
        constraints = request_data.get('constraints', {})
        max_semesters = constraints.get('maxSemesters', 12)
        max_units_per_semester = constraints.get('maxUnitsPerSemester', 60)
        max_units_iap = constraints.get('maxUnitsIAP', 12)
        max_hours_per_semester = constraints.get('maxHoursPerSemester', 60)

        # Publish progress: creating model
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Creating decision variables...",
                "step": 2,
                "totalSteps": 10
            })}
        )

        # Create model
        model = cp_model.CpModel()
        take_vars = create_take_vars(model, courses_df, planning_year_start, max_semesters)

        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": f"Created {len(take_vars)} decision variables",
                "step": 3,
                "totalSteps": 10
            })}
        )

        # Add basic constraints
        add_basic_constraints(
            model, take_vars, courses_df,
            max_units_per_semester, max_units_iap, max_semesters
        )

        # Publish progress: requirements
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Adding requirement constraints...",
                "step": 4,
                "totalSteps": 10
            })}
        )

        # Add requirement constraints
        for req_key in request_data.get('requirements', ['girs']):
            if req_key in requirements_data:
                req_data = requirements_data[req_key]
                req_tree = parse_requirement({'reqs': req_data.get('reqs', []), 'title': req_key})

                # Validate and prune
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)

                # Add constraints
                add_requirement_constraints(
                    model, take_vars, validation.pruned_tree,
                    courses_df, planning_year_start, enforce=True
                )

        # Publish progress: prerequisites
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Adding prerequisite constraints...",
                "step": 5,
                "totalSteps": 10
            })}
        )

        # Add prerequisite constraints
        prereq_trees = parse_prerequisites_for_all_courses(courses_df)
        prereq_result = add_prerequisite_constraints(
            model, take_vars, courses_df, planning_year_start, prereq_trees
        )

        # Publish progress: markers
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Adding user markers...",
                "step": 6,
                "totalSteps": 10
            })}
        )

        # Add marker constraints
        markers_data = request_data.get('markers', [])
        markers = parse_markers_from_dict(markers_data)
        marker_result = add_marker_constraints(
            model, take_vars, markers, courses_df, planning_year_start
        )

        # Publish progress: objectives
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Building objective function...",
                "step": 7,
                "totalSteps": 10
            })}
        )

        # Build objective function
        # TODO: Allow user to customize objective weights
        builder = ObjectiveBuilder()
        builder.add(MinimizeUnits(), weight=0.4)
        builder.add(MaximizeRating(target_rating=6.0), weight=0.3)
        builder.add(MinimizeTotalHours(default_hours=12.0), weight=0.2)
        builder.add(FrontloadCourses(), weight=0.1)

        objective = builder.build(model, take_vars, courses_df, planning_year_start)
        model.Minimize(objective)

        # Publish progress: solving
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Starting solver...",
                "step": 8,
                "totalSteps": 10
            })}
        )

        # Create callback
        callback = RedisStreamCallback(
            take_vars, courses_df, job_id, redis_client
        )

        # Configure solver
        solver = cp_model.CpSolver()
        solver.parameters.enumerate_all_solutions = True
        solver.parameters.max_time_in_seconds = 30

        # Run solver in thread pool (still blocks but worker is separate process)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, solver.Solve, model, callback)

        # Publish any remaining messages
        await callback.publish_pending_messages()

        # Map status
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID"
        }

        # Collect warnings
        warnings = []
        if result == cp_model.FEASIBLE:
            warnings.append("Solution found but may not be optimal (time limit reached)")
        elif result == cp_model.INFEASIBLE:
            warnings.append("No feasible solution found - constraints may be too strict")
            # Add specific warnings about marker conflicts
            if marker_result.errors:
                warnings.extend(marker_result.errors[:3])

        # Get final solution nodes
        final_nodes = []
        if callback._pending_messages and callback._pending_messages[-1].get('type') == 'solution':
            final_nodes = callback._pending_messages[-1].get('nodes', [])
        elif result in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            # Reconstruct from solver state if no pending messages
            for (course_idx, semester), var in take_vars.items():
                if solver.Value(var) != 0:
                    course_id = courses_df.at[course_idx, 'subject_id']
                    title = courses_df.at[course_idx, 'title'] if 'title' in courses_df.columns else None
                    final_nodes.append({
                        "courseId": course_id,
                        "section": semester - 1,  # Convert to 0-based for frontend
                        "title": title
                    })

        # Publish completion
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "complete",
                "status": status_map.get(result, "MODEL_INVALID"),
                "solutionCount": callback.solution_count,
                "warnings": warnings
            })}
        )

        # Store final result
        await redis_client.set(
            f"optimization:result:{job_id}",
            json.dumps({
                "status": status_map.get(result, "MODEL_INVALID"),
                "solutionCount": callback.solution_count,
                "nodes": final_nodes,
                "warnings": warnings
            }),
            ex=3600  # Expire after 1 hour
        )

    except Exception as e:
        # Publish error
        error_message = str(e)
        error_type = type(e).__name__

        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "error",
                "error": error_message,
                "details": error_type
            })}
        )

        # Re-raise so arq logs it
        raise
