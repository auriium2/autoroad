import asyncio
import json
from typing import Any, Dict, List

import pandas as pd
import redis.asyncio as redis
from backend.scripts.analyze import add_prerequisite_constraints, add_requirement_constraints
from backend.utils.utils import find_current_school_year, is_valid_class_semester
from ortools.sat.python import cp_model

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
        take: TakeVars,
        group_vars: Dict[str, Any],
        units: pd.Series,
        classes: pd.Series,
        courses_df: pd.DataFrame,
        job_id: str,
        redis_client: redis.Redis
    ):
        super().__init__()
        self.take = take
        self.group_vars = group_vars
        self.units = units
        self.classes = classes
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

        for (c, s), v in self.take.items():
            if self.Value(v) != 0:
                course_id = self.classes.loc[c]
                units = self.units.loc[c]
                title = self.courses_df.loc[c, "title"] if "title" in self.courses_df.columns else None

                nodes.append({
                    "courseId": course_id,
                    "semester": s,
                    "title": title
                })

                semester_units[s - 1] += int(units)

        group_status = {}
        for name, var in self.group_vars.items():
            try:
                if isinstance(var, dict):
                    continue
                group_status[name] = self.Value(var) == 1
            except:
                group_status[name] = None

        message = {
            "type": "solution",
            "step": self.solution_count,
            "nodes": nodes,
            "semesterUnits": semester_units,
            "groupVars": group_status
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
        # Publish progress
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Initializing optimization...",
                "step": 0
            })}
        )

        # Convert to DataFrame
        courses_df = pd.DataFrame(courses_data)

        planning_year = request_data.get('planningYear')
        if not planning_year:
            school_year, planning_year = find_current_school_year()

        planning_year_start = int(planning_year.split('-')[0])

        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Building constraint model...",
                "step": 1
            })}
        )

        model = cp_model.CpModel()
        classes = courses_df['subject_id']
        units = courses_df['total_units']

        C = request_data.get('constraints', {}).get('maxUnitsPerSemester', 60)
        C_IAP = request_data.get('constraints', {}).get('maxUnitsIAP', 12)
        PLANNING_HORIZON = request_data.get('constraints', {}).get('maxSemesters', 12)

        take = {}
        for c, el in classes.items():
            for s in range(1, PLANNING_HORIZON + 1):
                if not is_valid_class_semester(c, s, courses_df, planning_year_start):
                    continue
                take[c, s] = model.NewBoolVar(f"take_{c}_{s}")

        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": f"Created {len(take)} decision variables",
                "step": 2
            })}
        )

        semCred = {
            s: model.NewIntVar(
                0,
                48 if s == 1 else (C_IAP if (s - 2) % 3 == 0 and s <= 11 else C),
                f"semCred_{s}"
            )
            for s in range(1, PLANNING_HORIZON + 1)
        }

        group_vars = {}

        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Adding requirement constraints...",
                "step": 3
            })}
        )

        for req_key in request_data.get('requirements', ['girs']):
            if req_key in requirements_data:
                req_tree = requirements_data[req_key].get('reqs')
                add_requirement_constraints(
                    model, take, req_tree, courses_df, planning_year_start, group_vars
                )

        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Adding prerequisite constraints...",
                "step": 4
            })}
        )

        add_prerequisite_constraints(model, take, courses_df, planning_year_start)

        for s in range(1, PLANNING_HORIZON + 1):
            creditsum = sum(
                units[c] * take[c, s]
                for c in classes.index
                if is_valid_class_semester(c, s, courses_df, planning_year_start)
            )
            model.Add(semCred[s] == creditsum)

        # Apply markers
        markers = request_data.get('markers', [])
        for marker in markers:
            course_id = marker['courseId']
            section = marker['section']
            status = marker['status']

            course_indices = courses_df.index[courses_df['subject_id'] == course_id].tolist()
            if not course_indices:
                continue

            c = course_indices[0]

            if status == 'pin':
                if (c, section) in take:
                    model.Add(take[c, section] == 1)
            elif status == 'banish':
                for s in range(1, PLANNING_HORIZON + 1):
                    if (c, s) in take:
                        model.Add(take[c, s] == 0)

        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "progress",
                "message": "Starting solver...",
                "step": 5
            })}
        )

        finish_time = sum(
            take[idx, s]
            for idx in classes.index
            for s in range(1, PLANNING_HORIZON + 1)
            if is_valid_class_semester(idx, s, courses_df, planning_year_start)
        )
        model.Minimize(finish_time)

        callback = RedisStreamCallback(
            take, group_vars, units, classes, courses_df, job_id, redis_client
        )

        solver = cp_model.CpSolver()
        solver.parameters.enumerate_all_solutions = True
        solver.parameters.max_time_in_seconds = 20

        # Run solver in thread pool (still blocks but worker is separate process)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, solver.Solve, model, callback)

        # Publish any remaining messages
        await callback.publish_pending_messages()

        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID"
        }

        warnings = []
        if result == cp_model.FEASIBLE:
            warnings.append("Solution found but may not be optimal")
        elif result == cp_model.INFEASIBLE:
            warnings.append("No feasible solution found - constraints may be too strict")

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

        # Get final solution nodes
        final_nodes = []
        if callback._pending_messages:
            # Get last solution if available
            for msg in reversed(callback._pending_messages):
                if msg.get('type') == 'solution':
                    final_nodes = msg.get('nodes', [])
                    break

        # If no pending messages, reconstruct from solver state
        if not final_nodes and result in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            for (c, s), v in take.items():
                if solver.Value(v) != 0:
                    course_id = classes.loc[c]
                    title = courses_df.loc[c, "title"] if "title" in courses_df.columns else None
                    final_nodes.append({
                        "courseId": course_id,
                        "semester": s,
                        "title": title
                    })

        # Set job result with full solution
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
        await redis_client.xadd(
            f"optimization:{job_id}",
            {"data": json.dumps({
                "type": "error",
                "error": str(e),
                "details": str(type(e).__name__)
            })}
        )
        raise
